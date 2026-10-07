"""Several computers, one archive.

One computer, the hub, is the only one that writes the database: it records, analyzes and serves the dashboard.
The others (spokes) send it their coding agents' raw session files over HTTP, usually inside a Tailscale network,
and the hub ingests them as if they were its own, tagged with the computer they came from. A push is stateless:
the spoke asks the hub which files it already has (by size and modification time) and sends only the rest, so a
lost push is simply redone by the next one.

A spoke that already analyzed sessions with its own Chronicle sends those results once, when it first joins, so
the hub does not pay to analyze the same sessions again.

With `[hub] store = "postgres"` the hub also keeps the team's record in Postgres (team_store.py), and each computer
that shares knowledge gets its teammates' lessons for its own projects back after every push, kept read-only in its
own database (knowledge.source 'team') where its MCP tools and start-of-session notes find them.

Projects can be set up on the hub ahead of time (`chronicle hub project add <folder>`): a folder on the hub computer
whose sessions, and everything below it, are one project that other computers can add folders to before anything was
sent. Its own analyzed sessions go to the team store like a member's, so teammates get the hub owner's lessons too.
A person limited to projects (people.py) hears only of those projects, and the hub keeps only what belongs to them.
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import http.client
import json
import logging
import os
import platform
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlencode, urlparse

from . import __version__
from .config import Config
from .util import utcnow_iso

log = logging.getLogger("chronicle.hub")

PROTOCOL = 1
TOKEN_FILE = "hub-token"
ROOT_RE = re.compile(r"^(claude|codex)(-\d+)?$")
MACHINE_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_FILE_BYTES = 4 << 30  # one transcript; far above any real one
ANALYSES_FILE = "analyses.json.gz"
ANALYSES_MAX_AGE = 30 * 86400  # imported analyses whose sessions never arrive are dropped after this
REPOS_CACHE_S = 86400
FOLDERS_KV = "hub-folders:"  # + machine id: the folders that computer added to projects here (spoke's [hub] folders)
FOLDERS_FILE = "hub-folders.json"  # on a spoke: what the hub made of its folders at the last hello
MAX_FOLDERS = 200

# The analysis a spoke's own Chronicle already wrote, carried over when it joins (see export_analyses).
ANALYSIS_COLS = ("analysis_status", "analysis_reason", "analyzed_at", "analysis_model", "analyzed_prompts", "llm_title",
                 "summary", "goal", "outcome", "outcome_note", "sentiment", "work_types_json", "tags_json",
                 "highlights_json", "open_threads_json", "friction_json", "analysis_json")
KNOWLEDGE_COLS = ("kind", "title", "body", "tags_json", "scope", "confidence", "evidence", "source", "agent",
                  "source_ref", "fingerprint", "status", "pinned", "created_at", "updated_at")

# [hub] share = "knowledge": what a computer sends about a session it analyzed itself. Never its prompts, commands,
# file paths or transcript; the hub stores it with source 'remote' and never analyzes it again (receive_sessions).
SHARED_COLS = ("agent", "started_at", "ended_at", "duration_s", "active_s", "git_branch", "cc_version", "primary_model",
               "models_json", "tools_json", "skills_json", "mcp_json", "prs_json", "n_prompts", "n_api_calls",
               "n_tool_calls", "n_tool_errors", "n_interrupts", "n_compactions", "n_api_errors", "n_subagents", "n_files",
               "lines_added", "lines_removed", "input_tokens", "output_tokens", "cache_read_tokens",
               "cache_write_tokens", "sub_tokens", "est_cost_usd", "sub_cost_usd", "peak_context", "ended_flag")
SHARED_AGENTS = ("claude", "codex", "copilot", "bob", "antigravity")  # coding agents; imported chats stay personal
SHARE_BATCH = 200
SHARE_KV = "hub-share:"  # + machine id: what that computer sends, as it last said
SESSION_ID_RE = re.compile(r"^[\w.:-]{1,128}$")
TEAM_FILE = "team-lessons.json"  # on a computer that shares knowledge: the team lessons it holds, as of the last pull
TEAM_SOURCE = "team"  # knowledge.source of a teammate's lesson the hub sent; fingerprint "team:<lesson id on the hub>"


class HubError(Exception):
    pass


class HubUnreachable(HubError):
    pass


class HubUnauthorized(HubError):
    pass


# ------------------------------------------------------------------ identity
def _computer_name() -> str:
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True, text=True, timeout=3)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    name = socket.gethostname()
    return name[:-6] if name.endswith(".local") else name


def local_machine(cfg: Config) -> dict:
    """This computer's id and name, made once and kept in <home>/machine.json (rename it there)."""
    path = cfg.home / "machine.json"
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict) and MACHINE_RE.match(str(data.get("id", ""))):
            return {"id": data["id"], "name": str(data.get("name") or _computer_name())}
    except (OSError, ValueError):
        pass
    data = {"id": str(uuid.uuid4()), "name": _computer_name()}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)
    return data


def platform_label() -> str:
    return {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(platform.system(), platform.system())


def register_local(conn, cfg: Config) -> str:
    """Record this computer in the machines table; returns its id."""
    me = local_machine(cfg)
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO machines(id, name, platform, version, role, first_seen, last_seen) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET name = excluded.name, platform = excluded.platform, version = excluded.version, "
        "role = excluded.role, last_seen = excluded.last_seen",
        (me["id"], me["name"], platform_label(), __version__, "this", now, now),
    )
    return me["id"]


# ------------------------------------------------------------------ token
def token_path(cfg: Config) -> Path:
    return cfg.home / TOKEN_FILE


def read_token(cfg: Config) -> str | None:
    try:
        token = token_path(cfg).read_text().strip()
    except OSError:
        return None
    return token or None


