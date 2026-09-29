"""Import chats from a claude.ai or ChatGPT data export as sessions (`chronicle import`, Sources › Import export…).

Both exports are a .zip with conversations.json; the format is recognized from its contents. Only the chats
(conversations.json, and claude.ai's projects.json for project names) are read and archived; the account files
(users.json, user.json) and ChatGPT's chat.html are never opened. Imports are repeatable: a newer export updates the
chats that changed and adds new ones.

Imported chats are not analyzed automatically (years of chats would use up the Claude plan's limits in one go):
analyze one with **Analyze now**, or import with `--analyze` to queue them all.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import chatgpt_export, claude_export
from .util import utcnow_iso

log = logging.getLogger("chronicle.chat_import")

_CONVERSATIONS_RE = re.compile(r"^conversations(?:-\d+)?\.json$")  # large exports may be split


@dataclass(frozen=True)
class Format:
    key: str  # kv and archive name
    label: str
    module: object

    @property
    def agent(self) -> str:
        return self.module.AGENT

    @property
    def source(self) -> str:
        return self.module.SOURCE

    @property
    def last_import_key(self) -> str:
        return f"{self.key}:last-import"

    @property
    def not_analyzed(self) -> str:
        return f"imported {self.label} chat: not analyzed automatically (Analyze now, or import with --analyze)"


CLAUDE_AI = Format("claude-ai", "claude.ai", claude_export)
CHATGPT = Format("chatgpt", "ChatGPT", chatgpt_export)
FORMATS = (CLAUDE_AI, CHATGPT)


class ExportError(Exception):
    """The file is not an export Chronicle can read."""


@dataclass
class Export:
    format: Format
    conversations: list[dict]
    files: dict[str, bytes]  # what gets archived: the conversations file(s), claude.ai's projects.json


def _files(path: Path) -> dict[str, bytes]:
    """The chat files of an export .zip, its unpacked folder, or a conversations.json."""
    path = Path(path).expanduser()
    wanted = lambda name: bool(_CONVERSATIONS_RE.match(name)) or name == "projects.json"
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = {Path(n).name: n for n in z.namelist() if not n.startswith("__MACOSX/")}
            return {name: z.read(full) for name, full in sorted(names.items()) if wanted(name)}
    if path.is_dir():
        return {p.name: p.read_bytes() for p in sorted(path.iterdir()) if p.is_file() and wanted(p.name)}
    if path.suffix == ".json" and path.is_file():
        sibling = path.with_name("projects.json")
        return {"conversations.json": path.read_bytes(), **({"projects.json": sibling.read_bytes()} if sibling.is_file() else {})}
    if path.exists():
        raise ExportError(f"{path.name} is not a chat export: give the .zip, its unpacked folder, or conversations.json")
    raise ExportError(f"{path} not found")


def _folders(path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(path) as z:
            return {n.split("/")[0] for n in z.namelist() if "/" in n}
    except (OSError, zipfile.BadZipFile):
        return set()


def read_export(path: Path, name: str | None = None) -> Export:
    name = name or Path(path).name
    files = _files(path)
    shards = [n for n in files if _CONVERSATIONS_RE.match(n)]
    if not shards and "projects" in _folders(path):
        raise ExportError(f"{name} holds your claude.ai projects, not chats, and the export does not say which project a "
                          "chat belongs to: there is nothing to import from it. The chats are in conversations-000.zip.")
    if not shards:
        raise ExportError(f"no conversations.json in {name}: is it a claude.ai or ChatGPT data export? "
                          "(claude.ai sends several zips; the chats are in conversations-000.zip)")
    conversations: list[dict] = []
    for name in shards:
        try:
            data = json.loads(files[name])
        except ValueError as exc:
            raise ExportError(f"{name} is not valid JSON") from exc
        if isinstance(data, dict):
            data = data.get("conversations") or []
        if not isinstance(data, list):
            raise ExportError(f"{name} is not a list of conversations")
        conversations += [c for c in data if isinstance(c, dict)]
    fmt = CHATGPT if chatgpt_export.is_chatgpt(conversations) else CLAUDE_AI
    if fmt is CLAUDE_AI and conversations and not claude_export.is_claude(conversations):
        raise ExportError("conversations.json is neither a claude.ai nor a ChatGPT export")
    if fmt is CHATGPT:
        files.pop("projects.json", None)
    return Export(fmt, conversations, files)


def import_export(cfg, conn, path: Path, *, analyze: bool = False, progress=None, name: str | None = None) -> dict:
    """Import (or re-import) an export. `name` is the file's name when `path` is an upload's temporary copy."""
    from .db import kv_set
    from .ingest import _unchanged, forgotten_ids, store_parsed
    from .util import file_lock

    name = name or Path(path).name
    export = read_export(Path(path), name)
    fmt, mod = export.format, export.format.module
    projects = claude_export.project_names(export.files.get("projects.json")) if fmt is CLAUDE_AI else {}
    digest = hashlib.sha1(b"".join(export.files[k] for k in sorted(export.files))).hexdigest()[:12]
    dst = cfg.archive_dir / fmt.key / digest
    shard = next(n for n in export.files if _CONVERSATIONS_RE.match(n))
    archive = dst / f"{shard}.gz"
    if not archive.exists():  # the export's chats, kept for good
        dst.mkdir(parents=True, exist_ok=True)
        for fname, raw in export.files.items():
            with gzip.open(dst / f"{fname}.gz", "wb") as f:
                f.write(raw)
    counts = {"format": fmt.label, "conversations": len(export.conversations), "new": 0, "updated": 0, "unchanged": 0,
              "empty": 0, "excluded": 0}
    with file_lock(cfg.locks_dir / "ingest.lock", timeout=900) as got:
        if not got:
            raise ExportError("a sync is running; try again when it finishes")
        skip = forgotten_ids(conn)
        for i, conv in enumerate(export.conversations):
            if progress and i % 50 == 0:
                progress(f"importing {fmt.label} chats… {i:,}/{len(export.conversations):,}")
            sid, sig = mod.conversation_id(conv), mod.conversation_signature(conv)
            if not sid:
                counts["empty"] += 1
                continue
            if sid in skip or _unchanged(conn, sid, sig, False):
                counts["unchanged"] += 1
                continue
            ps = mod.parse_conversation(conv, projects)
            if ps is None:
                counts["empty"] += 1
                continue
            if cfg.is_excluded(ps.project_path):
                counts["excluded"] += 1
                continue
            result = store_parsed(conn, cfg, ps, claude_dir=dst, project_dir=None, transcript_path=archive,
                                  archive_path=archive, files_sig=sig, agent=fmt.agent, source=fmt.source)
            if not analyze:
                conn.execute("UPDATE sessions SET analysis_status = 'skipped', analysis_reason = ? "
                             "WHERE id = ? AND analysis_status = 'pending'", (fmt.not_analyzed, sid))
            counts["new" if result == "new" else "updated"] += 1
            conn.commit()
        kv_set(conn, fmt.last_import_key, json.dumps({"at": utcnow_iso(), "file": name, **counts}))
        conn.commit()
    log.info("%s import from %s: %s", fmt.label, name, counts)
    return counts


def summary(counts: dict) -> str:
    parts = [f"{counts['new']} new", f"{counts['updated']} updated", f"{counts['unchanged']} unchanged"]
    if counts.get("empty"):
        parts.append(f"{counts['empty']} empty")
    if counts.get("excluded"):
        parts.append(f"{counts['excluded']} excluded")
    return f"{counts['format']} export: {counts['conversations']} chats · " + ", ".join(parts)


def import_status(conn) -> dict:
    """Per format: chats imported and analyzed, and the last import."""
    from .db import kv_get

    out = {}
    for fmt in FORMATS:
        r = conn.execute("SELECT COUNT(*), SUM(analysis_status = 'done') FROM sessions WHERE source = ?", (fmt.source,)).fetchone()
        try:
            last = json.loads(kv_get(conn, fmt.last_import_key) or "null")
        except ValueError:
            last = None
        out[fmt.key] = {"label": fmt.label, "agent": fmt.agent, "sessions": r[0] or 0, "analyzed": r[1] or 0, "last_import": last}
    return out
