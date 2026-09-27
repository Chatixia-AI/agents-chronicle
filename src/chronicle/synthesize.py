"""Cross-session synthesis: consolidate knowledge items into per-project knowledge bases and a global playbook."""

from __future__ import annotations

import json
import logging
import sqlite3

from .config import Config
from .llm import ClaudeRunner
from .util import dumps, local_str, loads, one_line, truncate, utcnow_iso

log = logging.getLogger("chronicle.synthesize")

GLOBAL = "__global__"
MAX_ITEMS = 250

KB_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overview", "sections", "superseded_ids"],
    "properties": {
        "overview": {
            "type": "string",
            "description": "2-4 short paragraphs of markdown: what this is, how it is built, and its current state",
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "items"],
                "properties": {
                    "title": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["text", "sources"],
                            "properties": {
                                "text": {"type": "string", "description": "One self-contained markdown bullet"},
                                "sources": {"type": "array", "items": {"type": "integer"},
                                            "description": "ids of the knowledge items this bullet is based on"},
                            },
                        },
                    },
                },
            },
        },
        "superseded_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "ids of items that are outdated, contradicted by newer items, or fully duplicated by another item",
        },
    },
}

PROJECT_SYSTEM = """\
You maintain the knowledge base of one software project, distilled from many Claude Code sessions.

You receive the project's recent sessions and its knowledge items (each with an id, kind, date, confidence and \
source; "memory" items were written by Claude Code's own memory feature and are usually reliable). You may also \
receive the previous version of the knowledge base.

Write the current knowledge base:
- An overview of what the project is, how it is built, and where it stands now.
- Sections of concise, self-contained bullets. Suggested sections (use only those that have content, add others if \
needed): "Architecture & key facts", "Run, test & deploy", "Gotchas & fixes", "Decisions & rationale", \
"Conventions & preferences", "Useful commands", "Open threads".
- Merge duplicates into one bullet, prefer newer and higher-confidence items when they conflict, and keep concrete \
identifiers (paths, commands, config keys, error messages). Cite the ids each bullet is based on.
- List in superseded_ids the items that are outdated, contradicted by a newer item, or fully duplicated.
Do not invent anything that the items do not support."""

GLOBAL_SYSTEM = """\
You maintain a developer's personal engineering playbook, distilled from knowledge extracted across all of their \
Claude Code sessions and projects.

You receive cross-project knowledge items (each with an id, kind, project, date and confidence) and possibly the \
previous playbook. Write the current playbook:
- An overview of how this developer works and what they work on.
- Sections of concise, self-contained bullets. Suggested sections (use only those with content): \
"Working preferences for Claude", "Tooling & platform gotchas", "Reusable patterns & commands", "Learnings", \
"Recurring problems".
- Merge duplicates, prefer newer items on conflict, keep concrete identifiers, and cite source ids per bullet.
- List in superseded_ids the items that are outdated, contradicted or fully duplicated.
Do not invent anything that the items do not support."""


def _item_line(k: dict) -> dict:
    return {
        "id": k["id"],
        "kind": k["kind"],
        "date": (k.get("created_at") or "")[:10],
        "confidence": k.get("confidence"),
        "source": k.get("source"),
        "project": k.get("project_name"),
        "title": k["title"],
        "body": truncate(k.get("body") or "", 900),
    }


def projects_needing_synthesis(conn: sqlite3.Connection, cfg: Config, force: bool = False) -> list[str]:
    out = []
    rows = conn.execute(
        "SELECT project_path, MAX(id) AS max_id, COUNT(*) AS n FROM knowledge "
        "WHERE status = 'active' AND project_path IS NOT NULL GROUP BY project_path"
    ).fetchall()
    for r in rows:
        if cfg.is_excluded(r["project_path"]):
            continue
        if not force and conn.execute(
            "SELECT 1 FROM sessions WHERE project_path = ? AND source != 'history' AND analysis_status IN ('pending', 'stale') "
            "LIMIT 1", (r["project_path"],)).fetchone():
            continue  # more of this project's sessions are queued: synthesize once, after they are analyzed
        kb = conn.execute("SELECT knowledge_max_id FROM project_kb WHERE project_path = ?", (r["project_path"],)).fetchone()
        last = kb["knowledge_max_id"] if kb else 0
        new_items = conn.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project_path = ? AND status = 'active' AND id > ?",
            (r["project_path"], last or 0),
        ).fetchone()[0]
        if force and new_items:
            out.append(r["project_path"])
        elif new_items >= cfg.synthesis.min_new_items or (kb is None and r["n"] >= 2):
            out.append(r["project_path"])
    return out