def write_token(cfg: Config, token: str) -> None:
    path = token_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.with_name(path.name + ".tmp"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(token + "\n")
    os.replace(path.with_name(path.name + ".tmp"), path)


def new_token(cfg: Config) -> str:
    token = secrets.token_urlsafe(32)
    write_token(cfg, token)
    return token


def token_ok(cfg: Config, authorization: str | None) -> bool:
    expected = read_token(cfg)
    if not expected or cfg.is_spoke or not authorization or not authorization.startswith("Bearer "):
        return False
    return hmac.compare_digest(authorization[7:].strip().encode(), expected.encode())


def authorize(cfg: Config, conn, authorization: str | None, machine_id: str | None = None) -> tuple[bool, dict | None]:
    """Who may call /api/hub/*: (ok, person). The hub's shared token is let in (person None) while the hub has no
    people, or while `[hub] shared_token` stays on; a person's own computer token (from `hub join --code`) is let in
    as that person, from the computer it was issued to. Nothing is let in once this computer stopped being a hub."""
    from . import people

    if not read_token(cfg) or cfg.is_spoke or not authorization or not authorization.startswith("Bearer "):
        return False, None
    if token_ok(cfg, authorization):
        return bool(cfg.hub_shared_token or not people.has_people(conn)), None
    person = people.computer_person(conn, authorization[7:].strip(), machine_id or None)
    return (True, person) if person else (False, None)


# ------------------------------------------------------------------ git remotes
def normalize_remote(url: str | None) -> str | None:
    """git@github.com:Org/Repo.git, https://user@github.com/Org/Repo, ssh://git@github.com/Org/Repo -> github.com/org/repo."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    m = re.match(r"^[\w.-]+@([\w.-]+):(.+)$", u)  # scp-like ssh
    if m:
        host, path = m.group(1), m.group(2)
    else:
        parsed = urlparse(u)
        if not parsed.hostname:
            return None
        host, path = parsed.hostname, parsed.path
    path = re.sub(r"\.git/?$", "", path.strip("/"))
    return f"{host.lower()}/{path.lower()}" if path else None


def git_info(path: str) -> tuple[str, str] | None:
    """(top-level folder, normalized remote) of the git repository at path, or None."""
    if not path or not Path(path).is_dir() or not shutil.which("git"):
        return None
    try:
        top = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
        if top.returncode != 0:
            return None
        remotes = subprocess.run(["git", "-C", path, "remote"], capture_output=True, text=True, timeout=5).stdout.split()
        if not remotes:
            return None
        name = "origin" if "origin" in remotes else remotes[0]
        url = subprocess.run(["git", "-C", path, "remote", "get-url", name], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    remote = normalize_remote(url)
    return (top.stdout.strip(), remote) if remote else None


# ------------------------------------------------------------------ what a spoke sends
@dataclass
class Root:
    name: str   # claude, claude-2, codex, …: the folder it lands in on the hub
    kind: str   # claude | codex
    path: Path


def spoke_roots(cfg: Config) -> list[Root]:
    roots = []
    for kind, dirs in (("claude", cfg.claude_dirs), ("codex", cfg.codex_dirs)):
        for i, d in enumerate(dirs):
            if d.is_dir():
                roots.append(Root(kind if i == 0 else f"{kind}-{i + 1}", kind, d))
    return roots


def _walk(base: Path, rel_base: PurePosixPath):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel = PurePosixPath(rel_base, Path(dirpath).relative_to(base).as_posix())
        for fn in filenames:
            if not fn.startswith("."):
                yield str(rel / fn).removeprefix("./"), Path(dirpath) / fn


def root_files(root: Root):
    """(relative path, file) for every file of an agent's folder the hub's ingest reads."""
    if root.kind == "claude":
        projects = root.path / "projects"
        if projects.is_dir():
            yield from _walk(projects, PurePosixPath("projects"))
        if (root.path / "history.jsonl").is_file():
            yield "history.jsonl", root.path / "history.jsonl"
    else:
        for sub in ("sessions", "memories"):
            if (root.path / sub).is_dir():
                yield from _walk(root.path / sub, PurePosixPath(sub))
        for name in ("session_index.jsonl", "external_agent_session_imports.json"):
            if (root.path / name).is_file():
                yield name, root.path / name


class _Exclusions:
    """cfg.exclude_projects, applied on the spoke so excluded projects never leave it."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cache: dict[str, bool] = {}

    def excluded(self, root: Root, rel: str, path: Path) -> bool:
        if not self.cfg.exclude_projects:
            return False
        from .codex_parser import read_meta
        from .ingest import decode_project_dir, peek_cwd

        parts = rel.split("/")
        if root.kind == "claude" and parts[0] == "projects" and len(parts) > 2:
            key = f"{root.name}/{parts[1]}"
            if key not in self.cache:
                proj = root.path / "projects" / parts[1]
                self.cache[key] = self.cfg.is_excluded(peek_cwd(proj) or decode_project_dir(parts[1]))
            return self.cache[key]
        if root.kind == "codex" and parts[0] == "sessions" and path.suffix == ".jsonl":
            return self.cfg.is_excluded(read_meta(path).get("cwd"))
        return False


def spoke_repos(cfg: Config, roots: list[Root]) -> dict[str, list[str]]:
    """{project folder: [git top level, normalized remote]} for the Claude Code projects here, cached for a day."""
    from .ingest import decode_project_dir, peek_cwd

    cache_path = cfg.home / "repos-cache.json"
    try:
        cache = json.loads(cache_path.read_text())
    except (OSError, ValueError):
        cache = {}
    now = time.time()
    out: dict[str, list[str]] = {}
    for root in roots:
        projects = root.path / "projects"
        if root.kind != "claude" or not projects.is_dir():
            continue
        for proj in projects.iterdir():
            if not proj.is_dir():
                continue
            cwd = peek_cwd(proj) or decode_project_dir(proj.name)
            hit = cache.get(cwd)
            if not hit or now - hit.get("at", 0) > REPOS_CACHE_S:
                info = git_info(cwd)
                hit = cache[cwd] = {"at": now, "info": list(info) if info else None}
            if hit.get("info"):
                out[cwd] = hit["info"]
    try:
        cache_path.write_text(json.dumps(cache))
    except OSError:
        pass
    return out


# ------------------------------------------------------------------ folders added by hand
def under(path: str | None, folder: str) -> bool:
    """`path` is `folder` or somewhere below it."""
    if not path:
        return False
    folder = folder.rstrip("/") or "/"
    return path == folder or path.startswith(folder if folder == "/" else folder + "/")


def clean_folders(raw) -> dict[str, str]:
    """A spoke's {folder: project on the hub} as the hub accepts it: absolute paths, a bounded number of them."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in list(raw.items())[:MAX_FOLDERS]:
        k, v = str(k).strip(), str(v).strip()
        if k.startswith("/") and v.startswith("/") and len(k) <= 1024 and len(v) <= 1024 and "\0" not in k + v:
            out[k.rstrip("/") or "/"] = v.rstrip("/") or "/"
    return out


def folders_of(conn, machine_id: str) -> dict[str, str]:
    """The folders another computer added to projects here, as it last reported them."""
    from .db import kv_get

    try:
        data = json.loads(kv_get(conn, FOLDERS_KV + machine_id) or "{}")
    except ValueError:
        return {}
    return clean_folders(data)


def hub_projects(conn, limit: int = 1000, only: list[str] | None = None) -> list[dict]:
    """The projects this hub files sessions under, busiest first, and the ones set up ahead of time: what another
    computer can add a folder to. `only`: just these project paths (a person limited to projects)."""
    from .ingest import project_name_for

    rows = {r[0]: {"path": r[0], "name": r[1], "sessions": r[2]} for r in conn.execute(
        "SELECT project_path, MAX(project_name), COUNT(*) FROM sessions WHERE project_path IS NOT NULL "
        "AND source != 'history' GROUP BY project_path ORDER BY COUNT(*) DESC LIMIT ?", (limit,))}
    for path in declared_projects(conn):
        rows.setdefault(path, {"path": path, "name": project_name_for(path), "sessions": 0})["set_up"] = True
    out = sorted(rows.values(), key=lambda p: -p["sessions"])
    return [p for p in out if only is None or p["path"] in only]


def shared_projects(conn) -> list[dict]:
    """The projects set up on this hub, for the dashboard: where each is, who sees it, and what each computer filed
    there. Everyone with every project (admins included) is counted, not listed."""
    from .ingest import project_name_for
    from .people import listing

    everyone = listing(conn)
    out = []
    for r in conn.execute("SELECT path, created_at, created_by FROM hub_projects ORDER BY path").fetchall():
        path = r["path"]
        computers = [{"id": c["machine_id"], "name": c["name"], "sessions": c["n"], "this": c["this"]} for c in conn.execute(
            "SELECT s.machine_id, m.name, m.role = 'this' AS this, COUNT(*) n FROM sessions s LEFT JOIN machines m "
            "ON m.id = s.machine_id WHERE s.project_path = ? AND s.source != 'history' GROUP BY s.machine_id "
            "ORDER BY n DESC", (path,))]
        folders = []
        for m in conn.execute("SELECT id, name FROM machines WHERE role = 'spoke' ORDER BY name"):
            folders += [{"computer": m["name"] or m["id"][:8], "folder": f} for f, proj in folders_of(conn, m["id"]).items()
                        if proj == path]
        limited = [p for p in everyone if p["projects"] is not None]
        out.append({"path": path, "name": project_name_for(path), "set_up_at": r["created_at"],
                    "sessions": sum(c["sessions"] for c in computers), "computers": computers, "folders": folders,
                    "people": [{"id": p["id"], "name": p["name"], "email": p["email"], "role": p["role"]}
                               for p in limited if path in p["projects"]],
                    "everyone": len(everyone) - len(limited)})
    return out


def declared_projects(conn) -> list[str]:
    """The projects set up on this hub ahead of time (`chronicle hub project add`): folders on this computer."""
    return [r[0] for r in conn.execute("SELECT path FROM hub_projects ORDER BY path")]


def project_folder(folder: str) -> str:
    """A folder as a project path: absolute, without a trailing slash, symlinks kept as the agents recorded them."""
    path = os.path.abspath(os.path.expanduser(str(folder or "").strip()))
    return path.rstrip("/") or "/"


PROJECT_NAME_RULE = "A project's name is up to 80 characters, without / or \\, and doesn't start with a dot."


def named_project_folder(cfg: Config, name: str) -> str:
    """The folder of a project a dedicated hub's admin makes by name (`[hub] dedicated`): <chronicle home>/projects/
    <name>, created here. Only a plain name: never a path, so it can't reach a folder outside that one."""
    name = " ".join(str(name or "").split())
    if (not name or len(name) > 80 or name.startswith(".") or any(c in name for c in "/\\")
            or any(ord(c) < 32 for c in name)):
        raise HubError(PROJECT_NAME_RULE)
    base = (cfg.home / "projects").resolve()
    folder = (base / name).resolve()
    if folder.parent != base:
        raise HubError(PROJECT_NAME_RULE)
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def add_project(cfg: Config, conn, folder: str, *, by: str | None = None) -> dict:
    """Set up a project on this hub ahead of time: `folder`, on this computer, and everything below it. This
    computer's sessions there are filed under it at once (their knowledge moves along), and other computers can add
    folders to it before anything was sent. Returns {path, name, moved}."""
    from .ingest import project_name_for
    from .people import LOCAL

    path = project_folder(folder)
    if under(os.path.expanduser("~").rstrip("/") or "/", path):  # /, /Users, the home folder itself
        raise HubError(f"{path} holds every project: pick the project's own folder")
    have = conn.execute("SELECT COUNT(*) FROM sessions WHERE source != 'history' AND (project_path = ? OR "
                        "machine_path = ? OR substr(project_path, 1, ?) = ? OR substr(machine_path, 1, ?) = ?)",
                        (path, path, len(path) + 1, path + "/", len(path) + 1, path + "/")).fetchone()[0]
    if not Path(path).is_dir() and not have:
        raise HubError(f"{path} is not a folder on this computer, and no session here ran in it")
    inside = [p for p in declared_projects(conn) if under(p, path) or under(path, p)]
    if path in inside:
        return {"path": path, "name": project_name_for(path), "moved": 0, "existed": True}
    if inside:
        raise HubError(f"{path} overlaps the project {inside[0]}: a folder belongs to one project")
    conn.execute("INSERT INTO hub_projects(path, created_at, created_by) VALUES (?, ?, ?)", (path, utcnow_iso(), by or LOCAL))
    conn.commit()
    resolver(cfg, conn, fresh=True)
    moved = refile(cfg, conn, local_machine(cfg)["id"], [path])
    conn.execute("UPDATE knowledge SET project_path = ?, project_name = ? WHERE session_id IS NULL AND "
                 "substr(project_path, 1, ?) = ?", (path, project_name_for(path), len(path) + 1, path + "/"))
    conn.commit()
    held = conn.execute("SELECT COUNT(*) FROM sessions WHERE project_path = ? AND source != 'history'", (path,)).fetchone()[0]
    return {"path": path, "name": project_name_for(path), "moved": moved, "sessions": held, "existed": False}


def remove_project(cfg: Config, conn, folder: str) -> dict:
    """Undo add_project: this computer's sessions in the folder are filed by their own folders again. What other
    computers sent stays where it was filed until they send it again; people keep the project in their lists."""
    path = project_folder(folder)
    if not conn.execute("SELECT 1 FROM hub_projects WHERE path = ?", (path,)).fetchone():
        raise HubError(f"{path} is not a project set up on this hub (`chronicle hub project list`)")
    conn.execute("DELETE FROM hub_projects WHERE path = ?", (path,))
    conn.commit()
    resolver(cfg, conn, fresh=True)
    return {"path": path, "moved": refile(cfg, conn, local_machine(cfg)["id"], [path])}


def refile(cfg: Config, conn, machine_id: str, folders) -> int:
    """File a computer's sessions in `folders` again after its folder mappings changed; their knowledge moves along.

    Both projects' knowledge bases are rebuilt at the next synthesis. Returns how many sessions moved.
    """
    from .ingest import project_name_for

    folders = list(folders)
    r = ProjectResolver(cfg, conn)
    moved, touched = 0, set()
    rows = conn.execute("SELECT id, project_path, machine_path, project_dir FROM sessions WHERE machine_id = ?",
                        (machine_id,)).fetchall()
    for row in rows:
        recorded = row["machine_path"] or row["project_path"]
        if not any(under(recorded, f) for f in folders):
            continue
        new = r.resolve(machine_id, recorded)
        if new == row["project_path"]:
            continue
        name = project_name_for(new, row["project_dir"])
        conn.execute("UPDATE sessions SET project_path = ?, project_name = ?, machine_path = ? WHERE id = ?",
                     (new, name, recorded if recorded != new else None, row["id"]))
        conn.execute("UPDATE knowledge SET project_path = ?, project_name = ? WHERE session_id = ? AND project_path IS ?",
                     (new, name, row["id"], row["project_path"]))
        touched.update(p for p in (row["project_path"], new) if p)
        moved += 1
    conn.executemany("UPDATE project_kb SET knowledge_max_id = 0 WHERE project_path = ?", [(p,) for p in touched])
    conn.commit()
    return moved


def computers_of(conn, person_id: int) -> list[str]:
    """The computers that joined with one of this person's invites."""
    return [r[0] for r in conn.execute("SELECT DISTINCT machine_id FROM people_tokens WHERE person_id = ? AND "
                                       "kind = 'computer' AND machine_id IS NOT NULL", (person_id,))]


def purge_targets(conn, machine_ids: list[str], *, projects: list[str] | None = None,
                  keep: list[str] | None = None) -> list[dict]:
    """What `chronicle hub purge` would remove: sessions those computers sent, filed under `projects`, or (`keep`)
    under any project but those, sessions filed under no project included."""
    if not machine_ids or (projects is None) == (keep is None):
        return []
    marks = ", ".join("?" for _ in machine_ids)
    sql = f"SELECT id, project_path, project_name, title, source, transcript_path FROM sessions WHERE machine_id IN ({marks})"
    params: list = list(machine_ids)
    if projects is not None:
        sql += f" AND project_path IN ({', '.join('?' for _ in projects) or 'NULL'})"
        params += projects
    elif keep:
        sql += f" AND (project_path IS NULL OR project_path NOT IN ({', '.join('?' for _ in keep)}))"
        params += keep
    return [dict(r) for r in conn.execute(sql + " ORDER BY project_path, started_at", params)]


def purge(cfg: Config, conn, sessions: list[dict], *, by: str | None = None, person_id: int | None = None) -> dict:
    """Remove sessions other computers sent from this hub for good (purge_targets picks them): their rows, lessons,
    notes and received transcripts, the team store's copy, and the knowledge bases built from them. Each is forgotten
    (ingest.forget_session), so the computer that sent it can't send it again. Returns what was removed."""
    from .ingest import forget_session
    from .people import LOCAL, audit

    me = local_machine(cfg)["id"]
    ids = [x["id"] for x in sessions]
    if conn.execute(f"SELECT 1 FROM sessions WHERE machine_id = ? AND id IN ({', '.join('?' for _ in ids) or 'NULL'})",
                    (me, *ids)).fetchone():
        raise HubError("purge removes what other computers sent, not this hub's own sessions (`chronicle forget`)")
    store = _store(cfg)
    if store and ids:  # the team's record first: if it fails, nothing here changes and purge can run again
        _in_store(store.forget_sessions, ids)
    received = cfg.machines_dir
    for x in sessions:  # forget_session also removes its note in the Markdown vault
        sent_here = bool(x["transcript_path"]) and under(x["transcript_path"], str(received))
        forget_session(conn, cfg, x["id"], delete_transcript=sent_here)
    projects = sorted({x["project_path"] for x in sessions if x["project_path"]})
    emptied = [p for p in projects if not conn.execute("SELECT 1 FROM sessions WHERE project_path = ? LIMIT 1",
                                                       (p,)).fetchone()]
    for p in projects:  # built from the lessons just removed: the next sync builds it again from what is left
        conn.execute("DELETE FROM project_kb WHERE project_path = ?", (p,))
    for p in emptied:
        conn.execute("DELETE FROM glossary_usage WHERE project_path = ?", (p,))
        conn.execute("DELETE FROM suggestions WHERE project_path = ? AND status IN ('new', 'stale')", (p,))
    conn.execute("DELETE FROM suggestions WHERE knowledge_id IS NOT NULL AND status IN ('new', 'stale') AND "
                 "knowledge_id NOT IN (SELECT id FROM knowledge)")
    audit(conn, by or LOCAL, "purge", person_id, sessions=len(ids), projects=projects)
    conn.commit()
    return {"sessions": len(ids), "projects": projects, "emptied": emptied, "store": bool(store)}


def folders_report(conn, machine_id: str, folders: dict[str, str], repos: dict, remotes: dict[str, str]) -> dict:
    """Per folder: its project, this computer's sessions filed there, and the repositories inside it that their git
    remote files under another project (a remote the hub knows wins over a folder around it)."""
    out = {}
    for folder, project in folders.items():
        n = conn.execute("SELECT COUNT(*) FROM sessions WHERE machine_id = ? AND project_path = ? AND source != 'history'",
                         (machine_id, project)).fetchone()[0]
        other = sorted({(top, remotes[rem]) for top, rem in repos.values()
                        if under(top, folder) and remotes.get(rem) and remotes[rem] != project})
        out[folder] = {"project": project, "sessions": n, "overridden": [{"repo": t, "project": p} for t, p in other]}
    return out


# ------------------------------------------------------------------ client (spoke)
class HubClient:
    """Keep-alive HTTP(S) client for the hub's /api/hub endpoints."""

    def __init__(self, url: str, token: str, *, timeout: float = 120):
        parsed = urlparse(url if "://" in url else f"https://{url}")
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise HubError(f"not a hub address: {url}")
        self.url = f"{parsed.scheme}://{parsed.netloc}"
        self.https = parsed.scheme == "https"
        self.host = parsed.hostname
        self.port = parsed.port
        self.token = token
        self.timeout = timeout
        self.conn: http.client.HTTPConnection | None = None

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def _connection(self) -> http.client.HTTPConnection:
        if self.conn is None:
            cls = http.client.HTTPSConnection if self.https else http.client.HTTPConnection
            self.conn = cls(self.host, self.port, timeout=self.timeout)
        return self.conn

    def request(self, method: str, path: str, *, params: dict | None = None, body=None, length: int | None = None,
                headers: dict | None = None) -> dict:
        target = path + (f"?{urlencode(params)}" if params else "")
        hdrs = {"User-Agent": f"chronicle/{__version__}", **(headers or {})}
        if self.token:  # none when redeeming an invite: the code is the credential
            hdrs["Authorization"] = f"Bearer {self.token}"
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        if body is not None:
            hdrs["Content-Length"] = str(length if length is not None else len(body))
        for attempt in (1, 2):  # a kept-alive connection the hub closed meanwhile gets one fresh retry
            if hasattr(body, "seek"):
                body.seek(0)
            try:
                conn = self._connection()
                conn.request(method, target, body=body, headers=hdrs)
                resp = conn.getresponse()
                data = resp.read()
                break
            except (OSError, http.client.HTTPException) as exc:
                self.close()
                if attempt == 2:
                    raise HubUnreachable(f"can't reach the hub at {self.url}: {exc}") from exc
        try:
            payload = json.loads(data or b"{}")
        except ValueError:
            payload = {"error": data[:200].decode(errors="replace")}
        if resp.status == 401:
            raise HubUnauthorized("the hub did not accept this computer's token; join it again with a new invite "
                                  "(`chronicle hub invite` on the hub) or the command `chronicle hub enable` prints there")
        if resp.status >= 400:
            raise HubError(f"hub error {resp.status}: {payload.get('error') or payload}")
        return payload


@dataclass
class PushReport:
    sent: int = 0
    bytes: int = 0
    unchanged: int = 0
    skipped: int = 0
    analyses: int = 0
    errors: list[str] = field(default_factory=list)
    hub: str = ""
    seconds: float = 0.0
    kind: str = "files"  # or "knowledge": sessions this computer analyzed itself
    team: int | None = None  # teammates' lessons held here after the pull (a hub with a team store sends them)

    def summary(self) -> str:
        what = "session" if self.kind == "knowledge" else "file"
        verb = "shared" if self.kind == "knowledge" else "sent"
        parts = [f"{self.sent} {what}{'s' * (self.sent != 1)} {verb} ({self.bytes / 1e6:.1f} MB)", f"{self.unchanged} unchanged"]
        if self.skipped:  # sharing knowledge: sessions outside the hub's projects, or in excluded ones, stay here
            parts.append(f"{self.skipped} kept here" if self.kind == "knowledge" else f"{self.skipped} excluded")
        if self.analyses:
            parts.append(f"{self.analyses} earlier analyses handed over")
        if self.team is not None:
            parts.append(f"{self.team} team lesson{'s' * (self.team != 1)} here")
        if self.errors:
            parts.append(f"{len(self.errors)} errors")
        return f"to {self.hub}: " + ", ".join(parts) + f" in {self.seconds:.1f}s"


def _gzip_to_temp(path: Path) -> tuple[tempfile.SpooledTemporaryFile, int, str]:
    """(gzip of the file in a spooled temp file, raw size, raw sha256). Reads the file once, as it is now."""
    out = tempfile.SpooledTemporaryFile(max_size=16 << 20)
    h, size = hashlib.sha256(), 0
    with open(path, "rb") as fin, gzip.GzipFile(fileobj=out, mode="wb", compresslevel=6, mtime=0) as gz:
        while chunk := fin.read(1 << 20):
            h.update(chunk)
            size += len(chunk)
            gz.write(chunk)
    return out, size, h.hexdigest()


def _same(inv: list | None, size: int, mtime: float) -> bool:
    return bool(inv) and inv[0] == size and abs(float(inv[1]) - mtime) < 1.0


def hello_info(cfg: Config, roots: list[Root]) -> dict:
    me = local_machine(cfg)
    return {"protocol": PROTOCOL, "machine": me["id"], "name": me["name"], "platform": platform_label(),
            "version": __version__, "roots": [r.name for r in roots], "repos": spoke_repos(cfg, roots),
            "folders": cfg.hub_folders, "share": cfg.hub_share}


def _check_protocol(hello: dict) -> None:
    if int(hello.get("protocol", 0)) != PROTOCOL:
        raise HubError(f"the hub runs Chronicle {hello.get('version')}, which speaks a different protocol; "
                       "update both computers to the same version")


def handshake(cfg: Config, client: HubClient | None = None) -> dict:
    """Say hello without sending files: the hub's projects and what it made of this computer's folders."""
    token = read_token(cfg)
    if not cfg.hub_url or not token:
        raise HubError("this computer has not joined a hub (`chronicle hub join`)")
    client = client or HubClient(cfg.hub_url, token)
    try:
        hello = client.request("POST", "/api/hub/hello", body=hello_info(cfg, spoke_roots(cfg)))
    finally:
        client.close()
    _check_protocol(hello)
    _record_folders(cfg, hello)
    return hello


def redeem_invite(cfg: Config, url: str, code: str, client: HubClient | None = None) -> dict:
    """Trade an invite code for this computer's own token at the hub (`chronicle hub join --code`).

    Returns the hub's answer: {"token", "person", "hub"}. The caller keeps the token (write_token).
    """
    me = local_machine(cfg)
    client = client or HubClient(url, "")
    try:
        got = client.request("POST", "/api/hub/join", body={"code": code, "machine": me["id"], "name": me["name"],
                                                             "platform": platform_label(), "version": __version__})
    except HubUnauthorized:  # a hub that predates invites asks every caller for its shared token
        raise HubError(f"the hub at {client.url} doesn't take invite codes yet: update Chronicle there, or join with "
                       "the command its `chronicle hub enable` prints") from None
    finally:
        client.close()
    if not isinstance(got.get("token"), str) or not got["token"]:
        raise HubError(f"the hub at {client.url} sent no token")
    return got


def dashboard_signin(cfg: Config, client: HubClient | None = None) -> str:
    """A short-lived link that opens the hub's dashboard as the person this computer joined as (no password)."""
    token = read_token(cfg)
    if not cfg.hub_url or not token:
        raise HubError("this computer has not joined a hub (`chronicle hub join`)")
    client = client or HubClient(cfg.hub_url, token)
    try:
        got = client.request("POST", "/api/hub/signin", body={"machine": local_machine(cfg)["id"]})
    finally:
        client.close()
    code = got.get("code")
    if not isinstance(code, str) or not code:
        raise HubError("the hub sent no sign-in code")
    return f"{cfg.hub_url}/signin?code={quote(code, safe='-_')}"


def push(cfg: Config, *, progress=None, client: HubClient | None = None) -> PushReport:
    """Send the hub every session file it lacks (or has an older copy of); with [hub] share = "knowledge", what
    this computer learned instead (push_knowledge)."""
    if cfg.shares_knowledge:
        return push_knowledge(cfg, progress=progress, client=client)
    token = read_token(cfg)
    if not cfg.hub_url or not token:
        raise HubError("this computer has not joined a hub (`chronicle hub join`)")
    t0 = time.monotonic()
    report = PushReport(hub=cfg.hub_url)
    roots = spoke_roots(cfg)
    client = client or HubClient(cfg.hub_url, token)
    me = local_machine(cfg)
    try:
        hello = client.request("POST", "/api/hub/hello", body=hello_info(cfg, roots))
        _check_protocol(hello)
        _record_folders(cfg, hello)
        inventory = hello.get("inventory") or {}
        if hello.get("wants_analyses"):
            blob, n = export_analyses(cfg)
            client.request("POST", "/api/hub/analyses", params={"machine": me["id"]}, body=blob,
                           headers={"Content-Type": "application/gzip"})
            report.analyses = n
        exclusions = _Exclusions(cfg)
        todo = []
        for root in roots:
            have = inventory.get(root.name) or {}
            for rel, path in root_files(root):
                try:
                    st = path.stat()
                except OSError:
                    continue
                if _same(have.get(rel), st.st_size, st.st_mtime):
                    report.unchanged += 1
                elif exclusions.excluded(root, rel, path):
                    report.skipped += 1
                else:
                    todo.append((root, rel, path, st))
        for i, (root, rel, path, st) in enumerate(todo, 1):
            if progress:
                progress(f"sending {i} of {len(todo)}: {rel}")
            try:
                body, size, sha = _gzip_to_temp(path)
            except OSError as exc:
                report.errors.append(f"{path}: {exc}")
                continue
            try:
                body.seek(0, os.SEEK_END)
                length = body.tell()
                client.request("POST", "/api/hub/file", body=body, length=length, headers={"Content-Type": "application/gzip"},
                               params={"machine": me["id"], "root": root.name, "path": rel, "size": size,
                                       "mtime": repr(st.st_mtime), "sha256": sha})
                report.sent += 1
                report.bytes += size
            except HubUnreachable:
                raise
            except HubError as exc:
                report.errors.append(f"{rel}: {exc}")
            finally:
                body.close()
        if report.sent or report.analyses:
            client.request("POST", "/api/hub/done", body={"machine": me["id"]})
    finally:
        client.close()
    report.seconds = time.monotonic() - t0
    _record_push(cfg, report)
    return report


def _shared_records(cfg: Config, have: dict, *, scope: list[str] | None = None, remotes: dict | None = None,
                    projects_only: bool = False, conn=None, where: str = "",
                    params: tuple = ()) -> tuple[list[dict], int, int]:
    """(records the hub lacks or has an older analysis of, unchanged, excluded) for push_knowledge.

    `scope`: the hub projects this computer's person is limited to (hello says so); then only sessions the hub files
    under them are sent: in a folder added to one of them, or in a repository whose remote the hub files there.
    `projects_only` ([hub] all_folders = false): the same for any of the hub's projects, so a folder nobody added and
    a repository the hub doesn't know stay here.
    `conn`/`where`: the hub's own sessions in projects set up there (share_own)."""
    from .db import connect

    out: list[dict] = []
    unchanged = excluded = 0
    own = conn is None
    if own and not cfg.db_path.exists():
        return out, 0, 0
    conn = conn or connect(cfg.db_path, readonly=True)
    found: dict[str, str | None] = {}
    try:
        cols = ", ".join(("id", "project_path", "machine_path") + SHARED_COLS + ANALYSIS_COLS)  # never a prompt-made title
        marks = ", ".join("?" for _ in SHARED_AGENTS)
        rows = conn.execute(f"SELECT {cols} FROM sessions WHERE analysis_status = 'done' "
                            f"AND source NOT IN ('history', 'remote') AND agent IN ({marks}){where}",
                            (*SHARED_AGENTS, *params)).fetchall()
        for r in rows:
            rec = dict(r)
            ran = rec.pop("machine_path") or rec["project_path"]  # where it ran: a set-up project may hold it
            if cfg.is_excluded(rec["project_path"]):
                excluded += 1
                continue
            limited = scope is not None or projects_only
            if not limited and have.get(rec["id"]) == rec["analyzed_at"]:
                unchanged += 1  # asked git nothing: it runs once per folder, only for what goes
                continue
            if ran and ran not in found:
                info = git_info(ran)
                found[ran] = info[1] if info else None
            rec["remote"] = found.get(ran) if ran else None
            if limited:
                goes = destination(cfg, rec["project_path"], rec["remote"], remotes or {})
                if goes is None or (scope is not None and goes not in scope):
                    excluded += 1  # not one of the hub's projects, or not one this person shares: it stays here
                    continue
            if have.get(rec["id"]) == rec["analyzed_at"]:
                unchanged += 1
                continue
            rec["language"] = cfg.analysis.language  # what its summary and lessons are written in
            # lessons about the project only: ones about the person (global, preferences) stay on this computer
            rec["knowledge"] = [dict(k) for k in conn.execute(
                f"SELECT {', '.join(KNOWLEDGE_COLS)} FROM knowledge WHERE session_id = ? AND source = 'analysis' "
                "AND scope = 'project' AND kind != 'preference' AND status != 'dismissed'", (rec["id"],)).fetchall()]
            out.append(rec)
    finally:
        if own:
            conn.close()
    return out, unchanged, excluded


def destination(cfg: Config, path: str | None, remote: str | None, remotes: dict) -> str | None:
    """The hub project a session of this computer is filed under, as far as this computer can tell: the project the
    hub files its repository's remote under, else the project of the folder it was added to (the longest one)."""
    if remote and remotes.get(remote):
        return remotes[remote]
    folder = max((f for f in cfg.hub_folders if under(path, f)), key=len, default=None)
    return cfg.hub_folders[folder] if folder else None


def share_own(cfg: Config, conn, store) -> int:
    """On a hub with a team store: send the store this computer's own analyzed sessions in projects set up here
    (add_project), the same details and project lessons a member's computer shares, so teammates get the hub
    owner's lessons too. Only what changed since the last time; returns how many sessions went."""
    declared = declared_projects(conn)
    if not declared:
        return 0
    me = local_machine(cfg)
    have = _in_store(store.shared, me["id"])
    marks = ", ".join("?" for _ in declared)
    records, _, _ = _shared_records(cfg, have, conn=conn, where=f" AND machine_id = ? AND project_path IN ({marks})",
                                    params=(me["id"], *declared))
    if not records:
        return 0
    from .ingest import project_name_for
    from .team_store import payload

    _in_store(store.computer_seen, me["id"], me["name"], platform_label(), __version__)
    for i in range(0, len(records), SHARE_BATCH):
        _in_store(store.put_sessions, me["id"], [
            payload(rec, project=rec["project_path"], project_name=project_name_for(rec["project_path"]),
                    remote=rec["remote"], title=rec.get("llm_title"), details_cols=SHARED_COLS)
            for rec in records[i:i + SHARE_BATCH]])
    return len(records)


def push_knowledge(cfg: Config, *, progress=None, client: HubClient | None = None) -> PushReport:
    """[hub] share = "knowledge": send the hub each analyzed session's details, analysis and project lessons that it
    lacks or has an older analysis of. Transcripts never leave this computer."""
    token = read_token(cfg)
    if not cfg.hub_url or not token:
        raise HubError("this computer has not joined a hub (`chronicle hub join`)")
    t0 = time.monotonic()
    report = PushReport(hub=cfg.hub_url, kind="knowledge")
    client = client or HubClient(cfg.hub_url, token)
    me = local_machine(cfg)
    try:
        info = hello_info(cfg, spoke_roots(cfg))
        hello = client.request("POST", "/api/hub/hello", body=info)
        _check_protocol(hello)
        _record_folders(cfg, hello)
        have = hello.get("knowledge")
        if not isinstance(have, dict):
            raise HubError(f"the hub runs Chronicle {hello.get('version')}, which can't take knowledge only; update it")
        scope = hello.get("scope") if isinstance(hello.get("scope"), list) else None  # the hub limits this person
        records, report.unchanged, report.skipped = _shared_records(cfg, have, scope=scope,
                                                                    remotes=hello.get("remotes") or {},
                                                                    projects_only=not cfg.hub_all_folders)
        for i in range(0, len(records), SHARE_BATCH):
            batch = records[i:i + SHARE_BATCH]
            if progress:
                progress(f"sharing {i + len(batch)} of {len(records)} sessions")
            body = gzip.compress(json.dumps({"version": 1, "sessions": batch}).encode(), mtime=0)
            try:
                client.request("POST", "/api/hub/sessions", params={"machine": me["id"]}, body=body,
                               headers={"Content-Type": "application/gzip"})
            except HubUnreachable:
                raise
            except HubError as exc:
                report.errors.append(str(exc))
                continue
            report.sent += len(batch)
            report.bytes += len(body)
        if report.sent:
            client.request("POST", "/api/hub/done", body={"machine": me["id"]})
        if hello.get("team"):  # the hub keeps a team store: bring back what teammates learned in these projects
            try:
                report.team = pull_team_lessons(cfg, client, info["repos"])
            except HubUnreachable:
                raise
            except HubError as exc:
                report.errors.append(f"team lessons: {exc}")
    finally:
        client.close()
    report.seconds = time.monotonic() - t0
    _record_push(cfg, report)
    return report


def pull_team_lessons(cfg: Config, client: HubClient, repos: dict) -> int:
    """Ask the hub for teammates' lessons in this computer's projects and keep them here, read-only (source 'team').
    Returns how many this computer holds. Nothing changes when the hub's answer is the one it already has."""
    from .db import connect

    state = last_team(cfg) or {}
    if state.get("version") and cfg.db_path.exists():  # "unchanged" only counts if the lessons are still here
        conn = connect(cfg.db_path, readonly=True)
        try:
            held = conn.execute("SELECT COUNT(*) FROM knowledge WHERE source = ?", (TEAM_SOURCE,)).fetchone()[0]
        finally:
            conn.close()
        if held != state.get("lessons"):
            state = {}
    remotes = sorted({v[1] for v in repos.values() if isinstance(v, list) and len(v) == 2 and v[1]})
    data = client.request("POST", "/api/hub/lessons", body={
        "machine": local_machine(cfg)["id"], "remotes": remotes, "projects": sorted(set(cfg.hub_folders.values())),
        "version": state.get("version")})
    if not data.get("team"):
        return 0
    if data.get("unchanged"):
        held = int(state.get("lessons") or 0)
    else:
        held = apply_team_lessons(cfg, data, repos)
        state = {"version": data.get("version"), "lessons": held, "hub": data.get("hub")}
    try:  # "at" is when this computer last asked, whether or not the answer changed
        (cfg.home / TEAM_FILE).write_text(json.dumps({**state, "at": utcnow_iso()}))
    except OSError:
        pass
    return held


def team_from(row) -> list[str]:
    """The computers whose sessions stated a teammate's lesson (knowledge.source_ref of a 'team' item)."""
    try:
        ref = json.loads(row["source_ref"] or "{}")
    except (ValueError, TypeError, KeyError, IndexError):
        return []
    return [str(c) for c in ref.get("from") or []] if isinstance(ref, dict) else []


def last_team(cfg: Config) -> dict | None:
    try:
        return json.loads((cfg.home / TEAM_FILE).read_text())
    except (OSError, ValueError):
        return None


def apply_team_lessons(cfg: Config, data: dict, repos: dict) -> int:
    """Keep the hub's lessons in this computer's own database, each filed under the folder here that holds its place
    (a repository, or a hub project without one): where this computer's own sessions there were filed, else the clone
    of that repository with the most sessions, else a folder added to that hub project. Lessons with no folder here
    are skipped. A lesson the hub no longer sends is removed; one dismissed here stays dismissed. Returns how many are
    held."""
    from . import ladder
    from .db import connect
    from .util import dumps

    places = data.get("places") if isinstance(data.get("places"), dict) else {}
    clones: dict[str, list[str]] = {}
    for cwd, v in repos.items():
        if isinstance(v, list) and len(v) == 2 and v[1]:
            clones.setdefault(v[1], []).append(cwd)
    added = {}
    for folder, project in sorted(cfg.hub_folders.items()):
        added.setdefault(project, folder)
    conn = connect(cfg.db_path)
    try:
        def name_of(path: str) -> str:
            r = conn.execute("SELECT project_name FROM sessions WHERE project_path = ? AND project_name IS NOT NULL "
                             "LIMIT 1", (path,)).fetchone()
            return r[0] if r else (Path(path).name or path)

        def here(at: str, project: str | None) -> tuple[str, str] | None:
            info = places.get(at) if isinstance(places.get(at), dict) else {}
            mine = info.get("mine")
            if isinstance(mine, str):
                r = conn.execute("SELECT project_path, project_name FROM sessions WHERE id = ?", (mine,)).fetchone()
                if r and r[0]:
                    return r[0], r[1] or name_of(r[0])
            found = sorted(clones.get(info.get("remote"), [])) if isinstance(info.get("remote"), str) else []
            if found:
                marks = ",".join("?" * len(found))
                used = dict(conn.execute(f"SELECT project_path, COUNT(*) FROM sessions WHERE project_path IN ({marks}) "
                                         "GROUP BY project_path", found).fetchall())
                best = max(found, key=lambda c: used.get(c, 0))
                return best, name_of(best)
            for p in (info.get("project"), project):
                if isinstance(p, str) and p in added:
                    return added[p], name_of(added[p])
            return None

        where: dict[tuple, tuple[str, str] | None] = {}
        held: set[str] = set()
        changed: list[int] = []
        now = utcnow_iso()
        for k in data.get("lessons") or []:
            if not isinstance(k, dict) or not isinstance(k.get("id"), int) or not k.get("title") or not k.get("kind"):
                continue
            spot = (str(k.get("place") or ""), k.get("project") if isinstance(k.get("project"), str) else None)
            if spot not in where:
                where[spot] = here(*spot)
            if not where[spot]:
                continue
            path, name = where[spot]
            fp = f"{TEAM_SOURCE}:{k['id']}"
            held.add(fp)
            sessions = [str(s) for s in k.get("session_ids") or [] if isinstance(s, str)][:ladder.MAX_CONFIRMATIONS]
            ref = dumps({"lesson": k["id"], "hub": data.get("hub"), "from": [str(c) for c in k.get("computers") or []][:10],
                         "sessions": int(k.get("sessions") or len(sessions)), "language": k.get("language")})
            tags = k.get("tags") if isinstance(k.get("tags"), list) else None
            values = {"project_path": path, "project_name": name, "kind": str(k["kind"])[:40], "title": str(k["title"]),
                      "body": k.get("body") if isinstance(k.get("body"), str) else None,
                      "tags_json": dumps(tags) if tags else None, "scope": "project", "source": TEAM_SOURCE,
                      "agent": None, "source_ref": ref, "confirmed_json": dumps(sessions) if sessions else None,
                      "created_at": k.get("created_at") or now, "updated_at": k.get("updated_at") or now}
            have = conn.execute("SELECT id FROM knowledge WHERE fingerprint = ?", (fp,)).fetchone()
            if have:  # its status and pin are this computer's own choice: kept
                conn.execute("UPDATE knowledge SET " + ", ".join(f"{c} = ?" for c in values) + " WHERE id = ?",
                             [*values.values(), have[0]])
                changed.append(have[0])
            else:
                cols = [*values, "fingerprint", "session_id"]
                cur = conn.execute(f"INSERT INTO knowledge({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                                   [*values.values(), fp, None])
                changed.append(cur.lastrowid)
        gone = [r[0] for r in conn.execute("SELECT id, fingerprint FROM knowledge WHERE source = ?", (TEAM_SOURCE,))
                if r[1] not in held]
        if gone:
            conn.execute(f"DELETE FROM knowledge WHERE id IN ({','.join('?' * len(gone))})", gone)
        ladder.refresh(conn, changed)
        conn.commit()
        return len(held)
    finally:
        conn.close()


def _record_push(cfg: Config, report: PushReport) -> None:
    """The spoke's own note of its last push, for `chronicle hub status` and its dashboard."""
    try:
        (cfg.home / "last-push.json").write_text(json.dumps({"at": utcnow_iso(), "summary": report.summary(),
                                                              "errors": report.errors[:5]}))
    except OSError:
        pass


def last_push(cfg: Config) -> dict | None:
    try:
        return json.loads((cfg.home / "last-push.json").read_text())
    except (OSError, ValueError):
        return None


def _record_folders(cfg: Config, hello: dict) -> None:
    """The spoke's note of what the hub made of its folders, for `chronicle hub folders` (an older hub sends none)."""
    if not isinstance(hello.get("folders"), dict):
        return
    try:
        (cfg.home / FOLDERS_FILE).write_text(json.dumps({"at": utcnow_iso(), "folders": hello["folders"],
                                                          "moved": int(hello.get("moved") or 0)}))
    except OSError:
        pass


def last_folders(cfg: Config) -> dict | None:
    try:
        return json.loads((cfg.home / FOLDERS_FILE).read_text())
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------ hub side
def machine_dir(cfg: Config, machine_id: str) -> Path:
    return cfg.machines_dir / machine_id


def safe_rel(rel: str) -> PurePosixPath | None:
    """A relative path inside a root, or None for anything that could escape it."""
    if not rel or "\\" in rel or "\x00" in rel or rel.startswith("/"):
        return None
    p = PurePosixPath(rel)
    if any(part in ("", ".", "..") or part.startswith(".") for part in p.parts):
        return None
    return p


def check_machine(cfg: Config, machine_id: str) -> str:
    if not MACHINE_RE.match(machine_id or ""):
        raise HubError("bad machine id")
    if machine_id == local_machine(cfg)["id"]:
        raise HubError("that is this hub's own id: the spoke's Chronicle folder was copied from the hub; delete "
                       "machine.json on the spoke and join again")
    return machine_id


def inventory(cfg: Config, machine_id: str) -> dict[str, dict[str, list]]:
    base = machine_dir(cfg, machine_id)
    out: dict[str, dict[str, list]] = {}
    if not base.is_dir():
        return out
    for root in base.iterdir():
        if not root.is_dir() or not ROOT_RE.match(root.name):
            continue
        files = out.setdefault(root.name, {})
        for rel, path in _walk(root, PurePosixPath(".")):
            if ".tmp-" in path.name:
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            files[rel] = [st.st_size, st.st_mtime]
    return out


def _store(cfg: Config):
    """The hub's team store (team_store.py) when `[hub] store` names one, else None; its errors as HubError."""
    from .team_store import TeamStoreError, get

    try:
        return get(cfg)
    except TeamStoreError as exc:
        raise HubError(str(exc)) from None


def _in_store(call, *args):
    from .team_store import TeamStoreError

    try:
        return call(*args)
    except TeamStoreError as exc:
        raise HubError(str(exc)) from None


def limited_error(person: dict) -> HubError:
    return HubError(f"{person['name']} sees only some projects on this hub, so this computer may share knowledge only "
                    "(summaries and project lessons, not transcripts): run `chronicle config set hub.share knowledge`, "
                    "then `chronicle push`")


def transcripts_refused(cfg: Config, person: dict | None) -> HubError | None:
    """Why this hub won't take a computer's transcripts, or None if it will: the hub takes knowledge only
    (`[hub] accept`), or the computer's person sees only some projects (people.py)."""
    from .people import projects_of

    if cfg.hub_accept == "knowledge":
        return HubError("this hub takes knowledge only (summaries and project lessons, not transcripts), so this "
                        "computer may share knowledge only: run `chronicle config set hub.share knowledge`, then "
                        "`chronicle push`")
    if projects_of(person) is not None:
        return limited_error(person)
    return None


def hello(cfg: Config, conn, body: dict, person: dict | None = None) -> dict:
    """A computer says who it is and which folders it added to projects here; the hub answers with what it has of
    that computer's, and the projects it may add folders to. A person limited to projects (people.py) hears only of
    theirs. They, and every computer of a hub that takes knowledge only, must share knowledge (no transcripts)."""
    from .people import projects_of

    machine_id = check_machine(cfg, str(body.get("machine") or ""))
    if int(body.get("protocol", 0)) != PROTOCOL:
        return {"protocol": PROTOCOL, "version": __version__}
    scope = projects_of(person)
    if body.get("share") != "knowledge" and (refused := transcripts_refused(cfg, person)):
        raise refused
    # the team store holds what computers share as knowledge; one that sends transcripts never waits on it
    store = _store(cfg) if body.get("share") == "knowledge" else None
    if store:
        _in_store(store.computer_seen, machine_id, str(body.get("name") or "")[:120] or None,
                  str(body.get("platform") or "")[:40] or None, str(body.get("version") or "")[:40] or None)
    repos = body.get("repos") if isinstance(body.get("repos"), dict) else {}
    repos = {str(k): [str(v[0]), str(v[1])] for k, v in repos.items() if isinstance(v, list) and len(v) == 2}
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO machines(id, name, platform, version, role, first_seen, last_seen, repos_json) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET name = excluded.name, platform = excluded.platform, version = excluded.version, "
        "role = excluded.role, last_seen = excluded.last_seen, repos_json = excluded.repos_json",
        (machine_id, str(body.get("name") or "")[:120] or None, str(body.get("platform") or "")[:40] or None,
         str(body.get("version") or "")[:40] or None, "spoke", now, now, json.dumps(repos)),
    )
    conn.commit()
    from .db import kv_get, kv_set

    folders, moved, refiled = folders_of(conn, machine_id), 0, False
    if "folders" in body:  # an older spoke doesn't send them: keep what it had
        sent = clean_folders(body.get("folders"))
        if scope is not None:  # a folder can go only to a project this person sees
            sent = {f: proj for f, proj in sent.items() if proj in scope}
        if sent != folders:
            kv_set(conn, FOLDERS_KV + machine_id, json.dumps(sent))
            conn.commit()
            moved = refile(cfg, conn, machine_id, set(folders) | set(sent))
            folders, refiled = sent, True
    remotes = {rem: proj for rem, proj in ProjectResolver(cfg, conn).project_remotes().items()
               if scope is None or proj in scope}
    report = folders_report(conn, machine_id, folders, repos, remotes)
    share = "knowledge" if body.get("share") == "knowledge" else "everything"
    kv_set(conn, SHARE_KV + machine_id, share)
    conn.commit()  # local_remotes caches what git said
    me = local_machine(cfg)
    if store:  # the store is the team's record: what it lacks is sent again, and folders that changed refile it all
        shared = {} if refiled else _in_store(store.shared, machine_id)
    else:
        shared = {r[0]: r[1] for r in conn.execute(
            "SELECT id, analyzed_at FROM sessions WHERE machine_id = ? AND source = 'remote'", (machine_id,))}
    return {"protocol": PROTOCOL, "version": __version__, "hub": me["name"],
            "inventory": inventory(cfg, machine_id), "wants_analyses": not kv_get(conn, f"hub-analyses:{machine_id}"),
            "projects": hub_projects(conn, only=scope), "remotes": remotes, "folders": report, "moved": moved,
            "knowledge": shared, "team": bool(store), "scope": scope}


def join_with_code(cfg: Config, conn, body: dict) -> dict:
    """POST /api/hub/join: a computer redeems an invite for a push token of its own. The code is the credential, so
    this is called without a token; the computer is recorded only once its code was good."""
    from . import people

    if not read_token(cfg) or cfg.is_spoke:
        raise HubError("this computer is not a hub")
    machine_id = check_machine(cfg, str(body.get("machine") or ""))
    code, name = str(body.get("code") or ""), str(body.get("name") or "")[:120] or None
    # a read-only person's computer could never send: refuse before the code is used, so it still opens a browser
    invited = people.peek_invite(conn, code)
    if invited and invited["role"] == "readonly":
        raise HubError(f"{invited['name']} is read-only on this hub: read-only people see its dashboard but don't send "
                       "to it. Open the invite link in a browser instead; the code still works there.")
    try:
        person, token = people.join_computer(conn, code, machine_id, name)
    except people.PeopleError as exc:
        raise HubError(str(exc)) from None
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO machines(id, name, platform, version, role, first_seen, last_seen, person_id) VALUES (?,?,?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET person_id = excluded.person_id",
        (machine_id, name, str(body.get("platform") or "")[:40] or None, str(body.get("version") or "")[:40] or None,
         "spoke", now, now, person["id"]),
    )
    conn.commit()
    scope = people.projects_of(person)
    return {"token": token, "person": people.public(person), "hub": local_machine(cfg)["name"],
            "projects": hub_projects(conn, only=scope) if scope is not None else None,
            "share": "knowledge" if scope is not None or cfg.hub_accept == "knowledge" else None}


def signin_code_for(cfg: Config, conn, person: dict | None) -> dict:
    """POST /api/hub/signin: a short-lived code that opens the dashboard as the person whose computer asks. A computer
    sending with the shared token is nobody in particular, so it can't."""
    from . import people

    if person is None:
        raise HubError("join with an invite to sign in")
    return {"code": people.signin_code(conn, person)}


def receive_file(cfg: Config, conn, params: dict, rfile, length: int) -> dict:
    """Store one gzip-compressed file a spoke sent, verified against its size and sha256, atomically."""
    from .ingest import forgotten_ids

    machine_id = check_machine(cfg, params.get("machine", ""))
    root = params.get("root", "")
    rel = safe_rel(params.get("path", ""))
    try:
        size, mtime, sha = int(params.get("size", "")), float(params.get("mtime", "")), params.get("sha256", "")
    except ValueError:
        raise HubError("bad size or mtime") from None
    if not ROOT_RE.match(root) or rel is None or not re.fullmatch(r"[0-9a-f]{64}", sha) or not 0 <= size <= MAX_FILE_BYTES:
        raise HubError("bad file parameters")
    if any(sid in rel.name for sid in forgotten_ids(conn)):
        _drain(rfile, length)
        return {"ok": True, "skipped": "forgotten"}  # `chronicle forget` on the hub keeps it out for good
    target = machine_dir(cfg, machine_id) / root / Path(*rel.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    h, raw = hashlib.sha256(), 0
    d = zlib.decompressobj(wbits=31)
    left = length
    try:
        with open(tmp, "wb") as out:
            while left > 0:
                chunk = rfile.read(min(left, 1 << 20))
                if not chunk:
                    raise HubError("upload cut off")
                left -= len(chunk)
                data = d.decompress(chunk)
                raw += len(data)
                if raw > size:
                    raise HubError("file larger than announced")
                h.update(data)
                out.write(data)
            tail = d.flush()
            raw += len(tail)
            h.update(tail)
            out.write(tail)
        if raw != size or h.hexdigest() != sha:
            raise HubError("file damaged in transit (size or checksum mismatch)")
        old = target.stat().st_size if target.exists() else None
        os.replace(tmp, target)
        os.utime(target, (mtime, mtime))
    except zlib.error as exc:
        tmp.unlink(missing_ok=True)
        _drain(rfile, left)
        raise HubError(f"not gzip data: {exc}") from None
    except BaseException:
        tmp.unlink(missing_ok=True)
        _drain(rfile, left)
        raise
    conn.execute("UPDATE machines SET last_push = ?, files = files + ?, bytes = bytes + ? WHERE id = ?",
                 (utcnow_iso(), 0 if old is not None else 1, size - (old or 0), machine_id))
    conn.commit()
    return {"ok": True}


def _drain(rfile, left: int) -> None:
    while left > 0:
        chunk = rfile.read(min(left, 1 << 20))
        if not chunk:
            return
        left -= len(chunk)


def _cell(value):
    """A value another computer sent, as SQLite can store it."""
    if value is None or isinstance(value, (str, int, float)):
        return value
    return json.dumps(value) if isinstance(value, (dict, list)) else str(value)


def receive_sessions(cfg: Config, conn, params: dict, rfile, length: int, person: dict | None = None) -> dict:
    """Sessions another computer analyzed itself ([hub] share = "knowledge"): their details, analysis and project
    lessons, without a transcript. Stored with source 'remote', filed like any session of that computer, and never
    analyzed here. A session the hub has the transcript of keeps its own record."""
    from .ingest import best_title, project_name_for

    machine_id = check_machine(cfg, params.get("machine", ""))
    if length > 64 << 20:
        _drain(rfile, length)
        raise HubError("sessions too large")
    try:
        data = json.loads(gzip.decompress(rfile.read(length)))
    except (OSError, ValueError, EOFError) as exc:
        raise HubError(f"bad sessions: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        raise HubError("bad sessions")
    from .people import projects_of

    from .ingest import forgotten_ids

    scope = projects_of(person)
    forgotten = forgotten_ids(conn)  # forgotten or purged here: never taken again
    r = ProjectResolver(cfg, conn)
    now = utcnow_iso()
    stored = kept = refused = 0
    accepted = []
    for rec in data["sessions"][:SHARE_BATCH * 2]:
        sid = str(rec.get("id") or "") if isinstance(rec, dict) else ""
        if not SESSION_ID_RE.match(sid) or rec.get("agent") not in SHARED_AGENTS:
            continue
        if sid in forgotten:
            refused += 1
            continue
        have = conn.execute("SELECT source FROM sessions WHERE id = ?", (sid,)).fetchone()
        if have and have["source"] != "remote":
            kept += 1  # its transcript is here: the hub's own record wins
            continue
        recorded = str(rec.get("project_path") or "") or None
        remote = rec.get("remote") if isinstance(rec.get("remote"), str) else None
        project = r.resolve(machine_id, recorded, remote)
        if scope is not None and project not in scope:
            refused += 1  # a person limited to projects: only what belongs to theirs is kept
            continue
        name = project_name_for(project)
        row = {c: _cell(rec.get(c)) for c in SHARED_COLS + ANALYSIS_COLS}
        row.update(id=sid, source="remote", machine_id=machine_id, project_path=project, project_name=name,
                   machine_path=recorded if recorded != project else None, source_present=1, ingested_at=now,
                   analysis_status="done", title=best_title({"llm_title": rec.get("llm_title")}),
                   ended_flag=1 if rec.get("ended_flag") else 0)
        # lessons about the project only: one about the person should not have been sent, and is not kept
        lessons = [k for k in rec.get("knowledge") or [] if isinstance(k, dict) and k.get("title") and k.get("kind")
                   and k.get("scope") == "project" and k.get("kind") != "preference"]
        accepted.append((sid, {**rec, "knowledge": lessons}, row, remote))
    store = _store(cfg)
    if store and accepted:  # the team's record first: if it fails, nothing is kept and the computer sends it again
        from .team_store import payload

        _in_store(store.put_sessions, machine_id, [
            payload(rec, project=row["project_path"], project_name=row["project_name"], remote=remote,
                    title=row["title"], details_cols=SHARED_COLS) for _, rec, row, remote in accepted])
    for sid, rec, row, _ in accepted:
        cols = list(row)
        try:
            conn.execute(f"INSERT INTO sessions({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) "
                         "ON CONFLICT(id) DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in cols if c != "id"),
                         [row[c] for c in cols])
        except sqlite3.Error as exc:  # one bad record must not lose the rest of the batch
            log.warning("shared session %s from %s not stored: %s", sid, machine_id, exc)
            continue
        project, name = row["project_path"], row["project_name"]
        conn.execute("DELETE FROM knowledge WHERE session_id = ? AND source = 'analysis'", (sid,))
        for k in rec["knowledge"]:
            krow = {c: _cell(k.get(c)) for c in KNOWLEDGE_COLS}
            krow.update(session_id=sid, project_path=project, project_name=name, source="analysis")
            conn.execute(f"INSERT OR IGNORE INTO knowledge({', '.join(krow)}) VALUES ({', '.join('?' for _ in krow)})",
                         list(krow.values()))
        stored += 1
    if stored:
        conn.execute("UPDATE machines SET last_push = ? WHERE id = ?", (now, machine_id))
    conn.commit()
    return {"ok": True, "stored": stored, "kept": kept, "refused": refused}


def team_lessons(cfg: Config, body: dict, person: dict | None = None, conn=None) -> dict:
    """What teammates learned in the projects a computer works on, from the team store (pull_team_lessons asks).
    {"team": False} when this hub keeps no team store; {"unchanged": True} when the computer already has this answer.
    A person limited to projects gets lessons from those projects only, whatever the computer names."""
    from .people import projects_of

    machine_id = check_machine(cfg, str(body.get("machine") or ""))
    store = _store(cfg)
    if not store:
        return {"team": False}
    if conn is not None:  # the hub owner's own lessons in projects set up here, before teammates ask for them
        try:
            share_own(cfg, conn, store)
        except HubError as exc:
            log.warning("team store: this hub's own sessions not shared: %s", exc)
    remotes = [normalize_remote(x) or x for x in body.get("remotes") or [] if isinstance(x, str) and len(x) <= 300][:500]
    projects = [x for x in body.get("projects") or [] if isinstance(x, str) and x.startswith("/") and len(x) <= 1024]
    within = projects_of(person)
    data = _in_store(lambda: store.lessons_for(machine_id, remotes, projects[:MAX_FOLDERS], within=within))
    version = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:32]
    if body.get("version") == version:
        return {"team": True, "version": version, "unchanged": True}
    return {"team": True, "version": version, "hub": local_machine(cfg)["name"], **data}


def receive_analyses(cfg: Config, conn, params: dict, rfile, length: int) -> dict:
    from .db import kv_set

    machine_id = check_machine(cfg, params.get("machine", ""))
    if length > 512 << 20:
        _drain(rfile, length)
        raise HubError("analyses too large")
    blob = rfile.read(length)
    try:
        data = json.loads(gzip.decompress(blob))
    except (OSError, ValueError, EOFError) as exc:
        raise HubError(f"bad analyses: {exc}") from None
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), list):
        raise HubError("bad analyses")
    dest = machine_dir(cfg, machine_id) / ANALYSES_FILE
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, dest)
    kv_set(conn, f"hub-analyses:{machine_id}", utcnow_iso())
    conn.commit()
    return {"ok": True, "sessions": len(data["sessions"])}


