"""Several computers, one archive.

One computer, the hub, is the only one that writes the database: it records, analyzes and serves the dashboard.
The others (spokes) send it their coding agents' raw session files over HTTP, usually inside a Tailscale network,
and the hub ingests them as if they were its own, tagged with the computer they came from. A push is stateless:
the spoke asks the hub which files it already has (by size and modification time) and sends only the rest, so a
lost push is simply redone by the next one.

A spoke that already analyzed sessions with its own Chronicle sends those results once, when it first joins, so
the hub does not pay to analyze the same sessions again.
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


class HubError(Exception):
    pass


class HubUnreachable(HubError):
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


def hub_projects(conn, limit: int = 1000) -> list[dict]:
    """The projects this hub files sessions under, busiest first: what another computer can add a folder to."""
    return [{"path": r[0], "name": r[1], "sessions": r[2]} for r in conn.execute(
        "SELECT project_path, MAX(project_name), COUNT(*) FROM sessions WHERE project_path IS NOT NULL "
        "AND source != 'history' GROUP BY project_path ORDER BY COUNT(*) DESC LIMIT ?", (limit,))]


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
        hdrs = {"Authorization": f"Bearer {self.token}", "User-Agent": f"chronicle/{__version__}", **(headers or {})}
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
            raise HubError("the hub did not accept this computer's token; run `chronicle hub join` again with the "
                           "command `chronicle hub enable` prints on the hub")
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

    def summary(self) -> str:
        parts = [f"{self.sent} file{'s' * (self.sent != 1)} sent ({self.bytes / 1e6:.1f} MB)", f"{self.unchanged} unchanged"]
        if self.skipped:
            parts.append(f"{self.skipped} excluded")
        if self.analyses:
            parts.append(f"{self.analyses} earlier analyses handed over")
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
            "folders": cfg.hub_folders}


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


def push(cfg: Config, *, progress=None, client: HubClient | None = None) -> PushReport:
    """Send the hub every session file it lacks (or has an older copy of)."""
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


def hello(cfg: Config, conn, body: dict) -> dict:
    machine_id = check_machine(cfg, str(body.get("machine") or ""))
    if int(body.get("protocol", 0)) != PROTOCOL:
        return {"protocol": PROTOCOL, "version": __version__}
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

    folders, moved = folders_of(conn, machine_id), 0
    if "folders" in body:  # an older spoke doesn't send them: keep what it had
        sent = clean_folders(body.get("folders"))
        if sent != folders:
            kv_set(conn, FOLDERS_KV + machine_id, json.dumps(sent))
            conn.commit()
            moved = refile(cfg, conn, machine_id, set(folders) | set(sent))
            folders = sent
    remotes = ProjectResolver(cfg, conn).local_remotes()
    report = folders_report(conn, machine_id, folders, repos, remotes)
    conn.commit()  # local_remotes caches what git said
    me = local_machine(cfg)
    return {"protocol": PROTOCOL, "version": __version__, "hub": me["name"],
            "inventory": inventory(cfg, machine_id), "wants_analyses": not kv_get(conn, f"hub-analyses:{machine_id}"),
            "projects": hub_projects(conn), "remotes": remotes, "folders": report, "moved": moved}


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
    """Every computer the hub knows, with its session counts, this one first."""
    register_local(conn, cfg)
    conn.commit()
    me = local_machine(cfg)["id"]
    counts = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT COALESCE(machine_id, ?), COUNT(*), MAX(ended_at) FROM sessions WHERE source != 'history' GROUP BY 1", (me,))}
    out = []
    for r in conn.execute("SELECT * FROM machines ORDER BY role = 'this' DESC, last_seen DESC").fetchall():
        m = dict(r)
        m.pop("repos_json", None)
        m["folders"] = [] if m["id"] == me else [
            {"folder": f, "project": p, "name": Path(p).name or p} for f, p in sorted(folders_of(conn, m["id"]).items())]
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

    def local_remotes(self) -> dict[str, str]:
        """{normalized remote: top-level folder} of the repositories this computer's own sessions ran in."""
        if self._local is None:
            from .db import kv_get, kv_set

            self._local = {}
            paths = [r[0] for r in self.conn.execute(
                "SELECT project_path, COUNT(*) n FROM sessions WHERE project_path IS NOT NULL AND "
                "(machine_id IS NULL OR machine_id = ?) GROUP BY project_path ORDER BY n", (self.me,))]
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
            return path
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
    return f"chronicle hub join {url} --token {quote(token, safe='-_')}"