def global_needs_synthesis(conn: sqlite3.Connection, cfg: Config) -> bool:
    kb = conn.execute("SELECT knowledge_max_id FROM project_kb WHERE project_path = ?", (GLOBAL,)).fetchone()
    last = kb["knowledge_max_id"] if kb else 0
    n = conn.execute(
        "SELECT COUNT(*) FROM knowledge WHERE status = 'active' AND (scope = 'global' OR kind = 'preference') AND id > ?",
        (last or 0,),
    ).fetchone()[0]
    return n >= max(cfg.synthesis.min_new_items, 5)


def synthesize_project(conn: sqlite3.Connection, cfg: Config, project_path: str, runner: ClaudeRunner | None = None) -> dict:
    runner = runner or ClaudeRunner(cfg)
    is_global = project_path == GLOBAL
    if is_global:
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM knowledge WHERE status = 'active' AND (scope = 'global' OR kind = 'preference') "
            "ORDER BY pinned DESC, id DESC LIMIT ?", (MAX_ITEMS,))]
        name = "Global playbook"
        sessions_txt = ""
    else:
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM knowledge WHERE status = 'active' AND project_path = ? "
            "ORDER BY pinned DESC, CASE confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id DESC LIMIT ?",
            (project_path, MAX_ITEMS))]
        name_row = conn.execute("SELECT project_name FROM sessions WHERE project_path = ? LIMIT 1", (project_path,)).fetchone()
        name = name_row[0] if name_row else project_path.rstrip("/").split("/")[-1]
        sessions = conn.execute(
            "SELECT started_at, title, outcome, summary FROM sessions WHERE project_path = ? AND source != 'history' "
            "ORDER BY started_at DESC LIMIT 40", (project_path,)).fetchall()
        sessions_txt = "\n".join(
            f"- {local_str(s['started_at'], '%Y-%m-%d')} [{s['outcome'] or 'not analyzed'}] {s['title']}: "
            f"{one_line(s['summary'] or '', 220)}" for s in sessions
        )
    if not items:
        raise ValueError(f"no active knowledge for {project_path}")
    # threshold bookkeeping must reflect what this synthesis saw, not items added during the (slow) call
    max_id = conn.execute(
        "SELECT MAX(id) FROM knowledge WHERE " + ("(scope = 'global' OR kind = 'preference')" if is_global else "project_path = ?"),
        () if is_global else (project_path,),
    ).fetchone()[0]
    prev = conn.execute("SELECT markdown FROM project_kb WHERE project_path = ?", (project_path,)).fetchone()
    parts = [f"<project name=\"{name}\" path=\"{project_path}\" />"] if not is_global else []
    if sessions_txt:
        parts.append(f"<recent_sessions>\n{sessions_txt}\n</recent_sessions>")
    parts.append("<knowledge_items>\n" + "\n".join(json.dumps(_item_line(k), ensure_ascii=False) for k in items)
                 + "\n</knowledge_items>")
    if prev and prev["markdown"]:
        parts.append(f"<previous_version>\n{truncate(prev['markdown'], 20000)}\n</previous_version>")
    parts.append("Write the updated knowledge base." if not is_global else "Write the updated playbook.")
    res = runner.run("\n\n".join(parts), KB_SCHEMA, system=GLOBAL_SYSTEM if is_global else PROJECT_SYSTEM,
                     model=cfg.synthesis.model)
    data = normalize_kb(res.data)
    valid_ids = {k["id"] for k in items}
    # only a project's own synthesis retires items: the global playbook merges across projects, and a
    # cross-project duplicate must stay in each project's knowledge base
    superseded = [] if is_global else [i for i in data["superseded_ids"] if i in valid_ids]
    markdown = render_kb_markdown(name, data, n_items=len(items), model=res.model)  # render before any write
    try:
        if superseded:
            conn.execute(
                f"UPDATE knowledge SET status = 'superseded', updated_at = ? WHERE pinned = 0 AND source != 'memory' "
                f"AND id IN ({','.join('?' * len(superseded))})",
                [utcnow_iso(), *superseded],
            )
        conn.execute(
            "INSERT INTO project_kb(project_path, project_name, updated_at, model, knowledge_max_id, n_items, overview, markdown, kb_json) "
            "VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(project_path) DO UPDATE SET project_name=excluded.project_name, "
            "updated_at=excluded.updated_at, model=excluded.model, knowledge_max_id=excluded.knowledge_max_id, "
            "n_items=excluded.n_items, overview=excluded.overview, markdown=excluded.markdown, kb_json=excluded.kb_json",
            (project_path, name, utcnow_iso(), res.model, max_id, len(items), data["overview"], markdown, dumps(data)),
        )
        conn.execute(
            "INSERT INTO analyses(kind, target, started_at, finished_at, model, status, input_chars, chunks, cost_usd, duration_ms) "
            "VALUES ('synthesis', ?, ?, ?, ?, 'done', ?, 1, ?, ?)",
            (project_path, utcnow_iso(), utcnow_iso(), res.model, sum(len(k.get("body") or "") for k in items), res.cost_usd,
             res.duration_ms),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    log.info("synthesized KB for %s (%d items, %d superseded, $%.3f)", name, len(items), len(superseded), res.cost_usd)
    return data


def normalize_kb(data: dict) -> dict:
    """Coerce a model reply into {overview, sections[{title, items[{text, sources[int]}]}], superseded_ids[int]}."""
    def ids(values) -> list[int]:
        out = []
        for v in values if isinstance(values, list) else []:
            try:
                out.append(int(v))
            except (TypeError, ValueError):
                continue
        return out

    sections = []
    raw_sections = data.get("sections") if isinstance(data.get("sections"), list) else []
    for sec in raw_sections:
        if isinstance(sec, str):
            sec = {"title": "Notes", "items": [sec]}
        if not isinstance(sec, dict):
            continue
        items = []
        raw_items = sec.get("items") if isinstance(sec.get("items"), list) else []
        for it in raw_items:
            if isinstance(it, str) and it.strip():
                items.append({"text": it.strip(), "sources": []})
            elif isinstance(it, dict) and str(it.get("text") or "").strip():
                items.append({"text": str(it["text"]).strip(), "sources": ids(it.get("sources"))})
        if items:
            sections.append({"title": str(sec.get("title") or "Notes"), "items": items})
    return {"overview": str(data.get("overview") or "").strip(), "sections": sections,
            "superseded_ids": ids(data.get("superseded_ids"))}


def render_kb_markdown(name: str, data: dict, *, n_items: int, model: str | None, link=None) -> str:
    """Render a KB as Markdown. `link(id) -> str` can turn source ids into links (defaults to [k12])."""
    link = link or (lambda i: f"k{i}")
    lines = [f"# {name}", "", f"_Synthesized from {n_items} knowledge items · {local_str(utcnow_iso())} · {model or ''}_", ""]
    if data.get("overview"):
        lines += ["## Overview", "", data["overview"].strip(), ""]
    for section in data.get("sections") or []:
        items = section.get("items") or []
        if not items:
            continue
        lines += [f"## {section.get('title') or 'Notes'}", ""]
        for it in items:
            src = ", ".join(link(i) for i in it.get("sources") or [] if isinstance(i, int))
            lines.append(f"- {str(it.get('text') or '').strip()}" + (f" <sub>[{src}]</sub>" if src else ""))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def kb_for_path(conn: sqlite3.Connection, cwd: str) -> dict | None:
    """Knowledge base for a working directory (exact project or the nearest enclosing one)."""
    rows = conn.execute("SELECT * FROM project_kb WHERE project_path != ?", (GLOBAL,)).fetchall()
    best = None
    for r in rows:
        p = r["project_path"].rstrip("/")
        if cwd == p or cwd.startswith(p + "/"):
            if best is None or len(p) > len(best["project_path"]):
                best = r
    return dict(best) if best else None


def kb_sections(row: dict) -> list[dict]:
    return (loads(row.get("kb_json"), {}) or {}).get("sections") or []