class IngestTrigger:
    """Runs `chronicle sync --work` after a push, one at a time; a push during a run queues exactly one more."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.Lock()
        self.running = False
        self.again = False

    def command(self) -> list[str]:
        from .hooks import self_command

        return [*self_command(), "sync", "--work", "--quiet"]

    def request(self) -> None:
        with self.lock:
            if self.running:
                self.again = True
                return
            self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        from .hooks import INTERNAL_ENV

        while True:
            with self.lock:
                self.again = False
            log_path = self.cfg.logs_dir / "hub.log"
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(log_path, "a") as fh:
                    subprocess.run(self.command(), stdin=subprocess.DEVNULL, stdout=fh, stderr=fh, start_new_session=True,
                                   env={k: v for k, v in os.environ.items() if k != INTERNAL_ENV})
            except OSError as exc:
                log.warning("hub ingest failed to start: %s", exc)
            with self.lock:
                if not self.again:
                    self.running = False
                    return


# ------------------------------------------------------------------ analyses a spoke already did
def export_analyses(cfg: Config) -> tuple[bytes, int]:
    """gzip JSON of this computer's finished analyses and the knowledge they produced (not memory notes)."""
    from .db import connect

    sessions: list[dict] = []
    if cfg.db_path.exists():
        conn = connect(cfg.db_path, readonly=True)
        try:
            cols = ", ".join(("id",) + ANALYSIS_COLS)
            for r in conn.execute(f"SELECT {cols} FROM sessions WHERE analysis_status = 'done'").fetchall():
                rec = dict(r)
                rec["knowledge"] = [dict(k) for k in conn.execute(
                    f"SELECT {', '.join(KNOWLEDGE_COLS)} FROM knowledge WHERE session_id = ? AND source = 'analysis'",
                    (rec["id"],)).fetchall()]
                sessions.append(rec)
        finally:
            conn.close()
    blob = gzip.compress(json.dumps({"version": 1, "sessions": sessions}).encode(), mtime=0)
    return blob, len(sessions)


