"""Claude Code hook entrypoints. These must return fast: heavy work is handed to a detached process."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

INTERNAL_ENV = "CHRONICLE_INTERNAL"


def _read_payload() -> dict:
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except (ValueError, OSError):
        return {}


def self_command() -> list[str]:
    """argv that re-runs this program: the bundled executable inside Chronicle.app, else `python -m chronicle`."""
    return [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "chronicle"]


def spawn_detached(args: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as log:
        subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
            env={k: v for k, v in os.environ.items() if k != INTERNAL_ENV},
        )


def hook_main(event: str) -> int:
    """Entry for `chronicle hook <event>`; never fails loudly (a hook error must not disturb Claude Code)."""
    if os.environ.get(INTERNAL_ENV):
        return 0
    payload = _read_payload()
    try:
        if event in ("session-end", "stop", "pre-compact"):
            return _on_session_end(payload, ended=event == "session-end")
        if event == "session-start":
            return _on_session_start(payload)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"chronicle hook {event} failed: {exc}", file=sys.stderr)
    return 0


def _on_session_end(payload: dict, *, ended: bool) -> int:
    from .config import chronicle_home

    transcript = payload.get("transcript_path")
    home = chronicle_home()
    args = [*self_command(), "ingest-session"]
    if transcript:
        args.append(transcript)
    if ended:
        args.append("--ended")
    args.append("--work")
    spawn_detached(args, home / "logs" / "hooks.log")
    return 0


def _on_session_start(payload: dict) -> int:
    from .config import load_config

    cfg = load_config(create=False)
    if not cfg.inject_session_start or not cfg.db_path.exists():
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    context = build_session_context(cfg, cwd)
    if context:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}))
    return 0


def build_session_context(cfg, cwd: str) -> str | None:
    """A compact digest of what previous sessions learned about this project."""
    from .db import connect
    from .synthesize import kb_for_path, kb_sections
    from .util import local_str, one_line

    conn = connect(cfg.db_path, readonly=True)
    try:
        kb = kb_for_path(conn, cwd)
        lines: list[str] = []
        if kb:
            lines.append(f"Chronicle knowledge base for {kb['project_name']} (from past Claude Code sessions, "
                         f"updated {local_str(kb['updated_at'], '%Y-%m-%d')}):")
            for section in kb_sections(kb):
                items = section.get("items") or []
                if not items:
                    continue
                lines.append(f"{section.get('title')}:")
                lines += [f"- {one_line(i.get('text') or '', 300)}" for i in items[:6]]
        else:
            rows = conn.execute(
                "SELECT kind, title FROM knowledge WHERE status = 'active' AND project_path = ? "
                "AND kind IN ('gotcha', 'fix', 'fact', 'decision', 'preference') ORDER BY pinned DESC, id DESC LIMIT 12",
                (cwd,),
            ).fetchall()
            if rows:
                lines.append("Chronicle notes from past Claude Code sessions in this project:")
                lines += [f"- [{r['kind']}] {one_line(r['title'], 200)}" for r in rows]
        recent = conn.execute(
            "SELECT started_at, title, outcome FROM sessions WHERE project_path = ? AND source != 'history' "
            "ORDER BY started_at DESC LIMIT 3", (cwd,),
        ).fetchall()
        if recent:
            lines.append("Recent sessions here: " + "; ".join(
                f"{local_str(r['started_at'], '%m-%d')} {one_line(r['title'] or '', 80)} ({r['outcome'] or 'not analyzed'})"
                for r in recent))
        if not lines:
            return None
        lines.append("Use the chronicle MCP tools (search_sessions, search_knowledge, get_session) for details.")
        text = "\n".join(lines)
        return text[: cfg.inject_max_chars]
    finally:
        conn.close()
