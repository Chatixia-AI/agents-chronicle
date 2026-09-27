"""Parse IBM Bob tasks (~/.bob/db/bob.db) into the same model as Claude Code sessions.

bob.db holds `tasks` (directory, title, git info, costs JSON, status) and `messages` (one OpenAI-style chat
message per row in `data`: role, content, tool_calls, ...). The database also stores login state elsewhere in
~/.bob; only these two tables are read, read-only.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path

from .copilot_parser import _Builder, _args, estimate_cost, finish_session, ms_to_iso, uri_path
from .parser import ApiCall, ParsedSession
from .pricing import normalize_model
from .util import safe_text

log = logging.getLogger("chronicle.bob")

BOB_PARSER_VERSION = 1
_ENV_RE = re.compile(r"<environment_details>.*?</environment_details>", re.S)
_TASK_RE = re.compile(r"^\s*<(?:task|user_message)>(.*?)</(?:task|user_message)>\s*$", re.S)


def bob_db(home: Path) -> Path:
    return home / "db" / "bob.db"


def load_tasks(home: Path) -> list[dict]:
    """Tasks with their messages, oldest message first. Read-only; returns [] if the database is unreadable."""
    db = bob_db(home)
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        tasks = [dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY created_at")]
        msgs: dict[str, list[dict]] = {}
        for r in conn.execute("SELECT id, task_id, role, data, created_at FROM messages ORDER BY created_at, id"):
            msgs.setdefault(r["task_id"], []).append(dict(r))
        conn.close()
    except sqlite3.Error as exc:
        log.warning("bob.db unreadable: %s", exc)
        return []
    for t in tasks:
        t["messages"] = msgs.get(t["id"], [])
    return tasks


def task_signature(task: dict) -> str:
    last = task["messages"][-1] if task["messages"] else {}
    return f"{task.get('updated_at')}:{len(task['messages'])}:{last.get('id')}:{task.get('status')}"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in ("text", "input_text", "output_text"))
    return ""


def _user_text(content) -> str:
    text = _ENV_RE.sub("", _text(content)).strip()
    m = _TASK_RE.match(text)
    return m.group(1).strip() if m else text


def parse_bob_task(task: dict) -> ParsedSession | None:
    msgs = task.get("messages") or []
    if not any(m["role"] == "user" for m in msgs):
        return None
    ps = ParsedSession(id=task["id"])
    ps.project_path = uri_path(task.get("directory") or task.get("project_id") or "") or None  # project_id is a file: URI
    ps.git_branch = task.get("git_branch") or None
    ps.cc_version = task.get("version") or None
    ps.entrypoint = f"bob:{task.get('task_type') or 'normal'}"
    ps.custom_title = task.get("title") or None
    b = _Builder(ps)
    for ms in (task.get("created_at"), task.get("updated_at")):
        if ms_to_iso(ms):
            b.stamps.append(ms_to_iso(ms))
    results: dict[str, str] = {}
    for m in msgs:
        try:
            d = json.loads(m["data"])
        except (TypeError, ValueError):
            ps.parse_errors += 1
            continue
        if isinstance(d, dict) and d.get("role") == "tool" and d.get("tool_call_id"):
            results[d["tool_call_id"]] = _text(d.get("content"))
    for m in msgs:
        ts = ms_to_iso(m.get("created_at"))
        try:
            d = json.loads(m["data"])
        except (TypeError, ValueError):
            continue
        if not isinstance(d, dict):
            continue
        role = d.get("role") or m.get("role")
        if role == "system":
            b.event(ts, "system", "meta", f"[system prompt, {len(_text(d.get('content'))):,} chars]")
        elif role == "user":
            b.prompt(ts, _user_text(d.get("content")))
        elif role == "assistant":
            reasoning = d.get("reasoning") or d.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                b.event(ts, "assistant", "thinking", reasoning)
            text = _text(d.get("content"))
            if text.strip():
                b.event(ts, "assistant", "text", text)
            for tc in d.get("tool_calls") or []:
                fn = tc.get("function") if isinstance(tc, dict) else None
                if not isinstance(fn, dict):
                    continue
                res = results.get(tc.get("id"))
                b.tool(ts, tc.get("id"), fn.get("name") or "tool", _args(fn.get("arguments")), result=res,
                       is_error=bool(res) and res.lower().startswith(("error", "failed")))
    if task.get("status") == "error" and task.get("last_error"):
        ps.n_api_errors += 1
        b.event(b.stamps[-1] if b.stamps else None, "system", "api_error", safe_text(str(task["last_error"]))[:300])
    try:
        costs = json.loads(task.get("costs") or "{}")
    except ValueError:
        costs = {}
    if isinstance(costs, dict) and any(costs.get(k) for k in ("input", "output", "cacheRead", "cacheWrite")):
        model = normalize_model(costs.get("model"))
        inp, out, cr, cw = (int(costs.get(k) or 0) for k in ("input", "output", "cacheRead", "cacheWrite"))
        ps.api_calls.append(ApiCall("", "task-total", ms_to_iso(task.get("updated_at")), model, input_tokens=inp,
                                    output_tokens=out, cache_read_tokens=cr, cache_write_tokens=cw,
                                    cost_usd=float(costs.get("cost") or 0) or estimate_cost(model, inp, cr, cw, out)))
    return finish_session(ps, b.stamps)