def apply_analyses(cfg: Config, conn) -> int:
    """Carry over analyses spokes sent for sessions the hub has now ingested; returns how many were applied."""
    from .ingest import best_title

    applied = 0
    if not cfg.machines_dir.is_dir():
        return 0
    for path in cfg.machines_dir.glob(f"*/{ANALYSES_FILE}"):
        try:
            data = json.loads(gzip.decompress(path.read_bytes()))
            records = data.get("sessions") or []
        except (OSError, ValueError, EOFError):
            path.unlink(missing_ok=True)
            continue
        waiting = []
        for rec in records:
            if not isinstance(rec, dict) or not rec.get("id"):
                continue
            s = conn.execute("SELECT analysis_status, n_prompts, project_path, project_name, ai_title, first_prompt "
                             "FROM sessions WHERE id = ?", (rec["id"],)).fetchone()
            if s is None:
                waiting.append(rec)  # its transcript has not arrived yet
                continue
            if s["analysis_status"] in ("done", "running"):
                continue  # the hub's own analysis wins
            values = {c: rec.get(c) for c in ANALYSIS_COLS}
            if values["analyzed_prompts"] and (s["n_prompts"] or 0) < values["analyzed_prompts"]:
                values["analyzed_prompts"] = s["n_prompts"]  # counted by an older parser that saw replayed prompts twice
            if (s["n_prompts"] or 0) > (values["analyzed_prompts"] or 0):
                values["analysis_status"], values["analysis_reason"] = "stale", "session continued after analysis"
            values["title"] = best_title({"llm_title": values["llm_title"], "ai_title": s["ai_title"],
                                          "first_prompt": s["first_prompt"]})
            conn.execute(f"UPDATE sessions SET {', '.join(f'{c} = ?' for c in values)} WHERE id = ?",
                         [*values.values(), rec["id"]])
            for k in rec.get("knowledge") or []:
                if not isinstance(k, dict) or not k.get("title") or not k.get("kind"):
                    continue
                row = {c: k.get(c) for c in KNOWLEDGE_COLS}
                row.update(session_id=rec["id"], project_path=s["project_path"], project_name=s["project_name"])
                conn.execute(f"INSERT OR IGNORE INTO knowledge({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
                             list(row.values()))
            applied += 1
        conn.commit()
        if not waiting or time.time() - path.stat().st_mtime > ANALYSES_MAX_AGE:
            path.unlink(missing_ok=True)
        elif len(waiting) != len(records):
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(gzip.compress(json.dumps({"version": 1, "sessions": waiting}).encode(), mtime=0))
            os.replace(tmp, path)
    return applied


