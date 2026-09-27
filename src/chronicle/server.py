"""Local dashboard: JSON API + static single-page app (stdlib only, binds to localhost)."""

from __future__ import annotations

import json
import logging
import mimetypes
import re
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from .config import Config
from .db import connect, kv_get
from .search import search_events, search_knowledge, search_sessions
from .synthesize import GLOBAL
from .util import loads, to_iso, utcnow
from .views import project_labels, resolve_session_id, session_record

log = logging.getLogger("chronicle.server")
WEB_DIR = Path(__file__).parent / "web"


def _ui_build() -> str:
    """Content hash of the web assets; open tabs reload themselves when it changes (after an upgrade)."""
    import hashlib

    h = hashlib.sha1()
    for p in sorted(WEB_DIR.glob("*")):
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()[:12]


UI_BUILD = _ui_build()

SESSION_LIST_COLS = (
    "id, source, agent, title, project_name, project_path, started_at, ended_at, duration_s, active_s, n_prompts, "
    "n_tool_calls, n_tool_errors, n_subagents, n_compactions, n_interrupts, lines_added, lines_removed, n_files, "
    "input_tokens + output_tokens + cache_read_tokens + cache_write_tokens AS tokens, est_cost_usd, primary_model, "
    "git_branch, outcome, sentiment, analysis_status, analysis_reason, tags_json, summary, source_present, peak_context"
)
SORTABLE = {"started_at", "ended_at", "active_s", "duration_s", "n_prompts", "n_tool_calls", "tokens", "est_cost_usd",
            "title", "project_name", "lines_added", "n_tool_errors"}


def _local_offset_modifier() -> str:
    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    return f"{int(offset.total_seconds() // 60):+d} minutes"


