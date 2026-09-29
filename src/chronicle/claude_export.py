"""Import a claude.ai data export (claude.ai › Settings › Privacy › Export data) as sessions.

The export is a .zip with conversations.json (every chat: messages with text, thinking, tool use and attached
files), projects.json and users.json. Only conversations.json and projects.json are read; users.json (name, email)
is never opened. Imports are repeatable: a newer export updates the chats that changed and adds new ones.

Imported chats are not analyzed automatically (years of chats would use up the Claude plan's limits in one go):
analyze one with **Analyze now**, or import with `--analyze` to queue them all.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import zipfile
from pathlib import Path

from .copilot_parser import _Builder, finish_session
from .parser import ParsedSession
from .util import parse_ts, safe_text, to_iso, utcnow_iso

log = logging.getLogger("chronicle.claude_export")

CLAUDE_AI_PARSER_VERSION = 1
AGENT = "claude-ai"
SOURCE = "claude-ai-export"
LAST_IMPORT_KEY = "claude-ai:last-import"
NOT_ANALYZED = "imported claude.ai chat: not analyzed automatically (Analyze now, or import with --analyze)"


class ExportError(Exception):
    """The file is not a claude.ai export Chronicle can read."""


def _iso(value) -> str | None:
    return to_iso(parse_ts(value))


def read_export(path: Path) -> tuple[bytes, bytes | None]:
    """conversations.json and projects.json (raw) from the export .zip, its unpacked folder, or conversations.json."""
    path = Path(path).expanduser()
    if path.is_dir():
        conv, proj = path / "conversations.json", path / "projects.json"
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = {Path(n).name: n for n in z.namelist() if not n.startswith("__MACOSX/")}
            if "conversations.json" not in names:
                raise ExportError(f"{path.name} has no conversations.json: is it a claude.ai data export?")
            return z.read(names["conversations.json"]), z.read(names["projects.json"]) if "projects.json" in names else None
    elif path.suffix == ".json" and path.is_file():
        conv, proj = path, path.with_name("projects.json")
    elif path.exists():
        raise ExportError(f"{path.name} is not a claude.ai export: give the .zip, its unpacked folder, or conversations.json")
    else:
        raise ExportError(f"{path} not found")
    if not conv.is_file():
        raise ExportError(f"no conversations.json in {path}")
    return conv.read_bytes(), proj.read_bytes() if proj.is_file() else None


def load_conversations(raw: bytes) -> list[dict]:
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ExportError("conversations.json is not valid JSON") from exc
    if isinstance(data, dict):
        data = data.get("conversations") or []
    if not isinstance(data, list):
        raise ExportError("conversations.json is not a list of conversations")
    first = next((c for c in data if isinstance(c, dict)), {})
    if "mapping" in first and "chat_messages" not in first:
        raise ExportError("this is a ChatGPT export, not a claude.ai one")
    return [c for c in data if isinstance(c, dict) and c.get("uuid")]


def project_names(raw: bytes | None) -> dict[str, str]:
    try:
        data = json.loads(raw) if raw else []
    except ValueError:
        return {}
    return {p["uuid"]: p.get("name") or "" for p in data if isinstance(p, dict) and p.get("uuid")} if isinstance(data, list) else {}


def conversation_signature(conv: dict) -> str:
    msgs = conv.get("chat_messages") or []
    last = msgs[-1].get("uuid") if msgs and isinstance(msgs[-1], dict) else None
    return f"{conv.get('updated_at')}|{len(msgs)}|{last}|v{CLAUDE_AI_PARSER_VERSION}"


def _blocks(msg: dict) -> list[dict]:
    content = msg.get("content")
    if isinstance(content, list) and any(isinstance(b, dict) for b in content):
        return [b for b in content if isinstance(b, dict)]
    return [{"type": "text", "text": msg.get("text") or ""}]


def _result_text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
    return content if isinstance(content, str) else ""


def parse_conversation(conv: dict, projects: dict[str, str]) -> ParsedSession | None:
    msgs = [m for m in conv.get("chat_messages") or [] if isinstance(m, dict)]
    if not any(m.get("sender") == "human" for m in msgs):
        return None  # an empty chat
    ps = ParsedSession(id=conv["uuid"])
    project = conv.get("project") if isinstance(conv.get("project"), dict) else {}
    name = project.get("name") or projects.get(conv.get("project_uuid") or project.get("uuid") or "")
    ps.project_path = f"claude.ai/{name}" if name else "claude.ai"
    ps.entrypoint = "claude.ai"
    ps.custom_title = safe_text(conv.get("name") or "") or None
    b = _Builder(ps)
    b.stamps += [t for t in (_iso(conv.get("created_at")), _iso(conv.get("updated_at"))) if t]
    for m in msgs:
        ts = _iso(m.get("created_at"))
        blocks = _blocks(m)
        if m.get("sender") == "human":
            text = "\n\n".join(bl.get("text") or "" for bl in blocks if bl.get("type") == "text").strip()
            notes = [f"[attached {a.get('file_name') or 'a file'}, {len(a.get('extracted_content') or ''):,} chars]"
                     for a in m.get("attachments") or [] if isinstance(a, dict)]
            files = [f for f in m.get("files") or m.get("files_v2") or [] if isinstance(f, dict)]
            ps.n_images += sum(1 for f in files if f.get("file_kind") in (None, "image"))
            notes += [f"[file {f.get('file_name') or 'image'}]" for f in files]
            b.prompt(ts, "\n\n".join([text, *notes]).strip())
            continue
        results = [bl for bl in blocks if bl.get("type") == "tool_result"]
        for bl in blocks:
            bts = _iso(bl.get("start_timestamp")) or ts
            kind = bl.get("type")
            if kind == "thinking" and (bl.get("thinking") or "").strip():
                b.event(bts, "assistant", "thinking", bl["thinking"])
            elif kind == "text" and (bl.get("text") or "").strip():
                b.event(bts, "assistant", "text", bl["text"])
            elif kind == "tool_use":
                match = next((r for r in results if bl.get("id") and r.get("tool_use_id") == bl.get("id")), None) \
                    or next((r for r in results if r.get("name") == bl.get("name")), None)
                if match:
                    results.remove(match)
                inp = bl.get("input") if isinstance(bl.get("input"), dict) else {}
                b.tool(bts, bl.get("id"), bl.get("name") or "tool", inp, result=_result_text(match) if match else None,
                       is_error=bool(match and match.get("is_error")))
    if conv.get("model"):
        ps.models[conv["model"]] += 1
    return finish_session(ps, b.stamps)


def import_export(cfg, conn, path: Path, *, analyze: bool = False, progress=None) -> dict:
    """Import (or re-import) a claude.ai export. Returns counts for the CLI and the dashboard."""
    from .db import kv_set
    from .ingest import _unchanged, forgotten_ids, store_parsed
    from .util import file_lock

    raw_conv, raw_proj = read_export(Path(path))
    convs = load_conversations(raw_conv)
    projects = project_names(raw_proj)
    dst = cfg.archive_dir / "claude-ai" / hashlib.sha1(raw_conv).hexdigest()[:12]
    archive = dst / "conversations.json.gz"
    if not archive.exists():  # the export itself, kept for good (users.json is not copied)
        dst.mkdir(parents=True, exist_ok=True)
        for name, raw in (("conversations.json.gz", raw_conv), ("projects.json.gz", raw_proj)):
            if raw:
                with gzip.open(dst / name, "wb") as f:
                    f.write(raw)
    counts = {"conversations": len(convs), "new": 0, "updated": 0, "unchanged": 0, "empty": 0, "excluded": 0}
    with file_lock(cfg.locks_dir / "ingest.lock", timeout=900) as got:
        if not got:
            raise ExportError("a sync is running; try again when it finishes")
        skip = forgotten_ids(conn)
        for i, conv in enumerate(convs):
            if progress and i % 50 == 0:
                progress(f"importing claude.ai chats… {i:,}/{len(convs):,}")
            sid, sig = conv["uuid"], conversation_signature(conv)
            if sid in skip or _unchanged(conn, sid, sig, False):
                counts["unchanged"] += 1
                continue
            ps = parse_conversation(conv, projects)
            if ps is None:
                counts["empty"] += 1
                continue
            if cfg.is_excluded(ps.project_path):
                counts["excluded"] += 1
                continue
            result = store_parsed(conn, cfg, ps, claude_dir=dst, project_dir=None, transcript_path=archive,
                                  archive_path=archive, files_sig=sig, agent=AGENT, source=SOURCE)
            if not analyze:
                conn.execute("UPDATE sessions SET analysis_status = 'skipped', analysis_reason = ? "
                             "WHERE id = ? AND analysis_status = 'pending'", (NOT_ANALYZED, sid))
            counts["new" if result == "new" else "updated"] += 1
            conn.commit()
        kv_set(conn, LAST_IMPORT_KEY, json.dumps({"at": utcnow_iso(), "file": Path(path).name, **counts}))
        conn.commit()
    log.info("claude.ai import from %s: %s", path, counts)
    return counts


def summary(counts: dict) -> str:
    parts = [f"{counts['new']} new", f"{counts['updated']} updated", f"{counts['unchanged']} unchanged"]
    if counts.get("empty"):
        parts.append(f"{counts['empty']} empty")
    if counts.get("excluded"):
        parts.append(f"{counts['excluded']} excluded")
    return f"claude.ai export: {counts['conversations']} chats · " + ", ".join(parts)


def import_status(conn) -> dict:
    from .db import kv_get

    r = conn.execute("SELECT COUNT(*), SUM(analysis_status = 'done'), MAX(ended_at) FROM sessions WHERE source = ?",
                     (SOURCE,)).fetchone()
    try:
        last = json.loads(kv_get(conn, LAST_IMPORT_KEY) or "null")
    except ValueError:
        last = None
    return {"sessions": r[0] or 0, "analyzed": r[1] or 0, "last_chat": r[2], "last_import": last}