# ------------------------------------------------------------------ the hub's view of other computers
def machine_roots(cfg: Config) -> list[tuple[str, str, Path]]:
    """(machine id, kind, folder) of every agent folder received from other computers."""
    out = []
    if not cfg.machines_dir.is_dir():
        return out
    for mdir in sorted(cfg.machines_dir.iterdir()):
        if not mdir.is_dir() or not MACHINE_RE.match(mdir.name):
            continue
        for root in sorted(mdir.iterdir()):
            m = ROOT_RE.match(root.name)
            if root.is_dir() and m:
                out.append((mdir.name, m.group(1), root))
    return out


def machine_of(cfg: Config, path: Path | str | None) -> str | None:
    """The id of the computer a received folder belongs to, or None for this computer's own folders."""
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(cfg.machines_dir.resolve())
    except (ValueError, OSError):
        return None
    first = rel.parts[0] if rel.parts else ""
    return first if MACHINE_RE.match(first) else None


def machines(conn, cfg: Config) -> list[dict]:
    """Every computer the hub knows, with its session counts and whose it is, this one first."""
    from .db import kv_get

    register_local(conn, cfg)
    conn.commit()
    me = local_machine(cfg)["id"]
    counts = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT COALESCE(machine_id, ?), COUNT(*), MAX(ended_at) FROM sessions WHERE source != 'history' GROUP BY 1", (me,))}
    out = []
    for r in conn.execute("SELECT m.*, p.name AS person FROM machines m LEFT JOIN people p ON p.id = m.person_id "
                          "AND p.removed_at IS NULL ORDER BY m.role = 'this' DESC, m.last_seen DESC").fetchall():
        m = dict(r)
        m.pop("repos_json", None)
        m["folders"] = [] if m["id"] == me else [
            {"folder": f, "project": p, "name": Path(p).name or p} for f, p in sorted(folders_of(conn, m["id"]).items())]
        m["share"] = None if m["id"] == me else (kv_get(conn, SHARE_KV + m["id"]) or "everything")
        m["sessions"], m["last_session"] = counts.get(m["id"], (0, None))
        m["this"] = m["id"] == me
        out.append(m)
    return out