class Jobs:
    """Tiny in-process registry of background jobs started from the UI."""

    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: dict[str, dict] = {}

    def start(self, name: str, fn) -> bool:
        with self.lock:
            if self.jobs.get(name, {}).get("state") == "running":
                return False
            self.jobs[name] = {"state": "running", "started": time.time(), "message": "", "result": None}

        def run():
            try:
                result = fn(lambda m: self._msg(name, m))
                self._finish(name, "done", result)
            except Exception as exc:  # surfaced in the UI
                log.exception("job %s failed", name)
                self._finish(name, "error", str(exc))

        threading.Thread(target=run, daemon=True).start()
        return True

    def _msg(self, name, message):
        with self.lock:
            self.jobs[name]["message"] = message

    def _finish(self, name, state, result):
        with self.lock:
            self.jobs[name].update(state=state, result=result, finished=time.time())

    def snapshot(self) -> dict:
        with self.lock:
            return {k: dict(v) for k, v in self.jobs.items()}


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.local = threading.local()
        self.jobs = Jobs()
        self._cfg_sig = self._config_sig()

    def _config_sig(self):
        try:
            return self.cfg.config_path.stat().st_mtime_ns
        except OSError:
            return None

    def refresh_config(self) -> None:
        """The dashboard runs for days: pick up config.toml edits (e.g. `chronicle connect codex`) without a restart."""
        from .config import load_config

        sig = self._config_sig()
        if sig != self._cfg_sig:
            self.cfg = load_config(self.cfg.home)
            self._cfg_sig = sig

    @property
    def conn(self):
        conn = getattr(self.local, "conn", None)
        if conn is None:
            conn = connect(self.cfg.db_path)
            self.local.conn = conn
        return conn

    def release(self) -> None:
        """Close this request thread's connection (ThreadingHTTPServer uses a new thread per request)."""
        conn = getattr(self.local, "conn", None)
        if conn is not None:
            try:
                conn.rollback()
                conn.close()
            finally:
                self.local.conn = None

    # ------------------------------------------------------------------ helpers
    def _filters(self, q: dict) -> tuple[str, list]:
        where, params = ["1=1"], []
        if q.get("project"):
            where.append("project_path = ?")
            params.append(q["project"])
        if q.get("agent"):
            where.append("agent = ?")
            params.append(q["agent"])
        if q.get("since"):
            where.append("started_at >= ?")
            params.append(q["since"])
        if q.get("until"):
            where.append("started_at < ?")
            params.append(q["until"])
        return " AND ".join(where), params

    @staticmethod
    def _since_from_days(days: str | None) -> str | None:
        if not days or days == "all":
            return None
        return to_iso(utcnow() - timedelta(days=int(days)))

    # ------------------------------------------------------------------ endpoints
    def overview(self, q: dict) -> dict:
        c = self.conn
        days = q.get("days") or "90"
        since = self._since_from_days(days)
        project = q.get("project") or None
        agent = q.get("agent") or None
        mod = _local_offset_modifier()
        sw, sp = self._filters({"project": project, "since": since, "agent": agent})
        totals = dict(c.execute(
            f"SELECT COUNT(*) sessions, COALESCE(SUM(n_prompts),0) prompts, COALESCE(SUM(n_tool_calls),0) tool_calls, "
            f"COALESCE(SUM(n_tool_errors),0) tool_errors, COALESCE(SUM(active_s),0) active_s, "
            f"COALESCE(SUM(input_tokens+output_tokens+cache_read_tokens+cache_write_tokens),0) tokens, "
            f"COALESCE(SUM(est_cost_usd),0) cost, COALESCE(SUM(lines_added),0) lines_added, "
            f"COALESCE(SUM(lines_removed),0) lines_removed, COUNT(DISTINCT project_path) projects, "
            f"SUM(CASE WHEN analysis_status='done' THEN 1 ELSE 0 END) analyzed, MIN(started_at) first_at "
            f"FROM sessions WHERE {sw}", sp).fetchone())
        kw = "status = 'active'" + (" AND project_path = ?" if project else "")
        kp = [project] if project else []
        if since:
            kw += " AND created_at >= ?"
            kp.append(since)
        totals["knowledge"] = c.execute(f"SELECT COUNT(*) FROM knowledge WHERE {kw}", kp).fetchone()[0]
        # previous period for deltas
        prev = None
        if since:
            prev_since = to_iso(utcnow() - timedelta(days=2 * int(days)))
            pw, pp = self._filters({"project": project, "since": prev_since, "until": since, "agent": agent})
            prev = dict(c.execute(
                f"SELECT COUNT(*) sessions, COALESCE(SUM(n_prompts),0) prompts, COALESCE(SUM(n_tool_calls),0) tool_calls, "
                f"COALESCE(SUM(active_s),0) active_s, COALESCE(SUM(input_tokens+output_tokens+cache_read_tokens+cache_write_tokens),0) tokens, "
                f"COALESCE(SUM(est_cost_usd),0) cost, COALESCE(SUM(lines_added),0) lines_added FROM sessions WHERE {pw}", pp).fetchone())
        # daily series (sessions by start day; tokens/cost by API-call day)
        daily: dict[str, dict] = {}
        for r in c.execute(
            f"SELECT date(started_at, '{mod}') d, COUNT(*) sessions, SUM(n_prompts) prompts, SUM(active_s) active_s, "
            f"SUM(n_tool_calls) tool_calls, SUM(lines_added) lines_added "
            f"FROM sessions WHERE {sw} AND started_at IS NOT NULL GROUP BY d", sp):
            daily.setdefault(r["d"], {}).update(sessions=r["sessions"], prompts=r["prompts"] or 0, active_s=r["active_s"] or 0,
                                                tool_calls=r["tool_calls"] or 0, lines_added=r["lines_added"] or 0)
        aw = ("a.ts IS NOT NULL" + (" AND a.ts >= ?" if since else "") + (" AND s.project_path = ?" if project else "")
              + (" AND s.agent = ?" if agent else ""))
        ap = ([since] if since else []) + ([project] if project else []) + ([agent] if agent else [])
        for r in c.execute(
            f"SELECT date(a.ts, '{mod}') d, SUM(a.input_tokens+a.output_tokens+a.cache_read_tokens+a.cache_write_tokens) tokens, "
            f"SUM(a.cost_usd) cost FROM api_calls a JOIN sessions s ON s.id = a.session_id WHERE {aw} GROUP BY d", ap):
            daily.setdefault(r["d"], {}).update(tokens=r["tokens"] or 0, cost=r["cost"] or 0)
        daily_list = [{"date": d, "sessions": v.get("sessions", 0), "prompts": v.get("prompts", 0),
                       "active_s": v.get("active_s", 0), "tokens": v.get("tokens", 0), "cost": v.get("cost", 0),
                       "tool_calls": v.get("tool_calls", 0), "lines_added": v.get("lines_added", 0)}
                      for d, v in sorted(daily.items()) if d]
        # calendar: up to a year, whatever the period filter (same project scope)
        cal_since = to_iso(utcnow() - timedelta(days=372))
        cw, cp = self._filters({"project": project, "since": cal_since, "agent": agent})
        calendar = [dict(r) for r in c.execute(
            f"SELECT date(started_at, '{mod}') date, COUNT(*) sessions, SUM(active_s) active_s, SUM(n_prompts) prompts "
            f"FROM sessions WHERE {cw} GROUP BY date ORDER BY date", cp)]
        # hour-of-week from human prompts
        ew = ("e.kind = 'prompt' AND e.agent_id = ''" + (" AND e.ts >= ?" if since else "")
              + (" AND s.project_path = ?" if project else "") + (" AND s.agent = ?" if agent else ""))
        hours = [dict(r) for r in c.execute(
            f"SELECT CAST(strftime('%w', e.ts, '{mod}') AS INTEGER) dow, CAST(strftime('%H', e.ts, '{mod}') AS INTEGER) hour, "
            f"COUNT(*) n FROM events e JOIN sessions s ON s.id = e.session_id WHERE {ew} GROUP BY dow, hour", ap)]
        models = [dict(r) for r in c.execute(
            f"SELECT COALESCE(a.model, 'unknown') model, SUM(a.input_tokens+a.output_tokens+a.cache_read_tokens+a.cache_write_tokens) tokens, "
            f"SUM(a.output_tokens) output_tokens, SUM(a.cost_usd) cost, COUNT(*) calls FROM api_calls a JOIN sessions s ON s.id = a.session_id "
            f"WHERE {aw} GROUP BY model ORDER BY cost DESC", ap)]
        tw = ("1=1" + (" AND t.ts >= ?" if since else "") + (" AND s.project_path = ?" if project else "")
              + (" AND s.agent = ?" if agent else ""))
        tools = [dict(r) for r in c.execute(
            f"SELECT t.name, COUNT(*) n, SUM(t.is_error) errors, AVG(t.duration_ms) avg_ms FROM tool_calls t "
            f"JOIN sessions s ON s.id = t.session_id WHERE {tw} GROUP BY t.name ORDER BY n DESC LIMIT 200", ap)]
        labels = project_labels(c)
        projects = [dict(r) | {"label": labels.get(r["project_path"] or "", r["project_name"])} for r in c.execute(
            f"SELECT project_path, project_name, COUNT(*) sessions, SUM(active_s) active_s, SUM(est_cost_usd) cost, "
            f"MAX(started_at) last FROM sessions WHERE {sw} GROUP BY project_path ORDER BY active_s DESC LIMIT 12", sp)]
        outcomes = [dict(r) for r in c.execute(
            f"SELECT COALESCE(outcome, 'not analyzed') outcome, COUNT(*) n FROM sessions WHERE {sw} AND source != 'history' "
            f"GROUP BY 1 ORDER BY n DESC", sp)]
        work_types: dict[str, int] = {}
        for (wt,) in c.execute(f"SELECT work_types_json FROM sessions WHERE {sw} AND work_types_json IS NOT NULL", sp):
            for w in loads(wt, []) or []:
                work_types[w] = work_types.get(w, 0) + 1
        gw, gp = self._filters({"project": project, "since": since})  # every agent, whichever one is selected
        agents = [dict(r) for r in c.execute(
            f"SELECT agent, COUNT(*) sessions, COALESCE(SUM(active_s),0) active_s, COALESCE(SUM(est_cost_usd),0) cost, "
            f"COALESCE(SUM(n_prompts),0) prompts FROM sessions WHERE {gw} GROUP BY agent ORDER BY sessions DESC", gp)]
        recent = self._session_rows(f"{sw}", sp, "started_at DESC", 8)
        kq = "SELECT k.*, s.title session_title FROM knowledge k LEFT JOIN sessions s ON s.id = k.session_id WHERE k.status = 'active' AND k.source = 'analysis'"
        kqp = []
        if project:
            kq += " AND k.project_path = ?"
            kqp.append(project)
        knowledge = [self._k(dict(r)) for r in c.execute(kq + " ORDER BY k.id DESC LIMIT 8", kqp)]
        return {
            "days": days, "project": project, "agent": agent, "agents": agents, "totals": totals, "previous": prev, "daily": daily_list,
            "calendar": calendar, "hours": hours, "models": models, "tools": tools, "projects": projects,
            "outcomes": outcomes, "work_types": sorted(work_types.items(), key=lambda x: -x[1]),
            "recent": recent, "knowledge": knowledge, "status": self.status_small(),
        }

    def _k(self, k: dict) -> dict:
        k["tags"] = loads(k.pop("tags_json", None), []) or []
        return k

    def _session_rows(self, where: str, params: list, order: str, limit: int, offset: int = 0) -> list[dict]:
        rows = []
        for r in self.conn.execute(
            f"SELECT {SESSION_LIST_COLS} FROM sessions WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, limit, offset]):
            d = dict(r)
            d["tags"] = loads(d.pop("tags_json", None), []) or []
            rows.append(d)
        return rows

    def sessions(self, q: dict) -> dict:
        where, params = ["1=1"], []
        if q.get("project"):
            where.append("project_path = ?")
            params.append(q["project"])
        if q.get("outcome"):
            if q["outcome"] == "none":
                where.append("outcome IS NULL")
            else:
                where.append("outcome = ?")
                params.append(q["outcome"])
        if q.get("status"):
            where.append("analysis_status = ?")
            params.append(q["status"])
        if q.get("source"):
            where.append("source = ?")
            params.append(q["source"])
        if q.get("agent"):
            where.append("agent = ?")
            params.append(q["agent"])
        since = q.get("since") or self._since_from_days(q.get("days"))
        if since:
            where.append("started_at >= ?")
            params.append(since.replace("+00:00", "Z"))
        if q.get("until"):
            where.append("started_at < ?")
            params.append(q["until"].replace("+00:00", "Z"))
        if q.get("q"):
            ids = [s["session_id"] for s in search_sessions(self.conn, q["q"], project=q.get("project"), limit=500)]
            if not ids:
                return {"total": 0, "items": []}
            where.append(f"id IN ({','.join('?' * len(ids))})")
            params += ids
        sort = q.get("sort") if q.get("sort") in SORTABLE else "started_at"
        order = "ASC" if q.get("order") == "asc" else "DESC"
        w = " AND ".join(where)
        total = self.conn.execute(f"SELECT COUNT(*) FROM sessions WHERE {w}", params).fetchone()[0]
        limit = min(int(q.get("limit") or 50), 500)
        offset = int(q.get("offset") or 0)
        items = self._session_rows(w, params, f"{sort} {order} NULLS LAST", limit, offset)
        return {"total": total, "items": items}

    def session(self, sid: str) -> dict | None:
        real = resolve_session_id(self.conn, sid)
        if not real:
            return None
        s = session_record(self.conn, real)
        s["api_calls"] = [dict(r) for r in self.conn.execute(
            "SELECT ts, agent_id, model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd "
            "FROM api_calls WHERE session_id = ? ORDER BY ts", (real,))]
        s["markers"] = [dict(r) for r in self.conn.execute(
            "SELECT seq, ts, kind, text FROM events WHERE session_id = ? AND agent_id = '' AND kind IN ('prompt', 'compact', 'interrupt') "
            "ORDER BY seq", (real,))]
        s["tool_stats"] = [dict(r) for r in self.conn.execute(
            "SELECT name, COUNT(*) n, SUM(is_error) errors, AVG(duration_ms) avg_ms, SUM(duration_ms) total_ms "
            "FROM tool_calls WHERE session_id = ? GROUP BY name ORDER BY n DESC", (real,))]
        s["analyses"] = [dict(r) for r in self.conn.execute(
            "SELECT kind, started_at, finished_at, model, status, error, input_chars, chunks, cost_usd, duration_ms "
            "FROM analyses WHERE target = ? ORDER BY id DESC LIMIT 10", (real,))]
        s["agents"] = [{"agent_id": "", "label": "Main thread"}] + [
            {"agent_id": a["agent_id"], "label": f"{a.get('agent_type') or 'agent'}: {a.get('description') or a['agent_id']}"}
            for a in s["subagents"]]
        return s

    def events(self, sid: str, q: dict) -> dict:
        real = resolve_session_id(self.conn, sid)
        if not real:
            return {"total": 0, "items": []}
        agent = q.get("agent", "")
        kinds = [k for k in (q.get("kinds") or "").split(",") if k]
        where, params = ["session_id = ?", "agent_id = ?"], [real, agent]
        if kinds:
            where.append(f"kind IN ({','.join('?' * len(kinds))})")
            params += kinds
        w = " AND ".join(where)
        total = self.conn.execute(f"SELECT COUNT(*) FROM events WHERE {w}", params).fetchone()[0]
        limit = min(int(q.get("limit") or 400), 2000)
        offset = int(q.get("offset") or 0)
        if q.get("around"):  # jump to a specific seq
            pos = self.conn.execute(f"SELECT COUNT(*) FROM events WHERE {w} AND seq < ?", [*params, int(q["around"])]).fetchone()[0]
            offset = max(0, pos - 20)
        items = []
        for r in self.conn.execute(
            f"SELECT seq, ts, role, kind, tool_name, tool_use_id, is_error, text, meta_json FROM events WHERE {w} "
            f"ORDER BY seq LIMIT ? OFFSET ?", [*params, limit, offset]):
            d = dict(r)
            d["meta"] = loads(d.pop("meta_json", None), None)
            items.append(d)
        return {"total": total, "offset": offset, "items": items}

    def projects(self) -> list[dict]:
        labels = project_labels(self.conn)
        # per project: active time in each of the last 12 weeks (oldest first), outcomes and agents
        weekly: dict[str, list[float]] = {}
        for r in self.conn.execute(
                "SELECT project_path, CAST((julianday('now') - julianday(started_at)) / 7 AS INTEGER) wk, SUM(active_s) a "
                "FROM sessions WHERE started_at >= ? GROUP BY project_path, wk", (to_iso(utcnow() - timedelta(days=84)),)):
            if r["wk"] is not None and 0 <= r["wk"] < 12:
                weekly.setdefault(r["project_path"] or "", [0.0] * 12)[11 - r["wk"]] += r["a"] or 0
        outcomes: dict[str, dict] = {}
        for r in self.conn.execute("SELECT project_path, COALESCE(outcome, 'not analyzed') o, COUNT(*) n FROM sessions "
                                   "WHERE source != 'history' GROUP BY 1, 2"):
            outcomes.setdefault(r["project_path"] or "", {})[r["o"]] = r["n"]
        agents: dict[str, dict] = {}
        for r in self.conn.execute("SELECT project_path, agent, COUNT(*) n FROM sessions GROUP BY 1, 2"):
            agents.setdefault(r["project_path"] or "", {})[r["agent"] or "claude"] = r["n"]
        rows = []
        for r in self.conn.execute(
            "SELECT project_path, project_name, COUNT(*) sessions, SUM(n_prompts) prompts, SUM(active_s) active_s, "
            "SUM(est_cost_usd) cost, SUM(input_tokens+output_tokens+cache_read_tokens+cache_write_tokens) tokens, "
            "MIN(started_at) first, MAX(started_at) last, SUM(CASE WHEN analysis_status='done' THEN 1 ELSE 0 END) analyzed "
            "FROM sessions GROUP BY project_path ORDER BY last DESC"):
            d = dict(r)
            d["label"] = labels.get(d["project_path"] or "", d["project_name"])
            d["knowledge"] = self.conn.execute(
                "SELECT COUNT(*) FROM knowledge WHERE project_path = ? AND status = 'active'", (d["project_path"],)).fetchone()[0]
            kb = self.conn.execute("SELECT updated_at, n_items FROM project_kb WHERE project_path = ?", (d["project_path"],)).fetchone()
            d["kb_updated"] = kb["updated_at"] if kb else None
            d["exists"] = bool(d["project_path"]) and Path(d["project_path"]).exists()
            key = d["project_path"] or ""
            d["weekly"], d["outcomes"], d["agents"] = weekly.get(key, [0.0] * 12), outcomes.get(key, {}), agents.get(key, {})
            rows.append(d)
        return rows

    def project(self, path: str) -> dict | None:
        c = self.conn
        if path == GLOBAL:
            kb = c.execute("SELECT * FROM project_kb WHERE project_path = ?", (GLOBAL,)).fetchone()
            return {"project_path": GLOBAL, "label": "Global playbook", "kb": dict(kb) if kb else None,
                    "sessions": [], "knowledge": [], "stats": {}}
        stats = c.execute(
            "SELECT project_name, COUNT(*) sessions, SUM(n_prompts) prompts, SUM(active_s) active_s, SUM(est_cost_usd) cost, "
            "SUM(input_tokens+output_tokens+cache_read_tokens+cache_write_tokens) tokens, SUM(lines_added) lines_added, "
            "SUM(lines_removed) lines_removed, MIN(started_at) first, MAX(started_at) last FROM sessions WHERE project_path = ?",
            (path,)).fetchone()
        if not stats or not stats["sessions"]:
            return None
        from .glossary import glossary_entries
        kb = c.execute("SELECT * FROM project_kb WHERE project_path = ?", (path,)).fetchone()
        labels = project_labels(c)
        return {
            "project_path": path,
            "label": labels.get(path, stats["project_name"]),
            "stats": dict(stats),
            "kb": dict(kb) if kb else None,
            "sessions": self._session_rows("project_path = ?", [path], "started_at DESC", 200),
            "knowledge": [self._k(dict(r)) for r in c.execute(
                "SELECT k.*, s.title session_title FROM knowledge k LEFT JOIN sessions s ON s.id = k.session_id "
                "WHERE k.project_path = ? AND k.status = 'active' ORDER BY k.pinned DESC, k.id DESC LIMIT 300", (path,))],
            "glossary": [{"term": g["term"], "category": g["category"], "definition": g["definition"],
                          "context": next((u["context"] for u in g["usage"] if u["project_path"] == path), "")}
                         for g in glossary_entries(c, project=path)],
            "files": [dict(r) for r in c.execute(
                "SELECT f.path, COUNT(*) sessions, SUM(f.edits + f.writes) edits, SUM(f.lines_added) added, SUM(f.lines_removed) removed "
                "FROM session_files f JOIN sessions s ON s.id = f.session_id WHERE s.project_path = ? AND (f.edits + f.writes) > 0 "
                "GROUP BY f.path ORDER BY edits DESC LIMIT 25", (path,))],
        }

    def knowledge(self, q: dict) -> dict:
        rows = search_knowledge(self.conn, q.get("q") or None, project=q.get("project") or None, kind=q.get("kind") or None,
                                include_inactive=q.get("status") == "all", limit=min(int(q.get("limit") or 200), 1000))
        if q.get("source"):
            rows = [r for r in rows if r["source"] == q["source"]]
        counts = {r["kind"]: r["n"] for r in self.conn.execute(
            "SELECT kind, COUNT(*) n FROM knowledge WHERE status = 'active' GROUP BY kind")}
        return {"items": rows, "counts": counts}

    def search(self, q: dict) -> dict:
        query = q.get("q") or ""
        project = q.get("project") or None
        return {
            "sessions": search_sessions(self.conn, query, project=project, limit=20),
            "knowledge": search_knowledge(self.conn, query, project=project, limit=20),
            "events": search_events(self.conn, query, project=project, limit=60),
        }

    def glossary(self, q: dict) -> dict:
        from .glossary import CATEGORIES, glossary_entries

        items = glossary_entries(self.conn, query=q.get("q") or None, project=q.get("project") or None,
                                 category=q.get("category") or None)
        counts = {r[0]: r[1] for r in self.conn.execute("SELECT category, COUNT(*) FROM glossary GROUP BY category")}
        total = self.conn.execute("SELECT COUNT(*) FROM glossary").fetchone()[0]
        return {"items": items, "counts": counts, "categories": CATEGORIES, "total": total}

    def glossary_terms(self) -> list[dict]:
        """Compact term list the UI uses to link terms wherever they appear."""
        return [{"term": r["term"], "aliases": loads(r["aliases_json"], []) or [], "definition": r["definition"],
                 "category": r["category"]} for r in self.conn.execute("SELECT term, aliases_json, definition, category FROM glossary")]

    def action_glossary(self, path: str | None) -> bool:
        from .glossary import build_glossaries

        def job(progress):
            conn = connect(self.cfg.db_path)
            try:
                targets = [path] if path else [r[0] for r in conn.execute(
                    "SELECT DISTINCT project_path FROM knowledge WHERE status = 'active' AND project_path IS NOT NULL")] + [GLOBAL]
            finally:
                conn.close()
            results = build_glossaries(self.cfg, targets, concurrency=self.cfg.analysis.concurrency + 1, progress=progress)
            built = sum(1 for v in results.values() if isinstance(v, int))
            return f"glossary rebuilt for {built}/{len(targets)} projects"

        return self.jobs.start(f"glossary:{path or 'all'}", job)

    def connectors(self) -> list[dict]:
        from .connectors import all_status

        return all_status(self.cfg, self.conn)

    def action_connector(self, name: str, action: str) -> dict:
        from .config import load_config
        from .connectors import connect, disconnect
        from .install import executable

        if action == "connect":
            actions = connect(self.cfg, name, executable())
        elif action == "disconnect":
            actions = disconnect(self.cfg, name)
        else:
            raise KeyError(action)
        self.cfg = load_config(self.cfg.home)  # the connector rewrote config.toml
        self._cfg_sig = self._config_sig()
        started = self.action_sync() if action == "connect" else False
        return {"actions": actions, "sync_started": started}

    def reviews(self) -> dict:
        from .reviews import review_ready, week_bounds

        items = [dict(r) for r in self.conn.execute(
            "SELECT period, start, end, created_at, model, n_sessions, markdown, stats_json FROM reviews ORDER BY period DESC")]
        for r in items:
            r["stats"] = loads(r.pop("stats_json", None), {}) or {}
        ready, why = review_ready(self.conn)
        return {"items": items, "last_week": week_bounds(None)[0], "current_week": week_bounds("current")[0],
                "auto_ready": ready, "auto_note": why}

    def action_review(self, week: str | None) -> bool:
        from .reviews import generate_review

        def job(progress):
            conn = connect(self.cfg.db_path)
            try:
                progress("writing weekly review…")
                generate_review(conn, self.cfg, week)
            finally:
                conn.rollback()
                conn.close()
            return "review written"

        return self.jobs.start(f"review:{week or 'last'}", job)

    def status_small(self) -> dict:
        from .worker import PAUSE_KEY, count_pending

        pending = count_pending(self.conn, self.cfg)
        return {
            "pending": pending,
            "paused_until": kv_get(self.conn, PAUSE_KEY),
            "last_sync": kv_get(self.conn, "last_sync"),
            "jobs": self.jobs.snapshot(),
            "version": __version__,
            "ui_build": UI_BUILD,
        }

    def status(self) -> dict:
        from .install import hooks_installed, launchd_status, mcp_registered

        c = self.conn
        st = self.status_small()
        st["counts"] = {r["analysis_status"]: r["n"] for r in c.execute(
            "SELECT analysis_status, COUNT(*) n FROM sessions GROUP BY analysis_status")}
        st["analysis_cost"] = c.execute("SELECT COALESCE(SUM(cost_usd),0) FROM analyses").fetchone()[0]
        st["hooks"] = hooks_installed(self.cfg)
        st["launchd"] = launchd_status()
        st["ui_agent"] = launchd_status("com.claude-chronicle.ui")
        st["mcp"] = mcp_registered()
        st["db_size"] = self.cfg.db_path.stat().st_size if self.cfg.db_path.exists() else 0
        st["archive_dir"] = str(self.cfg.archive_dir)
        st["notes_dir"] = str(self.cfg.notes_dir)
        st["config"] = {"model": self.cfg.analysis.model, "auto": self.cfg.analysis.auto,
                        "backfill": self.cfg.analysis.backfill, "max_per_run": self.cfg.analysis.max_per_run}
        st["errors"] = [dict(r) for r in c.execute(
            "SELECT id, title, analysis_reason FROM sessions WHERE analysis_status = 'error' ORDER BY ended_at DESC LIMIT 10")]
        return st

    # ------------------------------------------------------------------ actions
    def action_sync(self) -> bool:
        from .ingest import sync
        from .worker import run_worker

        def job(progress):
            progress("syncing transcripts…")
            conn = connect(self.cfg.db_path)
            try:
                report = sync(self.cfg, conn)
            finally:
                conn.rollback()
                conn.close()
            progress("processing…")
            work = run_worker(self.cfg, progress=progress)
            return f"{report.summary()} | {work.summary()}"

        return self.jobs.start("sync", job)

    def action_analyze(self, sid: str) -> bool:
        from .worker import run_worker

        real = resolve_session_id(self.conn, sid)
        if not real:
            return False

        def job(progress):
            report = run_worker(self.cfg, session_ids=[real], synthesize=True, export=True, progress=progress, wait=True)
            if report.failed:
                raise RuntimeError(report.failed[0][1])
            return report.summary()

        return self.jobs.start(f"analyze:{real}", job)

    def action_synthesize(self, path: str) -> bool:
        from .synthesize import synthesize_project

        def job(progress):
            conn = connect(self.cfg.db_path)
            try:
                progress("synthesizing…")
                synthesize_project(conn, self.cfg, path)
            finally:
                conn.rollback()
                conn.close()
            return "done"

        return self.jobs.start(f"synthesize:{path}", job)

    def action_knowledge(self, kid: int, body: dict) -> bool:
        sets, params = [], []
        if body.get("status") in ("active", "dismissed", "superseded"):
            sets.append("status = ?")
            params.append(body["status"])
        if "pinned" in body:
            sets.append("pinned = ?")
            params.append(1 if body["pinned"] else 0)
        if not sets:
            return False
        self.conn.execute(f"UPDATE knowledge SET {', '.join(sets)}, updated_at = ? WHERE id = ?", [*params, to_iso(utcnow()), kid])
        self.conn.commit()
        return True


def make_handler(app: App, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = f"chronicle/{__version__}"

        def log_message(self, fmt, *args):  # quiet
            log.debug("%s - %s", self.address_string(), fmt % args)

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def _json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _static(self, rel: str):
            rel = rel.lstrip("/") or "index.html"
            path = (WEB_DIR / rel).resolve()
            if not path.is_relative_to(WEB_DIR.resolve()) or not path.is_file():
                path = WEB_DIR / "index.html"
            body = path.read_bytes()
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                app.refresh_config()
                return self._get()
            finally:
                app.release()

        def do_POST(self):
            try:
                app.refresh_config()
                return self._post()
            finally:
                app.release()

        def _get(self):
            if not self._host_ok():
                return self._json({"error": "forbidden host"}, 403)
            url = urlparse(self.path)
            q = {k: v[-1] for k, v in parse_qs(url.query).items()}
            p = url.path
            try:
                if p == "/api/overview":
                    return self._json(app.overview(q))
                if p == "/api/sessions":
                    return self._json(app.sessions(q))
                m = re.fullmatch(r"/api/sessions/([\w-]+)", p)
                if m:
                    s = app.session(m.group(1))
                    return self._json(s) if s else self._json({"error": "not found"}, 404)
                m = re.fullmatch(r"/api/sessions/([\w-]+)/events", p)
                if m:
                    return self._json(app.events(m.group(1), q))
                if p == "/api/projects":
                    return self._json(app.projects())
                if p == "/api/project":
                    proj = app.project(unquote(q.get("path", "")))
                    return self._json(proj) if proj else self._json({"error": "not found"}, 404)
                if p == "/api/knowledge":
                    return self._json(app.knowledge(q))
                if p == "/api/search":
                    return self._json(app.search(q))
                if p == "/api/status":
                    return self._json(app.status())
                if p == "/api/reviews":
                    return self._json(app.reviews())
                if p == "/api/glossary":
                    return self._json(app.glossary(q))
                if p == "/api/connectors":
                    return self._json(app.connectors())
                if p == "/api/glossary/terms":
                    return self._json(app.glossary_terms())
                if p == "/api/jobs":
                    return self._json(app.status_small())
                if p.startswith("/api/"):
                    return self._json({"error": "not found"}, 404)
                return self._static(p)
            except BrokenPipeError:
                pass
            except Exception as exc:
                log.exception("GET %s failed", p)
                return self._json({"error": str(exc)}, 500)

        def _post(self):
            if not self._host_ok() or self.headers.get("X-Chronicle") != "1":
                return self._json({"error": "forbidden"}, 403)
            length = int(self.headers.get("Content-Length") or 0)
            body = {}
            if length:
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return self._json({"error": "bad json"}, 400)
            p = urlparse(self.path).path
            try:
                if p == "/api/sync":
                    return self._json({"started": app.action_sync()})
                m = re.fullmatch(r"/api/sessions/([\w-]+)/analyze", p)
                if m:
                    return self._json({"started": app.action_analyze(m.group(1))})
                m = re.fullmatch(r"/api/connectors/(\w+)/(connect|disconnect)", p)
                if m:
                    try:
                        return self._json(app.action_connector(m.group(1), m.group(2)))
                    except KeyError:
                        return self._json({"error": "unknown connector"}, 404)
                if p == "/api/glossary/rebuild":
                    return self._json({"started": app.action_glossary(body.get("path") or None)})
                if p == "/api/review":
                    return self._json({"started": app.action_review(body.get("week"))})
                if p == "/api/synthesize":
                    return self._json({"started": app.action_synthesize(body.get("path") or GLOBAL)})
                m = re.fullmatch(r"/api/knowledge/(\d+)", p)
                if m:
                    return self._json({"ok": app.action_knowledge(int(m.group(1)), body)})
                return self._json({"error": "not found"}, 404)
            except Exception as exc:
                log.exception("POST %s failed", p)
                return self._json({"error": str(exc)}, 500)

    return Handler


def serve(cfg: Config, host: str | None = None, port: int | None = None, open_browser: bool = False) -> None:
    host = host or cfg.server_host
    port = port or cfg.server_port
    app = App(cfg)
    httpd = ThreadingHTTPServer((host, port), make_handler(app, port))
    url = f"http://127.0.0.1:{port}/"
    print(f"Chronicle dashboard: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