class ProjectResolver:
    """Maps a project folder on another computer to the same project's folder here.

    By git remote (the other computer reported its repositories' remotes, or the transcript names one), or by a
    folder that computer added to a project here (`chronicle hub add-folder`), whichever is more specific: a
    repository with a known remote inside an added folder follows its remote. Then by `[hub] path_map` prefixes;
    otherwise the folder is kept as that computer recorded it.
    """

    def __init__(self, cfg: Config, conn):
        self.cfg = cfg
        self.conn = conn
        self.me = local_machine(cfg)["id"]
        self._repos: dict[str, dict] = {}
        self._folders: dict[str, dict[str, str]] = {}
        self._local: dict[str, str] | None = None
        self._declared: list[str] | None = None

    def repos(self, machine_id: str) -> dict:
        if machine_id not in self._repos:
            row = self.conn.execute("SELECT repos_json FROM machines WHERE id = ?", (machine_id,)).fetchone()
            try:
                self._repos[machine_id] = json.loads(row[0]) if row and row[0] else {}
            except ValueError:
                self._repos[machine_id] = {}
        return self._repos[machine_id]

    def folders(self, machine_id: str) -> dict[str, str]:
        if machine_id not in self._folders:
            self._folders[machine_id] = folders_of(self.conn, machine_id)
        return self._folders[machine_id]

    def declared(self) -> list[str]:
        if self._declared is None:
            self._declared = declared_projects(self.conn)
        return self._declared

    def project_of(self, path: str | None) -> str | None:
        """A folder set up as a project here (add_project) holds everything below it."""
        if not path:
            return path
        return max((d for d in self.declared() if under(path, d)), key=len, default=path)

    def project_remotes(self) -> dict[str, str]:
        """{normalized remote: the project here its repository's sessions are filed under}."""
        return {rem: self.project_of(top) for rem, top in self.local_remotes().items()}

    def local_remotes(self) -> dict[str, str]:
        """{normalized remote: top-level folder} of the repositories this computer's own sessions ran in."""
        if self._local is None:
            from .db import kv_get, kv_set

            self._local = {}
            paths = [r[0] for r in self.conn.execute(  # where they ran, also when a set-up project holds them
                "SELECT COALESCE(machine_path, project_path) p, COUNT(*) n FROM sessions WHERE project_path IS NOT NULL "
                "AND (machine_id IS NULL OR machine_id = ?) GROUP BY p ORDER BY n", (self.me,))]
            for p in paths:
                key = f"git:{p}"
                cached = kv_get(self.conn, key)
                if cached is None:
                    info = git_info(p)
                    cached = json.dumps(list(info)) if info else ""
                    kv_set(self.conn, key, cached)
                if cached:
                    top, remote = json.loads(cached)
                    self._local[remote] = top  # ordered by use, so the most-used folder wins
        return self._local

    def resolve(self, machine_id: str | None, path: str | None, remote: str | None = None) -> str | None:
        if not path or not machine_id or machine_id == self.me:
            return self.project_of(path)
        return self.project_of(self._resolve(machine_id, path, remote))

    def _resolve(self, machine_id: str, path: str, remote: str | None) -> str:
        norm, top = normalize_remote(remote), None
        for repo_top, repo_remote in sorted(self.repos(machine_id).values(), key=lambda v: -len(v[0])):
            if path == repo_top or path.startswith(repo_top.rstrip("/") + "/"):
                top, norm = repo_top, norm or repo_remote
                break
        local_top = self.local_remotes().get(norm) if norm else None
        added = self.folders(machine_id)
        folder = max((f for f in added if under(path, f)), key=len, default=None)
        # a remote named by the transcript alone (no reported top level) is the session's own repository
        if local_top and (folder is None or top is None or len(top) >= len(folder)):
            rest = path[len(top):].strip("/") if top else ""
            return f"{local_top}/{rest}" if rest else local_top
        if folder is not None:
            return added[folder]  # the folder and everything below it is that project
        for src in sorted(self.cfg.hub_path_map, key=len, reverse=True):
            if path == src or path.startswith(src + "/"):
                return self.cfg.hub_path_map[src] + path[len(src):]
        return path


_resolvers: dict[int, ProjectResolver] = {}


def resolver(cfg: Config, conn, *, fresh: bool = False) -> ProjectResolver:
    key = id(conn)
    if fresh or key not in _resolvers or _resolvers[key].conn is not conn:
        _resolvers.clear()  # one live sync at a time; don't keep resolvers of closed connections around
        _resolvers[key] = ProjectResolver(cfg, conn)
    return _resolvers[key]


def join_command(url: str, token: str) -> str:
    return f"chronicle hub join {url} --token={quote(token, safe='-_')}"  # "=": a token may start with "-"


def invite_command(address: str, code: str) -> str:
    """What an invited person runs on their computer: it joins as them and shares knowledge only."""
    return f"chronicle hub join {address} --code {code} --share knowledge"


def invite_link(address: str, code: str) -> str:
    """The same invite opened in a browser: the hub's dashboard, without a computer joining."""
    return f"{address}/signin?code={quote(code, safe='-_')}"
