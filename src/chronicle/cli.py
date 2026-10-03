"""Command line interface: `chronicle <command>`."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__


def _cfg():
    from .config import load_config

    cfg = load_config()
    cfg.ensure_dirs()
    return cfg


def _conn(cfg):
    from .db import connect

    return connect(cfg.db_path)


def _console():
    from rich.console import Console

    return Console()


def _since(value: str | None) -> str | None:
    """'7d', '12h', '2w' or an ISO date -> ISO UTC timestamp."""
    import re
    from datetime import timedelta

    from .util import parse_ts, to_iso, utcnow

    if not value:
        return None
    m = re.fullmatch(r"(\d+)([hdw])", value.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"h": timedelta(hours=n), "d": timedelta(days=n), "w": timedelta(weeks=n)}[unit]
        return to_iso(utcnow() - delta)
    dt = parse_ts(value)
    return to_iso(dt) if dt else None


# ---------------------------------------------------------------------------- commands
def cmd_hook(args) -> int:
    from .hooks import hook_main

    return hook_main(args.event)


def cmd_ingest_session(args) -> int:
    """Used by the SessionEnd hook (runs detached): ingest one transcript, then process the queue."""
    from pathlib import Path

    from .ingest import sync
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    if cfg.is_spoke:
        return _push(cfg, quiet=True)
    conn = _conn(cfg)
    path = Path(args.transcript).expanduser() if args.transcript else None
    if path and path.exists():
        sync(cfg, conn, only=path, ended=args.ended)
    else:
        sync(cfg, conn)
    conn.close()
    if args.work:
        from .worker import run_worker

        run_worker(cfg, wait=False)
    return 0


def cmd_sync(args) -> int:
    from .ingest import sync
    from .notify import release_check_safely
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir, verbose=args.verbose)
    release_check_safely(cfg)  # [updates] notify: at most one PyPI request a day, one notification per release
    if cfg.is_spoke:  # the hub records and analyzes; this computer only sends it files
        return _push(cfg, quiet=args.quiet)
    conn = _conn(cfg)
    report = sync(cfg, conn, force=args.force)
    if not args.quiet:
        print(f"sync: {report.summary()}")
        for err in report.errors[:10]:
            print(f"  ! {err}", file=sys.stderr)
    conn.close()
    if args.work:
        from .worker import run_worker

        work = run_worker(cfg, progress=None if args.quiet else (lambda m: print(f"  {m}")))
        if not args.quiet:
            print(f"work: {work.summary()}")
    return 0


def cmd_work(args) -> int:
    from .util import setup_logging
    from .worker import run_worker

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    if cfg.is_spoke:
        print(f"This computer sends its sessions to the hub at {cfg.hub_url}, which analyzes them.")
        return 0
    report = run_worker(cfg, max_analyses=args.limit, analyze=not args.no_analyze, synthesize=not args.no_synthesize,
                        export=not args.no_export, force=args.force, model=args.model, wait=True,
                        progress=lambda m: print(f"  {m}"))
    print(report.summary())
    for sid, err in report.failed:
        print(f"  ! {sid[:8]}: {err[:200]}", file=sys.stderr)
    return 0 if not report.failed else 1


def cmd_analyze(args) -> int:
    from .util import human_cost, setup_logging
    from .views import resolve_session_id
    from .worker import pending_sessions, run_worker

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    conn = _conn(cfg)
    ids: list[str] = []
    for ref in args.sessions:
        sid = resolve_session_id(conn, ref)
        if not sid:
            print(f"no unique session matches {ref!r}", file=sys.stderr)
            return 2
        ids.append(sid)
    if args.all or args.pending:
        if args.all and args.force:
            conn.execute("UPDATE sessions SET analysis_status = 'pending', analysis_attempts = 0 "
                         "WHERE source != 'history' AND analysis_status IN ('done','error','stale')")
            conn.commit()
        ids += pending_sessions(conn, cfg, args.limit or 100_000)
    if not ids:
        print("nothing to analyze (use SESSION ids, --pending or --all)")
        return 0
    from .llm import make_runner

    if args.backend:
        cfg.analysis.backend = args.backend
    runner = make_runner(cfg)
    if args.dry_run:
        from .digest import build_digest

        total = 0
        for sid in ids:
            header, d = build_digest(conn, sid, cfg.analysis.chunk_chars)
            total += d.chars
            print(f"{sid[:8]}  level {d.level}  {d.chars:>9,} chars  {len(d.chunks)} chunk(s)")
        print(f"{len(ids)} session(s), {total:,} chars (~{total // 4:,} input tokens) with {runner.label} "
              f"({runner.model_label(args.model)})")
        return 0
    conn.close()
    if args.concurrency:
        cfg.analysis.concurrency = args.concurrency
    print(f"analyzing {len(ids)} session(s) with {runner.label} ({runner.model_label(args.model)})…")
    report = run_worker(cfg, session_ids=ids, model=args.model, synthesize=not args.no_synthesize, force=True, wait=True,
                        progress=lambda m: print(f"  {m}"))
    print(f"{report.summary()} · analysis cost {human_cost(report.cost_usd)}")
    for sid, err in report.failed:
        print(f"  ! {sid[:8]}: {err[:300]}", file=sys.stderr)
    return 0 if not report.failed else 1


def cmd_synthesize(args) -> int:
    from .synthesize import GLOBAL, projects_needing_synthesis, synthesize_project
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    conn = _conn(cfg)
    targets = []
    if args.project:
        row = conn.execute("SELECT project_path FROM sessions WHERE project_path = ? OR project_name = ? LIMIT 1",
                           (args.project, args.project)).fetchone()
        targets.append(row[0] if row else args.project)
    if args.all:
        targets += projects_needing_synthesis(conn, cfg, force=True)
    if args.global_ or args.all:
        targets.append(GLOBAL)
    if not targets:
        targets = projects_needing_synthesis(conn, cfg)
    for t in dict.fromkeys(targets):
        print(f"synthesizing {t}…")
        try:
            data = synthesize_project(conn, cfg, t)
            print(f"  {sum(len(s.get('items') or []) for s in data.get('sections') or [])} bullets, "
                  f"{len(data.get('superseded_ids') or [])} items superseded")
        except Exception as exc:
            conn.rollback()  # never carry a half-written transaction (and its lock) into the next target
            print(f"  ! {exc}", file=sys.stderr)
    return 0


def cmd_sessions(args) -> int:
    from rich.table import Table

    from .util import human_cost, human_count, human_duration, local_str

    cfg = _cfg()
    conn = _conn(cfg)
    where, params = ["1=1"], []
    if args.project:
        where.append("(project_path = ? OR project_name = ?)")
        params += [args.project, args.project]
    since = _since(args.since)
    if since:
        where.append("started_at >= ?")
        params.append(since)
    if args.status:
        where.append("analysis_status = ?")
        params.append(args.status)
    rows = conn.execute(
        f"SELECT id, started_at, project_name, title, n_prompts, n_tool_calls, active_s, "
        f"input_tokens+output_tokens+cache_read_tokens+cache_write_tokens tokens, est_cost_usd, outcome, analysis_status, source "
        f"FROM sessions WHERE {' AND '.join(where)} ORDER BY started_at DESC LIMIT ?", [*params, args.limit]).fetchall()
    if args.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1))
        return 0
    t = Table(show_lines=False, header_style="bold", pad_edge=False)
    for col, kw in [("id", {}), ("started", {}), ("project", {}), ("title", {"max_width": 60}), ("prompts", {"justify": "right"}),
                    ("tools", {"justify": "right"}), ("active", {"justify": "right"}), ("tokens", {"justify": "right"}),
                    ("est.$", {"justify": "right"}), ("outcome", {})]:
        t.add_column(col, **kw)
    for r in rows:
        outcome = r["outcome"] or ("history" if r["source"] == "history" else f"[dim]{r['analysis_status']}[/dim]")
        t.add_row(r["id"][:8], local_str(r["started_at"], "%m-%d %H:%M"), r["project_name"] or "-", r["title"] or "",
                  str(r["n_prompts"] or 0), str(r["n_tool_calls"] or 0), human_duration(r["active_s"]),
                  human_count(r["tokens"]), human_cost(r["est_cost_usd"]), outcome)
    _console().print(t)
    return 0


def cmd_show(args) -> int:
    from rich.markdown import Markdown

    from .views import resolve_session_id, session_markdown, session_record

    cfg = _cfg()
    conn = _conn(cfg)
    sid = resolve_session_id(conn, args.session)
    if not sid:
        print(f"no unique session matches {args.session!r}", file=sys.stderr)
        return 2
    s = session_record(conn, sid)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=1, default=str))
        return 0
    if args.transcript:
        from .util import local_str

        for r in conn.execute("SELECT ts, kind, tool_name, is_error, text FROM events WHERE session_id = ? AND agent_id = '' "
                              "AND kind IN ('prompt','text','tool_use','command','interrupt','compact') ORDER BY seq", (sid,)):
            label = {"prompt": "[bold cyan]USER[/]", "text": "[bold]CLAUDE[/]", "tool_use": "[dim]  →[/]",
                     "command": "[magenta]CMD[/]", "interrupt": "[red]INTERRUPT[/]", "compact": "[yellow]COMPACT[/]"}[r["kind"]]
            text = r["text"] if r["kind"] in ("prompt", "text") else r["text"][:200]
            _console().print(f"{label} [dim]{local_str(r['ts'], '%H:%M')}[/] ", end="")
            _console().print(text, markup=False, highlight=False)
        return 0
    md = session_markdown(s)
    if args.markdown:
        print(md)
    else:
        _console().print(Markdown(md))
    return 0


def cmd_search(args) -> int:
    from rich.markup import escape

    from .search import search_knowledge, search_sessions
    from .util import local_str

    cfg = _cfg()
    conn = _conn(cfg)
    console = _console()
    query = " ".join(args.query)
    if not args.sessions_only:
        ks = search_knowledge(conn, query, project=args.project, limit=args.limit)
        if ks:
            console.print(f"[bold]Knowledge[/] ({len(ks)})")
            for k in ks:
                console.print(f"  [cyan]{k['kind']:<10}[/] [bold]{k['title']}[/]  [dim]{k.get('project_name') or ''} "
                              f"{(k.get('session_id') or '')[:8]}[/]", highlight=False)
            console.print()
    if not args.knowledge_only:
        ss = search_sessions(conn, query, project=args.project, limit=args.limit)
        console.print(f"[bold]Sessions[/] ({len(ss)})")
        for s in ss:
            console.print(f"  [green]{s['session_id'][:8]}[/] {local_str(s['started_at'], '%Y-%m-%d')} "
                          f"[bold]{s['title']}[/] [dim]{s['project_name']} · {s['hits']} hits[/]", highlight=False)
            for sn in s["snippets"][:2]:
                console.print(f"      [dim]{sn['kind']}:[/] {escape(sn['text'])}", highlight=False)
    return 0


def cmd_knowledge(args) -> int:
    from .ladder import stage_label
    from .search import search_knowledge

    cfg = _cfg()
    conn = _conn(cfg)
    console = _console()
    rows = search_knowledge(conn, args.query, project=args.project, kind=args.kind, limit=args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
        return 0
    for k in rows:
        console.print(f"[cyan]{k['kind']}[/] [bold]{k['title']}[/] [dim]({k.get('project_name') or '-'}, {stage_label(k)}, "
                      f"{k.get('confidence') or '-'}, {(k.get('session_id') or k['source'])[:8]})[/]", highlight=False)
        if not args.brief:
            console.print(f"  {k.get('body') or ''}\n", highlight=False, markup=False)
    if not rows:
        print("no knowledge found")
    return 0


def cmd_projects(args) -> int:
    from rich.table import Table

    from .util import human_cost, human_duration, local_str
    from .views import project_labels

    cfg = _cfg()
    conn = _conn(cfg)
    labels = project_labels(conn)
    t = Table(header_style="bold")
    for col in ("project", "sessions", "active", "est.$", "knowledge", "KB", "last"):
        t.add_column(col, justify="right" if col in ("sessions", "active", "est.$", "knowledge") else "left")
    for r in conn.execute(
        "SELECT project_path, COUNT(*) n, SUM(active_s) a, SUM(est_cost_usd) c, MAX(started_at) last FROM sessions "
        "GROUP BY project_path ORDER BY last DESC"):
        k = conn.execute("SELECT COUNT(*) FROM knowledge WHERE project_path = ? AND status='active'", (r["project_path"],)).fetchone()[0]
        kb = conn.execute("SELECT updated_at FROM project_kb WHERE project_path = ?", (r["project_path"],)).fetchone()
        t.add_row(labels.get(r["project_path"] or "", "?"), str(r["n"]), human_duration(r["a"]), human_cost(r["c"]), str(k),
                  local_str(kb[0], "%m-%d") if kb else "-", local_str(r["last"], "%Y-%m-%d"))
    _console().print(t)
    return 0


def cmd_stats(args) -> int:
    from rich.table import Table

    from .util import human_cost, human_count, human_duration

    cfg = _cfg()
    conn = _conn(cfg)
    since = _since(args.since) or "0000"
    t = conn.execute(
        "SELECT COUNT(*) n, SUM(n_prompts) p, SUM(n_tool_calls) tc, SUM(n_tool_errors) te, SUM(active_s) a, "
        "SUM(input_tokens+output_tokens+cache_read_tokens+cache_write_tokens) tok, SUM(est_cost_usd) c, SUM(lines_added) la, "
        "SUM(lines_removed) lr, SUM(n_subagents) sa, COUNT(DISTINCT project_path) pr FROM sessions WHERE started_at >= ?",
        (since,)).fetchone()
    console = _console()
    console.print(f"[bold]{t['n']}[/] sessions in [bold]{t['pr']}[/] projects · {t['p'] or 0} prompts · "
                  f"{human_count(t['tc'])} tool calls ({t['te'] or 0} failed) · {human_duration(t['a'])} active · "
                  f"{human_count(t['tok'])} tokens · est. {human_cost(t['c'])} · +{t['la'] or 0}/−{t['lr'] or 0} lines · "
                  f"{t['sa'] or 0} subagents", highlight=False)
    tools = Table(title="Top tools", header_style="bold")
    for col in ("tool", "calls", "errors"):
        tools.add_column(col, justify="left" if col == "tool" else "right")
    for r in conn.execute(
        "SELECT name, COUNT(*) n, SUM(is_error) e FROM tool_calls t JOIN sessions s ON s.id = t.session_id "
        "WHERE s.started_at >= ? GROUP BY name ORDER BY n DESC LIMIT 12", (since,)):
        tools.add_row(r["name"], str(r["n"]), str(r["e"] or 0))
    models = Table(title="Models", header_style="bold")
    for col in ("model", "tokens", "est.$"):
        models.add_column(col, justify="left" if col == "model" else "right")
    for r in conn.execute(
        "SELECT a.model, SUM(a.input_tokens+a.output_tokens+a.cache_read_tokens+a.cache_write_tokens) tok, SUM(a.cost_usd) c "
        "FROM api_calls a JOIN sessions s ON s.id = a.session_id WHERE s.started_at >= ? GROUP BY a.model ORDER BY c DESC",
        (since,)):
        models.add_row(r["model"] or "?", human_count(r["tok"]), human_cost(r["c"]))
    console.print(tools)
    console.print(models)
    return 0


def cmd_status(args) -> int:
    from .db import kv_get
    from .install import UI_LABEL, hooks_installed, launchd_status, mcp_registered, statusline_installed
    from .statusline import WINDOW_LABEL, plan_usage
    from .llm import make_runner
    from .util import human_cost, local_str
    from .worker import PAUSE_KEY, QUEUE_REASON_LABEL, count_pending

    cfg = _cfg()
    conn = _conn(cfg)
    console = _console()
    ok = lambda b: "[green]✓[/]" if b else "[red]✗[/]"  # noqa: E731
    hooks = hooks_installed(cfg)
    ld = launchd_status()
    counts = {r[0]: r[1] for r in conn.execute("SELECT analysis_status, COUNT(*) FROM sessions GROUP BY 1")}
    pending = count_pending(conn, cfg)
    spent = conn.execute("SELECT COALESCE(SUM(cost_usd),0) FROM analyses").fetchone()[0]
    console.print(f"[bold]Chronicle[/] · home {cfg.home}")
    from .hub import last_push, read_token

    if cfg.is_spoke:
        last = last_push(cfg)
        console.print(f"  sends its sessions to the hub at {cfg.hub_url}"
                      f" (last push: {local_str(last['at']) + ' · ' + last['summary'] if last else 'never'})", highlight=False)
    elif read_token(cfg):
        others = conn.execute("SELECT COUNT(*) FROM machines WHERE role = 'spoke'").fetchone()[0]
        console.print(f"  hub for {others} other computer{'s' * (others != 1)} (`chronicle hub status`)")
    console.print(f"  {ok(hooks.get('SessionEnd'))} SessionEnd hook   {ok(hooks.get('SessionStart'))} SessionStart context hook"
                  f"{' (optional)' if not cfg.inject_session_start else ''}")
    plan = plan_usage(conn)
    limits = " · ".join(f"{WINDOW_LABEL[k]} {v['used_pct']:.0f}% (resets {local_str(v['resets_at'], '%m-%d %H:%M')})"
                        for k, v in ((plan or {}).get("limits") or {}).items())
    console.print(f"  {ok(statusline_installed(cfg))} status-line usage collector"
                  + (f": plan limits {limits}, as of {local_str(plan['as_of'])}" if limits
                     else " (optional: chronicle install --statusline)" if not statusline_installed(cfg)
                     else ": no plan limits seen yet (Pro and Max plans only)"), highlight=False)
    ui = launchd_status(UI_LABEL)
    console.print(f"  {ok(ld.get('loaded'))} background sync agent (runs: {ld.get('runs', '-')}, last exit: {ld.get('last_exit', '-')})")
    console.print(f"  {ok(ui.get('loaded'))} dashboard agent: http://127.0.0.1:{cfg.server_port}/")
    runner = make_runner(cfg)
    console.print(f"  {ok(mcp_registered())} MCP server registered   {ok(runner.available())} analysis by {runner.label}: "
                  f"{runner.bin or f'`{runner.cli.split()[0]}` not found'}")
    console.print(f"  sessions: {sum(counts.values())} · " + " · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    console.print(f"  analysis queue: {pending['ready']} ready now, {pending['queued']} queued in all, {pending['held']} held · "
                  f"model {runner.model_label()} · auto={'on' if cfg.analysis.auto else 'off'} · spent {human_cost(spent)}")
    if pending["reasons"]:
        console.print("    waiting because: " + " · ".join(f"{QUEUE_REASON_LABEL.get(k, k)}: {v}" for k, v in sorted(pending["reasons"].items())))
    if pending["block"]:
        console.print(f"    [yellow]{pending['block']}[/]", highlight=False)
    paused = kv_get(conn, PAUSE_KEY)
    if paused:
        console.print(f"  analysis paused until {local_str(paused)}")
    console.print(f"  last sync: {local_str(kv_get(conn, 'last_sync'))} · db {cfg.db_path.stat().st_size / 1e6:.0f} MB · notes {cfg.notes_dir}")
    for r in conn.execute("SELECT id, analysis_reason FROM sessions WHERE analysis_status='error' ORDER BY ended_at DESC LIMIT 5"):
        console.print(f"  [red]error[/] {r['id'][:8]}: {(r['analysis_reason'] or '')[:160]}", highlight=False)
    return 0


def _ask(question: str, default: bool) -> bool:
    try:
        answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except EOFError:
        return default
    return default if not answer else answer.startswith("y")


def _setup_choices(cfg, conn, console, *, ask) -> tuple[list[str], list[str]]:
    """Show the agents found on this machine; return (sources to connect, MCP-only clients to register)."""
    from .connectors import all_status, mcp_clients_status
    from .install import hooks_installed

    statuses = all_status(cfg, conn)
    sources = [s for s in statuses if s["name"] != "codex-cloud"]
    cloud = next(s for s in statuses if s["name"] == "codex-cloud")
    clients = mcp_clients_status()
    claude_hooked = bool(hooks_installed(cfg).get("SessionEnd"))
    connected = lambda s: claude_hooked if s["name"] == "claude" else s["connected"]  # noqa: E731

    console.print("[bold]Coding agents on this machine[/]")
    for s in sources:
        state = ("[green]connected[/]" if connected(s) else "[yellow]found[/]" if s["detected"] else "[dim]not installed[/]")
        count = f" · {s['on_disk']} session{'s' * (s['on_disk'] != 1)} on disk" if s["detected"] else ""
        console.print(f"  {s['label']:<16} {state}{count}", highlight=False)
    for c in clients:
        if c["detected"]:
            state = "[green]MCP server added[/]" if c["registered"] else "[yellow]found[/] [dim](MCP tools only, not recorded)[/]"
            console.print(f"  {c['label']:<16} {state}", highlight=False)
    console.print()

    picked = []
    for s in sources:
        if connected(s):
            picked.append(s["name"])  # re-run connect so paths stay current
        elif s["detected"] and ask(f"Record {s['label']} sessions?", True):
            picked.append(s["name"])
    if "codex" in picked and not cloud["connected"] and cloud["detected"]:
        if ask("Also record Codex Cloud tasks? (lists them online through the codex CLI on every sync)", False):
            picked.append("codex-cloud")
    elif cloud["connected"]:
        picked.append("codex-cloud")
    mcp = [c["name"] for c in clients if c["detected"] and not c["registered"]
           and ask(f"Give {c['label']} Chronicle's MCP tools (search your past sessions)?", True)]
    return picked, mcp


def _wait_for_port(port: int, seconds: float = 8.0) -> bool:
    import socket
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


ANALYZE_NEWEST = 20  # what "analyze the newest now" means at install: enough for a first Glossary and Map in minutes
STAGE_SECONDS = {"session": 45, "synthesis": 85, "glossary": 55, "themes": 70}  # typical call times, until measured here


def _about(minutes: float) -> str:
    if minutes < 60:
        return f"about {max(1, round(minutes))} min"
    if minutes < 48 * 60:
        return f"about {round(minutes / 60)} h"
    return f"about {round(minutes / 1440)} days"


def _estimate_minutes(conn, cfg, ids: list[str]) -> float:
    """Rough wall time to analyze `ids` now, then build the knowledge bases, glossaries and Map themes they feed."""
    import math

    secs = dict(STAGE_SECONDS)
    secs.update({r[0]: r[1] for r in conn.execute(
        "SELECT kind, AVG(duration_ms) / 1000.0 FROM analyses WHERE status = 'done' AND duration_ms > 0 GROUP BY kind")
        if r[0] in secs and r[1]})
    project_of = dict(conn.execute("SELECT id, project_path FROM sessions"))
    projects = len({project_of.get(i) for i in ids}) + 1  # + the cross-project playbook
    conc = max(1, cfg.analysis.concurrency)
    return (math.ceil(len(ids) / conc) * secs["session"] + projects * secs["synthesis"]
            + math.ceil(projects / conc) * secs["glossary"] + 2 * secs["themes"]) / 60


def _analysis_step(cfg, conn, console, analyzer, *, interactive: bool, choice: str | None, background_sync: bool,
                   interval: int) -> tuple[list[str], int, str]:
    """Explain what analysis builds (knowledge, then the Glossary and the Map) and when it happens; ask whether to
    analyze now. Returns (sessions to analyze now, sessions waiting, how the rest gets analyzed)."""
    import math

    from .worker import pending_sessions

    ids = pending_sessions(conn, cfg, 100_000)
    n = len(ids)
    if background_sync and cfg.analysis.auto:
        later = "in the background"
    elif not cfg.analysis.auto:
        later = "when you run `chronicle analyze --pending` (analysis.auto is off)"
    else:
        later = "when you run `chronicle analyze --pending` (nothing runs in the background)"
    if not n:
        return [], 0, later
    console.print("\n[bold]Analysis: knowledge, the Glossary and the Map[/]")
    console.print(f"  Chronicle reads each session through your {analyzer.label} login and pulls out what was learned "
                  "(fixes, decisions, gotchas, commands). That knowledge builds each project's knowledge base, then the "
                  "Glossary, then the Map. Until sessions are analyzed, the Glossary and the Map stay empty.",
                  highlight=False)
    console.print(f"  {n} past session{'s' * (n != 1)} waiting. Each is one {analyzer.label} call and counts toward "
                  "your plan's usage.", highlight=False)
    if later == "in the background":
        runs = math.ceil(n / max(1, cfg.analysis.max_per_run))
        console.print(f"  Later: in the background, {cfg.analysis.max_per_run} every {interval} min, so all of them in "
                      f"{_about(runs * interval)}. A project's glossary is built once all its sessions are analyzed.",
                      highlight=False)
    else:
        console.print(f"  Later: {later}.", highlight=False)

    if choice is None and not interactive:
        choice = "later"
    if choice is None:
        newest = ids[:ANALYZE_NEWEST]
        if n <= ANALYZE_NEWEST:
            choice = "all" if _ask(f"Analyze {'them' if n > 1 else 'it'} now and show the progress? "
                                   f"({_about(_estimate_minutes(conn, cfg, ids))})", True) else "later"
        else:
            try:
                answer = input(f"Analyze now and show the progress? [N]ewest {len(newest)} "
                               f"({_about(_estimate_minutes(conn, cfg, newest))}) / [a]ll {n} "
                               f"({_about(_estimate_minutes(conn, cfg, ids))}) / [l]ater: ").strip().lower()
            except EOFError:
                answer = ""
            choice = ("all" if answer.startswith("a") else "later" if answer.startswith(("l", "no", "s"))
                      else answer if answer.isdigit() else str(ANALYZE_NEWEST))
    if choice == "all":
        return ids, n, later
    if choice.isdigit():
        return ids[:int(choice)], n, later
    return [], n, later


class _StageProgress:
    """Draws the worker's progress messages as one bar per stage, so the Glossary and the Map are seen being built."""

    STAGES = {"analyzing": "Sessions", "synthesizing": "Knowledge bases", "glossary": "Glossary", "themes": "Map themes",
              "writing weekly review": "Weekly review"}

    def __init__(self, bar):
        import threading

        self.bar, self.task, self.stage, self.count = bar, None, None, 0
        self.lock = threading.Lock()  # sessions report from several analysis threads at once

    def __call__(self, message: str) -> None:
        with self.lock:
            self._update(message)

    def _update(self, message: str) -> None:
        from .synthesize import GLOBAL
        from .util import PROGRESS_RE

        stage = next((s for s in self.STAGES if message.startswith(s)), None)
        if (stage is None and self.task is None) or message.startswith("stopping"):
            self.bar.console.print(f"  {message}", highlight=False)
            return
        if stage and stage != self.stage:
            self.finish()
            self.stage, self.count = stage, 0
            self.task = self.bar.add_task(self.STAGES[stage], total=None, detail="")
        m = PROGRESS_RE.search(message)
        if m:
            done, total = (int(g.replace(",", "")) for g in m.groups())
            self.bar.update(self.task, completed=done, total=total, detail=f"{done} of {total}")
        elif stage == "synthesizing":
            self.count += 1
            name = message.removeprefix("synthesizing ").rstrip("…")
            self.bar.update(self.task, detail=f"{self.count}: {'global playbook' if name == GLOBAL else name}")

    def finish(self) -> None:
        if self.task is not None:
            total = next(t.total for t in self.bar.tasks if t.id == self.task) or 1
            self.bar.update(self.task, total=total, completed=total,
                            detail=f"{self.count} built" if self.stage == "synthesizing" else "done")


def _analyze_now(cfg, console, ids: list[str], waiting: int, later: str) -> str:
    """Analyze `ids` with live progress, then build the knowledge bases, glossaries and Map themes they feed.
    Returns the line for the closing summary about what is left."""
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

    from .worker import run_worker

    console.print(f"\nAnalyzing {len(ids)} session{'s' * (len(ids) != 1)}. Ctrl-C stops; what is left is analyzed {later}.",
                  highlight=False)
    try:
        with Progress(SpinnerColumn(), TextColumn("{task.description:<16}"), BarColumn(), TextColumn("{task.fields[detail]}"),
                      TimeElapsedColumn(), console=console) as bar:
            stages = _StageProgress(bar)
            report = run_worker(cfg, session_ids=ids, force=True, wait=True, progress=stages)
            stages.finish()
    except KeyboardInterrupt:
        console.print(f"[yellow]Stopped.[/] The rest is analyzed {later}; the Glossary and the Map are built after.",
                      highlight=False)
        return f"Sessions still waiting for analysis are analyzed {later}."
    conn = _conn(cfg)
    terms = conn.execute("SELECT COUNT(*) FROM glossary").fetchone()[0]
    themed = conn.execute("SELECT COUNT(DISTINCT category) FROM glossary_themes").fetchone()[0]
    conn.close()
    console.print(f"• analyzed {len(report.analyzed)} session{'s' * (len(report.analyzed) != 1)}"
                  + (f" ({len(report.skipped)} too short to analyze)" if report.skipped else "")
                  + f", built {len(report.synthesized)} knowledge base{'s' * (len(report.synthesized) != 1)}, "
                  f"{terms} glossary term{'s' * (terms != 1)}"
                  + (f", Map themes for {themed} categor{'ies' if themed != 1 else 'y'}" if themed else ""), highlight=False)
    for target, err in report.failed[:3]:
        console.print(f"  [red]![/] {target[:40]}: {err[:200]}", highlight=False)
    if report.paused_until:
        from .util import local_str

        console.print(f"  [yellow]{_analyzer(cfg)} usage limit reached[/]: analysis resumes after "
                      f"{local_str(report.paused_until)}.", highlight=False)
    rest = waiting - len(report.analyzed) - len(report.skipped)
    if rest > 0:
        return (f"The other {rest} session{'s are' if rest != 1 else ' is'} analyzed {later}; the Glossary and the Map "
                "grow as they are.")
    return "The Glossary and the Map are ready on the dashboard." if terms else ""


NOTIFY_ASKED_KEY = "update_notify_asked"  # kv: install asked about release notifications, so it asks only once


def _notify_choice(cfg, conn, args, *, ask, background_sync: bool) -> bool | None:
    """Turn release notifications on or off (True/False), or leave the setting alone (None). Asked once, and only
    where they can work: an install that updates from PyPI, with the background sync running to check."""
    from .db import kv_get
    from .update import compares_online

    if args.notify_updates is not None:
        return args.notify_updates
    if (ask is None or cfg.update_notify or not background_sync or kv_get(conn, NOTIFY_ASKED_KEY)
            or not compares_online()):
        return None
    return ask("Notify you when a new version of Chronicle is out? (a desktop notification; asks pypi.org once a "
               "day and sends nothing about you)", True)


def cmd_install(args) -> int:
    from .connectors import connect, disconnect
    from .db import kv_get, kv_set
    from .ingest import sync
    from .install import (LAUNCHD_LABEL, UI_LABEL, agent_path, background_supported, executable, install_hooks,
                          install_launchd, install_mcp, install_statusline, install_ui_agent, launchd_status,
                          statusline_installed, uninstall_launchd)
    from .util import utcnow_iso

    cfg = _cfg()
    conn = _conn(cfg)
    console = _console()
    exe = args.exe or executable()
    interactive = not args.yes and not args.dry_run and sys.stdin.isatty()
    ask = _ask if interactive else (lambda _q, default: default)

    console.print("[bold]Chronicle setup[/]\n")
    analyzer = _choose_analyzer(cfg, console, ask=ask, dry_run=args.dry_run)
    if " -m " in exe:
        console.print(f"[yellow]`chronicle` is not on PATH[/]; hooks will run `{exe}`. "
                      "`uv tool install agents-chronicle` gives it a stable path.\n", highlight=False)

    picked, mcp_clients = _setup_choices(cfg, conn, console, ask=ask)
    background_on = False  # nothing keeps Chronicle running here: say so instead of promising background analysis
    turned_off = [label for label, off in ((LAUNCHD_LABEL, args.no_launchd), (UI_LABEL, args.no_ui)) if off]
    if background_supported() and not (args.no_launchd and args.no_ui):
        background_on = (any(launchd_status(label).get("loaded") for label in (LAUNCHD_LABEL, UI_LABEL))
                         or ask("Run Chronicle in the background, starting at login? (syncs every 15 minutes and "
                                "keeps the dashboard up)", True))
    notify = _notify_choice(cfg, conn, args, ask=_ask if interactive else None,
                            background_sync=background_on and not args.no_launchd)
    if args.dry_run:
        console.print("Would record: " + (", ".join(picked) or "nothing") +
                      (f"; would add the MCP server to: {', '.join(mcp_clients)}" if mcp_clients else ""))

    actions = []
    if "claude" in picked:
        if not args.dry_run and not cfg.claude_dirs:
            _set_config_value(cfg, "sources", "claude_dirs", '["~/.claude"]')
        if not args.no_hooks:
            actions += install_hooks(cfg, exe, inject=args.inject_context or cfg.inject_session_start, dry_run=args.dry_run)
        if args.inject_context and not args.dry_run:
            _set_config_value(cfg, "inject", "session_start", "true")
        if args.statusline or statusline_installed(cfg):  # opt-in; once on, re-installs keep its path current
            actions += install_statusline(cfg, exe, dry_run=args.dry_run)
        if not args.no_mcp:
            actions += install_mcp(cfg, exe, dry_run=args.dry_run)
    elif cfg.claude_dirs and not args.dry_run:
        actions += disconnect(cfg, "claude")  # declined (or not installed): don't scan ~/.claude either
    if args.dry_run:
        if not background_on:
            actions.append("background agents: not installed")
        if background_on and not args.no_launchd:
            actions += install_launchd(cfg, exe, interval=args.interval * 60, dry_run=True)
        if background_on and not args.no_ui:
            actions += install_ui_agent(cfg, exe, dry_run=True)
        actions += [f"would remove background agent {agent_path(label)}" for label in turned_off if agent_path(label).exists()]
        if notify is not None:
            actions.append(f"would turn release notifications {'on' if notify else 'off'}")
        for a in actions:
            console.print(f"• {a}", highlight=False, soft_wrap=True)
        return 0
    for name in [n for n in picked if n != "claude"] + mcp_clients:
        actions += connect(cfg, name, exe)
    if notify is not None:
        _set_config_value(cfg, "updates", "notify", "true" if notify else "false")
        kv_set(conn, NOTIFY_ASKED_KEY, utcnow_iso())
        conn.commit()
        actions.append("a desktop notification when a new version is out (turn off in Status › Updates)" if notify
                       else "no release notifications (turn on in Status › Updates)")
    for a in actions:
        console.print(f"• {a}", highlight=False, soft_wrap=True)

    from .config import load_config

    cfg = load_config(cfg.home)  # pick up the sources just connected
    if picked and not args.no_sync:
        with console.status("Importing past sessions…"):
            report = sync(cfg, conn)
        console.print(f"• imported: {report.summary()}", highlight=False, soft_wrap=True)
    first_install = not kv_get(conn, "installed_at")
    if first_install:
        kv_set(conn, "installed_at", utcnow_iso())
        conn.commit()
    now, waiting, later = [], 0, ""
    if picked and analyzer and not cfg.is_spoke:
        now, waiting, later = _analysis_step(cfg, conn, console, analyzer, interactive=interactive, choice=args.analyze,
                                             background_sync=background_on and not args.no_launchd, interval=args.interval)
    conn.close()
    if now:  # before the background agents start, so they don't take the same sessions
        after = _analyze_now(cfg, console, now, waiting, later)
    else:
        after = (f"The {waiting} waiting session{'s are' if waiting != 1 else ' is'} analyzed {later}; the Glossary "
                 "and the Map are built from them." if waiting else "")

    background = []
    if background_on and not args.no_launchd:
        background += install_launchd(cfg, exe, interval=args.interval * 60)
    if background_on and not args.no_ui:
        background += install_ui_agent(cfg, exe)
    background += uninstall_launchd(turned_off)
    for a in background:
        console.print(f"• {a}", highlight=False, soft_wrap=True)

    url = f"http://127.0.0.1:{cfg.server_port}/"
    ui_running = any(a.startswith("dashboard always available") for a in background)
    console.print("\n[bold green]Done.[/]" + (" Nothing is recorded yet: connect an agent any time with "
                                              "`chronicle connect <name>`." if not picked else ""))
    if after:
        console.print(after, highlight=False)
    if not background_on:
        hooked = "claude" in picked and not args.no_hooks
        console.print("Not running in the background"
                      + (": Claude Code sessions are still recorded and analyzed as they end." if hooked else ".")
                      + " Run `chronicle sync --work` now and then to import new sessions and analyze the queue; "
                      "re-run `chronicle install` to turn background running on.", highlight=False)
    if ui_running:
        console.print(f"Dashboard: [bold]{url}[/] (kept running in the background; `chronicle ui --open` opens it)",
                      highlight=False)
        if interactive and first_install and ask("Open it now?", True) and _wait_for_port(cfg.server_port):
            import webbrowser

            webbrowser.open(url)
    else:
        console.print(f"Dashboard: run [bold]chronicle ui --open[/] (serves {url} while it runs)", highlight=False)
    console.print(f"[dim]More: chronicle sources · chronicle status · config {cfg.config_path}[/]", highlight=False, soft_wrap=True)
    return 0


def _analyzer(cfg) -> str:
    from .llm import make_runner

    return make_runner(cfg).label


def _choose_analyzer(cfg, console, *, ask, dry_run: bool):
    """Settle which agent analyzes sessions; return its runner, or None when it is not installed."""
    from .llm import BACKENDS, make_runner

    runner = make_runner(cfg)
    other = "codex" if runner.name == "claude" else "claude"
    other_found = bool(cfg.codex_bin() if other == "codex" else cfg.claude_bin())
    if runner.available():
        if other_found:
            console.print(f"Sessions are analyzed with {runner.label}. To use {BACKENDS[other]} instead: Status › "
                          f"Analysis in the dashboard, or `chronicle config set analysis.backend {other}`.\n",
                          highlight=False)
        return runner
    missing = f"{runner.label} (`{runner.cli.split()[0]}`) was not found."
    if other_found and ask(f"{missing} Analyze sessions with {BACKENDS[other]} instead, through your "
                           f"{BACKENDS[other]} login?", True):
        if not dry_run:
            _set_config_value(cfg, "analysis", "backend", json.dumps(other))
        cfg.analysis.backend = other
        return make_runner(cfg)
    console.print(f"[yellow]{missing}[/] Chronicle analyzes sessions through your own Claude Code or Codex login; "
                  "until one is installed and signed in (and chosen as analysis.backend), sessions are recorded but "
                  "not analyzed, so the Glossary and the Map stay empty.\n", highlight=False)
    return None


def _set_config_value(cfg, section: str, key: str, value: str) -> None:
    from .config import set_config_value

    set_config_value(cfg, section, key, value)


def cmd_uninstall(args) -> int:
    import shutil

    from .connectors import mcp_clients_status, remove_mcp_client
    from .install import uninstall_hooks, uninstall_launchd, uninstall_mcp, uninstall_statusline

    cfg = _cfg()
    actions = uninstall_hooks(cfg) + uninstall_statusline(cfg) + uninstall_launchd() + uninstall_mcp(cfg)
    for c in mcp_clients_status():
        if c["registered"]:
            actions += remove_mcp_client(cfg, c["name"])
    for a in actions or ["nothing to remove"]:
        print(f"• {a}")
    if args.purge:
        shutil.rmtree(cfg.home, ignore_errors=True)
        print(f"• deleted {cfg.home}")
    else:
        print(f"Data kept in {cfg.home} (use --purge to delete it).")
    return 0


def cmd_serve(args) -> int:
    from .server import serve
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    serve(cfg, host=args.host, port=args.port, open_browser=args.open)
    return 0


def cmd_app(args) -> int:
    from .desktop import main

    return main()


def cmd_export(args) -> int:
    from pathlib import Path

    from .export_md import export_markdown

    cfg = _cfg()
    if args.sessions:
        return _export_sessions(cfg, args)
    if args.out:
        cfg.notes_dir = Path(args.out).expanduser()
    conn = _conn(cfg)
    n = export_markdown(conn, cfg, full=args.full)
    print(f"{n} notes written to {cfg.notes_dir}")
    return 0


def _export_sessions(cfg, args) -> int:
    """`chronicle export ID...`: the sessions as one file (or a .zip of several) instead of the vault."""
    from pathlib import Path

    from .session_export import ExportError, export_sessions
    from .views import resolve_session_id

    conn = _conn(cfg)
    ids = []
    for ref in args.sessions:
        sid = resolve_session_id(conn, ref)
        if not sid:
            print(f"no unique session matches {ref!r}", file=sys.stderr)
            return 2
        ids.append(sid)
    try:
        name, _, data = export_sessions(conn, ids, args.format)
    except ExportError as exc:
        print(exc, file=sys.stderr)
        return 1
    out = Path(args.out or ".").expanduser()
    path = out / name if out.is_dir() else out
    path.write_bytes(data)
    print(f"wrote {path} ({len(data):,} bytes)")
    return 0


def cmd_mcp(args) -> int:
    if args.print_config:
        import json

        from .connectors import mcp_server_entry
        from .install import executable

        print(json.dumps({"mcpServers": {"chronicle": mcp_server_entry(executable())}}, indent=2))
        return 0
    from .mcp_server import serve

    return serve(_cfg())


def cmd_config(args) -> int:
    import os
    import subprocess

    cfg = _cfg()
    if args.action == "set":
        return _config_set(cfg, args.key, args.value)
    if args.action == "path":
        print(cfg.config_path)
    elif args.action == "edit":
        editor = os.environ.get("EDITOR", "open" if sys.platform == "darwin" else "vi")
        subprocess.call([*editor.split(), str(cfg.config_path)])
    else:
        print(cfg.config_path.read_text())
    return 0


def _config_set(cfg, key: str | None, value: str | None) -> int:
    """`chronicle config set section.key value`: the value is TOML, or a bare word taken as a string."""
    import tomllib

    from .config import LANGUAGES, load_config, set_config_value
    from .llm import BACKENDS

    if not key or value is None or "." not in key:
        print("usage: chronicle config set SECTION.KEY VALUE   (e.g. chronicle config set analysis.backend codex)",
              file=sys.stderr)
        return 2
    section, name = key.split(".", 1)
    try:
        tomllib.loads(f"v = {value}")
        literal = value
    except tomllib.TOMLDecodeError:
        literal = json.dumps(value)  # a bare word: a TOML basic string
    if key == "analysis.backend" and tomllib.loads(f"v = {literal}")["v"] not in BACKENDS:
        print(f"analysis.backend must be one of: {', '.join(BACKENDS)}", file=sys.stderr)
        return 2
    if key == "analysis.language" and tomllib.loads(f"v = {literal}")["v"] not in LANGUAGES:
        print(f"analysis.language must be one of: {', '.join(LANGUAGES)}", file=sys.stderr)
        return 2
    try:
        set_config_value(cfg, section, name, literal)
    except tomllib.TOMLDecodeError as exc:
        print(f"not changed: {exc}", file=sys.stderr)
        return 2
    print(f"[{section}] {name} = {literal}")
    if key == "analysis.backend":
        from .llm import make_runner

        runner = make_runner(load_config(cfg.home))
        if not runner.available():
            print(f"note: `{runner.cli.split()[0]}` was not found; analysis waits until it is installed and signed in")
    return 0


def cmd_forget(args) -> int:
    from .ingest import forget_session
    from .views import resolve_session_id

    cfg = _cfg()
    conn = _conn(cfg)
    sid = resolve_session_id(conn, args.session)
    if not sid:
        print(f"no unique session matches {args.session!r}", file=sys.stderr)
        return 2
    title = conn.execute("SELECT title FROM sessions WHERE id = ?", (sid,)).fetchone()[0]
    if not args.yes:
        answer = input(f"Forget {sid[:8]} ({title})? It will never be re-ingested. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            return 1
    for item in forget_session(conn, cfg, sid, delete_transcript=args.delete_transcript):
        print(f"• removed {item}")
    return 0


def cmd_glossary(args) -> int:
    from .glossary import build_glossaries, glossary_entries, lookup
    from .synthesize import GLOBAL
    from .util import local_str, setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    conn = _conn(cfg)
    console = _console()
    project = None
    if args.project:
        row = conn.execute("SELECT project_path FROM sessions WHERE project_path = ? OR project_name = ? LIMIT 1",
                           (args.project, args.project)).fetchone()
        project = row[0] if row else args.project
    if args.themes:
        from .glossary import build_themes, themes_due

        due = themes_due(conn, force=args.force)
        conn.close()
        if not due:
            print("themes are up to date (use --force to regroup anyway)")
            return 0
        print(f"grouping {len(due)} categor{'y' if len(due) == 1 else 'ies'} into themes with {_analyzer(cfg)}…")
        results = build_themes(cfg, due, concurrency=cfg.analysis.concurrency + 1, progress=lambda m: print(f"  {m}"))
        print(f"done: {sum(1 for v in results.values() if isinstance(v, int))}/{len(due)} categories grouped")
        return 0 if all(isinstance(v, int) for v in results.values()) else 1
    if args.rebuild:
        targets = [project] if project else ([r[0] for r in conn.execute(
            "SELECT DISTINCT project_path FROM knowledge WHERE status = 'active' AND project_path IS NOT NULL")] + [GLOBAL]
            if args.all else [])
        if not targets:
            print("use --rebuild with -p PROJECT or --all")
            return 2
        conn.close()
        print(f"building {len(targets)} glossar{'y' if len(targets) == 1 else 'ies'} with {_analyzer(cfg)}…")
        results = build_glossaries(cfg, targets, concurrency=cfg.analysis.concurrency + 1, progress=lambda m: print(f"  {m}"))
        ok = sum(1 for v in results.values() if isinstance(v, int))
        print(f"done: {ok}/{len(targets)} built, {sum(v for v in results.values() if isinstance(v, int))} terms")
        return 0
    if args.term:
        e = lookup(conn, args.term)
        if not e:
            print(f"{args.term!r} is not in the glossary")
            return 1
        console.print(f"[bold]{e['term']}[/] [dim]{e['category']}" + (f" · also: {', '.join(e['aliases'])}" if e["aliases"] else "") + "[/]",
                      highlight=False)
        console.print(e["definition"] or "", highlight=False, markup=False)
        for u in e["usage"]:
            if u["context"]:
                console.print(f"  [cyan]{u['project_name']}[/]: {u['context']}", highlight=False)
        if e["n_sessions"]:
            console.print(f"  [dim]in {e['n_sessions']} sessions, {local_str(e['first_seen'], '%Y-%m-%d')} → "
                          f"{local_str(e['last_seen'], '%Y-%m-%d')}[/]", highlight=False)
        return 0
    for e in glossary_entries(conn, project=project, category=args.category):
        console.print(f"[bold]{e['term']}[/] [dim]({e['category']})[/] {e['definition'] or ''}", highlight=False)
    return 0


def cmd_review(args) -> int:
    from rich.markdown import Markdown

    from .reviews import generate_review, week_bounds
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    conn = _conn(cfg)
    key = week_bounds(args.week)[0]
    row = conn.execute("SELECT markdown FROM reviews WHERE period = ?", (key,)).fetchone()
    if row and not args.regenerate:
        _console().print(Markdown(row[0]))
        return 0
    print(f"writing review for {key} with {_analyzer(cfg)}…")
    try:
        generate_review(conn, cfg, key)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    _console().print(Markdown(conn.execute("SELECT markdown FROM reviews WHERE period = ?", (key,)).fetchone()[0]))
    return 0


def _project_arg(conn, value: str | None) -> str | None:
    """-p accepts a project's path or its name."""
    if not value:
        return None
    row = conn.execute("SELECT project_path FROM sessions WHERE project_path = ? OR project_name = ? LIMIT 1",
                       (value, value)).fetchone()
    return row[0] if row else value


def escape_markup(text: str) -> str:
    from rich.markup import escape

    return escape(text or "")


def _home_short(path: str | None) -> str:
    from pathlib import Path

    if not path:
        return "-"
    home = str(Path.home())
    return "~" + path[len(home):] if path == home or path.startswith(home + "/") else path


def _warning_bits(w: dict) -> list[str]:
    bits = []
    if w.get("public_repo"):
        bits.append("public repo")
    if w.get("untracked"):
        bits.append("file not tracked by git")
    if w.get("overlap"):
        bits.append("already covered")
    bits += [f"sensitive: {h}" for h in w.get("sensitive") or []]
    return bits


def _print_diff(console, diff: str) -> None:
    from rich.text import Text

    for line in diff.splitlines():
        style = ("bold" if line.startswith(("+++", "---")) else "green" if line.startswith("+")
                 else "red" if line.startswith("-") else "cyan" if line.startswith("@@") else "")
        console.print(Text(line, style=style), highlight=False, soft_wrap=True)


def _show_suggestion(console, s: dict, pv: dict) -> None:
    console.print(f"[bold]#{s['id']}[/] [cyan]{s['kind']}[/] {escape_markup(s['title'])}", highlight=False, soft_wrap=True)
    if pv.get("command") is not None:
        console.print("  run it yourself, then `chronicle suggest done " + str(s["id"]) + "`:", highlight=False, soft_wrap=True)
        console.print(f"    {pv['command']}", highlight=False, markup=False, soft_wrap=True)
    elif not pv.get("ok"):
        console.print(f"  [red]cannot apply:[/] {escape_markup(str(pv.get('error')))}", highlight=False, soft_wrap=True)
    elif pv["diff"]:
        _print_diff(console, pv["diff"])
    else:
        console.print(f"  {_home_short(pv.get('path'))} already has it (nothing to change)", highlight=False, soft_wrap=True)
    for bit in _warning_bits(pv.get("warnings") or {}):
        console.print(f"  [yellow]! {escape_markup(bit)}[/]", highlight=False, soft_wrap=True)


def cmd_suggest(args) -> int:
    from . import suggest
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    conn = _conn(cfg)
    console = _console()
    action, ids = args.action or "list", args.ids
    if action == "refresh":
        got = suggest.refresh(conn, cfg)
        print(f"suggestions: {got['new']} new, {got['updated']} updated, {got['stale']} stale")
        return 0
    if action == "list":
        if ids:
            print("to look at one suggestion: chronicle suggest show ID", file=sys.stderr)
            return 2
        rows = suggest.list_suggestions(conn, status=None if args.all else "new", project=_project_arg(conn, args.project))
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
            return 0
        for s in rows:
            status = "" if s["status"] == "new" else f" [dim]({s['status']})[/]"
            console.print(f"[green]#{s['id']}[/] [cyan]{s['kind']}[/] [bold]{escape_markup(s['title'])}[/]{status} "
                          f"[dim]→ {escape_markup(_home_short(s['target_path']) if s['target_path'] else 'run yourself')}[/]",
                          highlight=False, soft_wrap=True)
            line = (s["evidence"] or {}).get("line")
            if line:
                console.print(f"    [dim]{escape_markup(line)}[/]", highlight=False, soft_wrap=True)
            for bit in _warning_bits(s["warnings"] or {}):
                console.print(f"    [yellow]! {escape_markup(bit)}[/]", highlight=False, soft_wrap=True)
        if not rows:
            print("no suggestions" + ("" if args.all else " waiting (--all for applied and dismissed ones)"))
        else:
            print("\nchronicle suggest show ID · apply ID · dismiss ID · done ID (setup steps) · move ID --to user|project")
        return 0
    if not ids:
        print(f"usage: chronicle suggest {action} ID", file=sys.stderr)
        return 2
    failed = 0
    for sid in ids:
        s = suggest.get(conn, sid)
        if s is None:
            print(f"no suggestion #{sid}", file=sys.stderr)
            failed += 1
            continue
        if action == "show":
            _show_suggestion(console, s, suggest.preview(conn, cfg, sid))
            continue
        if action == "dismiss":
            suggest.dismiss(conn, sid, args.reason)
            print(f"#{sid} dismissed; it will not be proposed again")
            continue
        if action == "done":
            got = suggest.mark_done(conn, sid)
            print(f"#{sid} marked done" if got["ok"] else f"#{sid}: {got['error']}", file=sys.stdout if got["ok"] else sys.stderr)
            failed += not got["ok"]
            continue
        if action == "move":
            if not args.to:
                print("usage: chronicle suggest move ID --to user|project", file=sys.stderr)
                return 2
            got = suggest.move(conn, cfg, sid, args.to)
            if not got["ok"]:
                print(f"#{sid}: {got['error']}", file=sys.stderr)
                failed += 1
            elif got["moved"]:
                print(f"#{sid} moved to " + ", ".join(_home_short(t) for t in got["targets"]) + " (see chronicle suggest)")
            else:
                print(f"#{sid} moved, but nothing is waiting there: it was dismissed or applied there before")
            continue
        if action == "undo":
            got = suggest.unapply(conn, cfg, sid)
            if got["ok"]:
                print(f"#{sid} taken back out" + (f" of {_home_short(got['path'])}" if got.get("path") else "")
                      + "; it is waiting again")
            else:
                print(f"#{sid}: {got['error']}", file=sys.stderr)
                failed += 1
            continue
        # apply
        pv = suggest.preview(conn, cfg, sid)
        _show_suggestion(console, s, pv)
        if s["kind"] == "environment" or not pv.get("ok"):
            failed += 1
            continue
        if not args.yes:
            try:
                answer = input(f"Apply #{sid} to {_home_short(pv['path'])}? [y/N] ")
            except EOFError:
                answer = ""
            if answer.strip().lower() not in ("y", "yes"):
                print(f"#{sid} skipped")
                continue
        got = suggest.apply(conn, cfg, sid)
        if got["ok"]:
            print(f"#{sid} applied to {_home_short(got['path'])} (undo: chronicle suggest undo {sid})")
        else:
            print(f"#{sid}: {got['error']}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


SPARK = "▁▂▃▄▅▆▇█"


def _spark(weekly: list[dict]) -> str:
    vals = [w["sessions"] for w in weekly or []]
    top = max(vals, default=0)
    return "".join(" " if not v else SPARK[min(len(SPARK) - 1, (v * len(SPARK) - 1) // top)] for v in vals) if top else ""


def cmd_friction(args) -> int:
    from rich import box
    from rich.table import Table

    from .friction import report

    cfg = _cfg()
    conn = _conn(cfg)
    got = report(conn, days=args.days, project=_project_arg(conn, args.project), noise=args.noise)
    if args.json:
        print(json.dumps(got, ensure_ascii=False, indent=1, default=str))
        return 0
    console = _console()

    def causes_table(title: str, causes: list[dict], caption: str | None = None):
        t = Table(header_style="bold", title=title, title_justify="left", box=box.SIMPLE_HEAD, caption=caption,
                  caption_justify="left", pad_edge=False)
        for col, width in (("cause", None), ("sessions", 8), ("projects", 8), ("last seen", 10), ("now", 3), ("trend", 12)):
            t.add_column(col, justify="right" if col in ("sessions", "projects") else "left", no_wrap=True,
                         overflow="ellipsis", min_width=width, max_width=max(22, console.width - 58) if width is None else None)
        for c in causes:
            name = c["id"] if c["category"] != "other" else f"other: {c['name']}"
            t.add_row(escape_markup(name), str(c["sessions"]), str(len(c["projects"])), c["last_seen"] or "-",
                      "[red]yes[/]" if c["still_happening"] else "[dim]no[/]", _spark(c["weekly"]))
        console.print(t)

    wasteful = [c for c in got["causes"] if not c["noise"]]
    if wasteful:
        causes_table("What goes wrong", wasteful, "now: still happening (last 14 days) · trend: sessions a week, last 12 weeks")
    else:
        print("no recurring failures found")
    noise = [c for c in got["causes"] if c["noise"]]
    if noise:
        causes_table("Noise (expected failures, not wasted work)", noise)
    if got["tool_errors"]:
        e = Table(header_style="bold", title="Tool error rates", title_justify="left", box=box.SIMPLE_HEAD)
        for col in ("tool", "calls", "errors", "rate"):
            e.add_column(col, justify="left" if col == "tool" else "right")
        for r in got["tool_errors"]:
            e.add_row(escape_markup(r["tool"]), str(r["calls"]), str(r["errors"]), f"{r['rate'] * 100:.1f}%")
        console.print(e)
    ns = got["noise_summary"]
    if not args.noise and ns["occurrences"]:
        print(f"filtered as noise: {ns['occurrences']} failure{'s' if ns['occurrences'] != 1 else ''} in {ns['sessions']} "
              f"session{'s' if ns['sessions'] != 1 else ''} (expected test failures, "
              "read-only checks, provider hiccups); --noise shows them")
    print("fixes for these: chronicle suggest")
    return 0


def cmd_sources(args) -> int:
    from .connectors import all_status, mcp_clients_status
    from .util import local_str

    cfg = _cfg()
    conn = _conn(cfg)
    console = _console()
    for c in all_status(cfg, conn):
        state = "[green]connected[/]" if c["connected"] else ("[yellow]detected, not connected[/]" if c["detected"] else "[dim]not installed[/]")
        console.print(f"[bold]{c['label']}[/] ({c['vendor']}) · {state} · {c['version'] or 'version unknown'}", highlight=False)
        rec = c["recorded"]
        console.print(f"  {c['on_disk']} sessions {c.get('on_disk_label', 'on disk')} · {rec['sessions']} recorded ({rec['analyzed']} analyzed) · "
                      f"last {local_str(rec['last_session'])} · {c['recording']}", highlight=False)
        for chk in c["checks"]:
            mark = "[green]✓[/]" if chk["ok"] else ("[dim]–[/]" if chk["ok"] is None or chk.get("optional") else "[red]✗[/]")
            console.print(f"  {mark} {chk['label']}: [dim]{chk['detail']}[/]", highlight=False)
        console.print()
    console.print("[bold]Other MCP clients[/] [dim](not recorded; `chronicle connect <name>` gives them Chronicle's MCP tools)[/]", highlight=False)
    for c in mcp_clients_status():
        state = "[green]✓ MCP server added[/]" if c["registered"] else ("[yellow]detected[/]" if c["detected"] else "[dim]not installed[/]")
        console.print(f"  {c['label']} [dim]({c['name']})[/] · {state} · [dim]{c['config']}[/]", highlight=False)
    return 0


def cmd_import(args) -> int:
    from pathlib import Path

    from .chat_import import ExportError, import_export, summary

    cfg = _cfg()
    conn = _conn(cfg)
    try:
        counts = import_export(cfg, conn, Path(args.path), analyze=args.analyze, progress=lambda m: print(m, file=sys.stderr))
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(summary(counts))
    if args.screen and not args.analyze:
        return _screen_run(cfg, conn, source=None, redo=False, limit=None, sample=False)
    if counts["new"] + counts["updated"]:
        print("queued for analysis (`chronicle work` runs it now)" if args.analyze
              else "not analyzed: `chronicle screen` sorts out which chats are worth analyzing (reading only their "
                   "openings); or open one and choose Analyze now, or re-run with --analyze to queue them all")
    return 0


def _screen_run(cfg, conn, *, source, redo, limit, sample) -> int:
    from .screen import SOURCES, screen_chats, screen_status
    from .util import human_cost

    report = screen_chats(cfg, conn, source=source, redo=redo, limit=limit, sample=sample,
                          progress=lambda m: print(m, file=sys.stderr))
    print(report.summary() + (f" · screening cost {human_cost(report.cost_usd)}" if report.calls else ""))
    worth = sum(screen_status(conn, s)["to_queue"] for s in SOURCES)
    if worth:
        print(f"next: `chronicle screen --list analyze` shows them, `chronicle screen --queue` queues the {worth:,} worth "
              "analyzing (add --maybe for the maybes too)")
    return 1 if report.left and not report.screened else 0


def cmd_screen(args) -> int:
    from .screen import BATCH, candidates, queue, rule_verdict

    cfg = _cfg()
    conn = _conn(cfg)
    if args.queue:
        n = queue(conn, source=args.source, maybe=args.maybe)
        print(f"queued {n:,} chat{'' if n == 1 else 's'} for analysis: the background agent analyzes "
              f"{cfg.analysis.max_per_run} every 15 minutes, newest first (`chronicle analyze --pending` runs them now)"
              if n else "nothing to queue: screen the chats first (`chronicle screen`), or they are queued already")
        return 0
    if args.list:
        return _screen_list(conn, args)
    if args.dry_run:
        rows = candidates(conn, source=args.source, redo=args.redo, limit=args.sample or args.limit, sample=bool(args.sample))
        ruled = sum(rule_verdict(r) is not None for r in rows)
        rest = len(rows) - ruled
        print(f"{len(rows):,} chats to screen: {ruled:,} settled by rules, {rest:,} for {cfg.analysis.screen_model} in "
              f"{-(-rest // BATCH)} call{'' if -(-rest // BATCH) == 1 else 's'}; nothing sent (dry run)")
        return 0
    return _screen_run(cfg, conn, source=args.source, redo=args.redo, limit=args.sample or args.limit, sample=bool(args.sample))


def _screen_list(conn, args) -> int:
    from rich import box
    from rich.table import Table

    from .screen import VERDICT_LABEL, source_filter

    where, params = source_filter(args.source)
    rows = conn.execute(
        f"SELECT id, started_at, n_prompts, title, screen_topic, screen_reason, analysis_status FROM sessions "
        f"WHERE {where} AND screen_verdict = ? AND screen_sig = files_sig ORDER BY started_at DESC LIMIT ?",
        [*params, args.list, args.limit or 100_000]).fetchall()
    if args.json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print(f"no chats screened as {args.list}")
        return 0
    console = _console()
    t = Table(header_style="bold", box=box.SIMPLE_HEAD, pad_edge=False)
    for col in ("id", "date", "prompts", "chat", "why"):
        t.add_column(col, justify="right" if col == "prompts" else "left", no_wrap=col in ("id", "date"),
                     overflow="fold" if col in ("chat", "why") else "ellipsis")
    for r in rows:
        title = escape_markup(r["title"] or "(untitled)") + (f" [dim]· {escape_markup(r['screen_topic'])}[/]" if r["screen_topic"] else "")
        t.add_row(r["id"][:8], (r["started_at"] or "")[:10], str(r["n_prompts"] or 0), title,
                  escape_markup(r["screen_reason"] or "") + (" [green](analyzed)[/]" if r["analysis_status"] == "done" else ""))
    console.print(t)
    print(f"{len(rows):,} chat{'' if len(rows) == 1 else 's'} screened as {args.list} ({VERDICT_LABEL[args.list]})")
    return 0


def cmd_connect(args) -> int:
    from .connectors import MCP_CLIENTS, connect, disconnect
    from .install import executable

    cfg = _cfg()
    if args.disconnect:
        actions = disconnect(cfg, args.name)
    else:
        actions = connect(cfg, args.name, args.exe or executable())
    for a in actions:
        print(f"• {a}")
    if not args.disconnect and not args.no_sync and args.name not in MCP_CLIENTS:
        from .config import load_config
        from .ingest import sync

        cfg = load_config(cfg.home)
        print("syncing…")
        report = sync(cfg, _conn(cfg))
        print(f"sync: {report.summary()}")
    return 0


def _push(cfg, *, quiet: bool = False) -> int:
    from .hub import HubError, push

    live = not quiet and sys.stdout.isatty()

    def progress(message: str) -> None:
        if live:
            print(f"\r\033[K  {message[:110]}", end="", flush=True)

    try:
        report = push(cfg, progress=progress)
    except HubError as exc:
        if live:
            print("\r\033[K", end="")
        print(f"push: {exc}", file=sys.stderr)
        return 1
    if live:
        print("\r\033[K", end="")
    if not quiet:
        print(f"push: {report.summary()}")
    for err in report.errors[:10]:
        print(f"  ! {err}", file=sys.stderr)
    return 0 if not report.errors else 1


def cmd_push(args) -> int:
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir)
    if not cfg.is_spoke:
        print("This computer has not joined a hub. On the hub run `chronicle hub enable`, then run the command it "
              "prints here.", file=sys.stderr)
        return 1
    return _push(cfg, quiet=args.quiet)


def _hub_url_guess(cfg) -> str | None:
    """The address other computers reach this one's dashboard at: its Tailscale name, when Serve is set up."""
    for host in cfg.server_allowed_hosts:
        if host.endswith(".ts.net"):
            return f"https://{host}"
    return None


def cmd_hub(args) -> int:
    import platform

    from . import hub
    from .install import background_status, hooks_installed

    cfg = _cfg()
    console = _console()
    action = args.action

    if action == "enable":
        if cfg.is_spoke:
            console.print(f"This computer sends its sessions to the hub at {cfg.hub_url}. Run `chronicle hub leave` "
                          "first to make it a hub itself.", highlight=False)
            return 1
        token = hub.read_token(cfg)
        if not token or args.rotate:
            token = hub.new_token(cfg)
            if args.rotate:
                console.print("New token: computers that joined with the old one must join again.")
        conn = _conn(cfg)
        hub.register_local(conn, cfg)
        conn.commit()
        conn.close()
        url = (args.url_opt or args.url or _hub_url_guess(cfg) or "").rstrip("/")
        console.print(f"[bold]{hub.local_machine(cfg)['name']}[/] is a hub: other computers can send it their sessions.",
                      highlight=False)
        if not url:
            console.print("Other computers need an address to reach it. Run `chronicle tailnet on` (Tailscale), then "
                          "`chronicle hub enable` again, or pass the address: `chronicle hub enable --url "
                          f"http://<address>:{cfg.server_port}` (only on a network you trust: without Tailscale the "
                          "files travel unencrypted).", highlight=False)
            return 0
        from urllib.parse import urlparse

        given = urlparse(url if "://" in url else f"http://{url}")
        name = (given.hostname or "").lower()
        if name and name not in ("127.0.0.1", "localhost", "::1") and name not in cfg.server_allowed_hosts:
            _set_config_value(cfg, "server", "allowed_hosts", json.dumps([*cfg.server_allowed_hosts, name]))
            if cfg.server_host in ("127.0.0.1", "localhost"):
                console.print(f"[yellow]The dashboard listens on {cfg.server_host} only[/]: for other computers to reach "
                              f"{url} without Tailscale, set `chronicle config set server.host 0.0.0.0` and restart it.",
                              highlight=False)
        console.print("On each other computer, install Chronicle and run:\n")
        console.print(f"  [bold]{hub.join_command(url, token)}[/]\n", highlight=False, soft_wrap=True)
        console.print("[dim]The token lets a computer send sessions here; keep it private. "
                      "`chronicle hub enable --rotate` replaces it.[/]", highlight=False)
        if not _wait_for_port(cfg.server_port, 1.0):
            console.print(f"[yellow]The dashboard is not running on port {cfg.server_port}[/]: it is what receives "
                          "the files. `chronicle install` keeps it running (or run `chronicle ui`).", highlight=False)
        if platform.system() == "Linux":
            console.print("[dim]A hub that should run while nobody is logged in: `loginctl enable-linger $USER`.[/]",
                          highlight=False)
        return 0

    if action == "join":
        if not args.url or not args.token:
            console.print("Usage: chronicle hub join <hub address> --token <token> (the hub's `chronicle hub enable` "
                          "prints the whole command).")
            return 2
        if hub.read_token(cfg) and not cfg.is_spoke:
            console.print("This computer is a hub itself (`chronicle hub disable` first).")
            return 1
        url = args.url.rstrip("/")
        if "://" not in url:
            url = f"https://{url}"
        hub.write_token(cfg, args.token)
        _set_config_value(cfg, "hub", "url", json.dumps(url))
        from .config import load_config

        cfg = load_config(cfg.home)
        console.print(f"Joined the hub at {url}. This computer now sends its Claude Code and Codex sessions there; "
                      "the hub records and analyzes them.", highlight=False)
        if args.no_push:
            return 0
        console.print("Sending the sessions on this computer (the first time can take a while)…")
        code = _push(cfg)
        if code == 0:
            bg = background_status()
            hooked = bool(hooks_installed(cfg).get("SessionEnd"))
            if bg.get("loaded") or hooked:
                console.print("New sessions go to the hub as each one ends" + (" and every 15 minutes." if bg.get("loaded") else "."))
            else:
                console.print("To send new sessions automatically (as each ends, and every 15 minutes), run "
                              "`chronicle install`. Until then: `chronicle push`.")
            console.print("[dim]This computer's own dashboard and MCP tools keep what they had and are no longer "
                          "updated; open the hub's dashboard instead. `chronicle hub leave` undoes this.[/]",
                          highlight=False)
        return code

    if action == "leave":
        if not cfg.is_spoke:
            console.print("This computer has not joined a hub.")
            return 0
        _set_config_value(cfg, "hub", "url", '""')
        hub.token_path(cfg).unlink(missing_ok=True)
        console.print(f"Left the hub at {cfg.hub_url}. This computer records and analyzes its own sessions again; "
                      "the hub keeps what it was sent.", highlight=False)
        return 0

    if action == "disable":
        if cfg.is_spoke or not hub.read_token(cfg):
            console.print("This computer is not a hub.")
            return 0
        hub.token_path(cfg).unlink(missing_ok=True)
        console.print("Other computers can no longer send sessions here. What they sent is kept.")
        return 0

    # status
    if cfg.is_spoke:
        last = hub.last_push(cfg)
        console.print(f"Sends its sessions to the hub at [bold]{cfg.hub_url}[/]", highlight=False)
        console.print(f"  last push: {last['at'] + ' · ' + last['summary'] if last else 'never'}", highlight=False)
        return 0
    conn = _conn(cfg)
    rows = hub.machines(conn, cfg)
    conn.close()
    role = "a hub" if hub.read_token(cfg) else "not a hub (`chronicle hub enable` makes it one)"
    console.print(f"[bold]{hub.local_machine(cfg)['name']}[/] is {role}.", highlight=False)
    from .util import local_str

    for m in rows:
        seen = "this computer" if m["this"] else f"last sent {local_str(m['last_push']) if m['last_push'] else 'nothing yet'}"
        console.print(f"  {m['name'] or m['id'][:8]:<28} {m['platform'] or '':<8} {m['sessions']:>5} session{'s' * (m['sessions'] != 1)} · {seen}",
                      highlight=False)
    return 0


def cmd_tailnet(args) -> int:
    import platform

    from . import tailnet

    cfg = _cfg()
    console = _console()
    cli = tailnet.find_cli()
    if not cli:
        console.print("Tailscale is not installed. Install it on this computer and your phone "
                      "(https://tailscale.com/download), sign both in to the same account, then run this again.")
        return 1
    try:
        st = tailnet.status(cli)
    except (tailnet.TailnetError, OSError) as exc:
        console.print(f"Could not ask Tailscale for its status: {exc}", highlight=False)
        return 1
    hosts = [h for h in cfg.server_allowed_hosts if h != st.dns_name]

    if args.action == "status":
        serving = tailnet.serves_port(tailnet.serve_status(cli), cfg.server_port)
        console.print(f"Tailscale: {st.state or 'unknown'}" + (f" as {st.login} · this computer is {st.dns_name}" if st.running else ""),
                      highlight=False)
        console.print(f"  dashboard on the tailnet: {st.url + '/' if serving else 'off (`chronicle tailnet on`)'}", highlight=False)
        console.print(f"  allowed_hosts: {cfg.server_allowed_hosts or '[]'} · allowed_users: {cfg.server_allowed_users or 'anyone on the tailnet'}",
                      highlight=False)
        return 0

    if not st.running or not st.dns_name:
        console.print(f"Tailscale is not connected ({st.state or 'unknown'}). Sign in with `tailscale up` or the "
                      "Tailscale app, then run this again.", highlight=False)
        return 1

    if args.action == "off":
        proc = tailnet.serve(cli, cfg.server_port, off=True, interactive=False)
        _set_config_value(cfg, "server", "allowed_hosts", json.dumps(hosts))
        _set_config_value(cfg, "server", "allowed_users", "[]")
        console.print("The dashboard is no longer on your tailnet." if proc.returncode == 0 else
                      f"Tailscale said: {(proc.stderr or proc.stdout).strip()[:300]}", highlight=False)
        return 0

    # on
    _set_config_value(cfg, "server", "allowed_hosts", json.dumps([*hosts, st.dns_name]))
    _set_config_value(cfg, "server", "allowed_users", json.dumps([] if args.anyone or not st.login else [st.login]))
    console.print(f"Serving the dashboard at [bold]{st.url}/[/] with Tailscale Serve…", highlight=False)
    proc = tailnet.serve(cli, cfg.server_port, interactive=sys.stdin.isatty())
    if proc.returncode != 0:
        hint = (" On Linux, let your user configure Tailscale once: `sudo tailscale set --operator=$USER`."
                if platform.system() == "Linux" else "")
        console.print(f"[red]Tailscale Serve did not start[/]{': ' + (proc.stderr or '').strip()[:300] if proc.stderr else ''}.{hint}",
                      highlight=False)
        return 1
    console.print(f"\nOpen [bold]{st.url}/[/] on your phone (with the Tailscale app on) or any computer in your tailnet.",
                  highlight=False)
    console.print("On an iPhone: Share › Add to Home Screen, for an app icon. On Android: ⋮ › Add to Home screen.")
    who = "you" if not args.anyone and st.login else "anyone in your tailnet"
    console.print(f"[dim]Only {who} ({st.login or 'tailnet'}) can open it; nothing is reachable from the internet. "
                  "`chronicle tailnet off` stops it.[/]", highlight=False)
    if not _wait_for_port(cfg.server_port, 1.0):
        console.print(f"[yellow]The dashboard is not running on port {cfg.server_port}.[/] `chronicle install` keeps it "
                      "running in the background (or run `chronicle ui`).", highlight=False)
    return 0


def cmd_context(args) -> int:
    import os

    from .hooks import build_session_context

    cfg = _cfg()
    print(build_session_context(cfg, args.cwd or os.getcwd()) or "(no knowledge recorded for this directory yet)")
    return 0


# ---------------------------------------------------------------------------- parser
def _analyze_choice(value: str) -> str:
    value = value.strip().lower()
    if value in ("all", "later") or (value.isdigit() and int(value) > 0):
        return value
    raise argparse.ArgumentTypeError("use all, later or a number of sessions")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chronicle",
        description="Record, archive and analyze every coding-agent session (Claude Code, Codex, GitHub Copilot, IBM Bob, "
                    "Google Antigravity); extract reusable knowledge.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    s = sub.add_parser("install", aliases=["setup"],
                       help="set up: pick which coding agents to record, import past sessions, start the dashboard")
    s.add_argument("-y", "--yes", action="store_true", help="don't ask: record every agent found (the default without a terminal)")
    s.add_argument("--no-sync", action="store_true", help="don't import past sessions now (the background sync will)")
    s.add_argument("--no-hooks", action="store_true")
    s.add_argument("--no-launchd", action="store_true", help="no 15-minute background sync (removes it if installed)")
    s.add_argument("--no-mcp", action="store_true")
    s.add_argument("--no-ui", action="store_true", help="don't keep the dashboard running in the background (removes it if installed)")
    s.add_argument("--inject-context", action="store_true", help="also add a SessionStart hook that injects project knowledge")
    s.add_argument("--statusline", action="store_true",
                   help="also record context and plan-limit usage from Claude Code's status line (keeps your own status line)")
    s.add_argument("--interval", type=int, default=15, help="background sync interval in minutes (default 15)")
    s.add_argument("--exe", help="command used by hooks/launchd (default: the installed `chronicle`)")
    s.add_argument("--analyze", type=_analyze_choice, metavar="all|N|later",
                   help="analyze past sessions now with progress (all, or the newest N), or later; asked when omitted "
                        "(later without a terminal). The Glossary and the Map are built from the analyzed sessions")
    s.add_argument("--notify-updates", action=argparse.BooleanOptionalAction, default=None,
                   help="show a desktop notification when a new version is out (asks pypi.org once a day); "
                        "asked once when omitted")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("uninstall", help="remove hooks, the background agent and the MCP server")
    s.add_argument("--purge", action="store_true", help="also delete all recorded data")
    s.set_defaults(fn=cmd_uninstall)

    s = sub.add_parser("status", aliases=["doctor"], help="show installation and queue status")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("sync", help="archive and ingest all transcripts")
    s.add_argument("--work", action="store_true", help="then analyze/synthesize/export (the background job does this)")
    s.add_argument("--force", action="store_true", help="re-parse every session")
    s.add_argument("--quiet", action="store_true")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("work", help="process the analysis queue, synthesize knowledge bases, export notes")
    s.add_argument("--limit", type=int, help="max sessions to analyze this run")
    s.add_argument("--model")
    s.add_argument("--force", action="store_true", help="synthesize even below the threshold")
    s.add_argument("--no-analyze", action="store_true")
    s.add_argument("--no-synthesize", action="store_true")
    s.add_argument("--no-export", action="store_true")
    s.set_defaults(fn=cmd_work)

    s = sub.add_parser("analyze", help="analyze specific sessions now (ids or prefixes)")
    s.add_argument("sessions", nargs="*")
    s.add_argument("--pending", action="store_true", help="all sessions waiting for analysis")
    s.add_argument("--all", action="store_true", help="every eligible session (with --force: re-analyze done ones)")
    s.add_argument("--limit", type=int)
    s.add_argument("--model")
    s.add_argument("--force", action="store_true")
    s.add_argument("--no-synthesize", action="store_true")
    s.add_argument("--backend", choices=["claude", "codex"], help="analyze with this agent for this run only")
    s.add_argument("--dry-run", action="store_true", help="show digest sizes instead of calling the model")
    s.add_argument("--concurrency", type=int, help="parallel analysis processes for this run")
    s.set_defaults(fn=cmd_analyze)

    s = sub.add_parser("synthesize", help="rebuild project knowledge bases")
    s.add_argument("--project", help="project path or name")
    s.add_argument("--global", dest="global_", action="store_true", help="the cross-project playbook")
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_synthesize)

    s = sub.add_parser("sessions", aliases=["ls"], help="list sessions")
    s.add_argument("-p", "--project")
    s.add_argument("--since", help="e.g. 7d, 12h, 2w or a date")
    s.add_argument("--status", help="analysis status filter")
    s.add_argument("-n", "--limit", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_sessions)

    s = sub.add_parser("show", help="show a session overview")
    s.add_argument("session")
    s.add_argument("--transcript", action="store_true", help="print the conversation")
    s.add_argument("--markdown", action="store_true", help="raw Markdown")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)

    s = sub.add_parser("search", help="full-text search across transcripts and knowledge")
    s.add_argument("query", nargs="+")
    s.add_argument("-p", "--project")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.add_argument("--knowledge-only", action="store_true")
    s.add_argument("--sessions-only", action="store_true")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("knowledge", aliases=["kb"], help="browse extracted knowledge")
    s.add_argument("query", nargs="?")
    s.add_argument("-k", "--kind")
    s.add_argument("-p", "--project")
    s.add_argument("-n", "--limit", type=int, default=30)
    s.add_argument("--brief", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_knowledge)

    s = sub.add_parser("projects", help="per-project summary")
    s.set_defaults(fn=cmd_projects)

    s = sub.add_parser("stats", help="usage statistics")
    s.add_argument("--since", help="e.g. 30d")
    s.set_defaults(fn=cmd_stats)

    s = sub.add_parser("ui", aliases=["serve"], help="open the local dashboard")
    s.add_argument("--host")
    s.add_argument("--port", type=int)
    s.add_argument("--open", action="store_true", help="open a browser tab")
    s.set_defaults(fn=cmd_serve)

    s = sub.add_parser("app", help="open the desktop app (macOS; needs the `app` extra)")
    s.set_defaults(fn=cmd_app)

    s = sub.add_parser("export", help="write the Markdown (Obsidian) vault, or export sessions as files")
    s.add_argument("sessions", nargs="*", help="session ids or prefixes: export these (one file, or a .zip of several)")
    s.add_argument("--format", choices=["md", "json", "raw"], default="md",
                   help="with sessions: md (overview + conversation), json (every event) or raw (the original transcript)")
    s.add_argument("--out", help="the vault folder; with sessions, a file or folder to write the export to")
    s.add_argument("--full", action="store_true", help="rewrite every note")
    s.set_defaults(fn=cmd_export)

    s = sub.add_parser("glossary", help="the vocabulary of your projects: terms, aliases, definitions")
    s.add_argument("term", nargs="?")
    s.add_argument("-p", "--project")
    s.add_argument("-c", "--category")
    s.add_argument("--rebuild", action="store_true", help="rebuild with the analysis model (-p PROJECT or --all)")
    s.add_argument("--all", action="store_true")
    s.add_argument("--themes", action="store_true", help="group big categories into themes with the analysis model (the Map's Theme level)")
    s.add_argument("--force", action="store_true", help="with --themes: regroup categories that have not changed")
    s.set_defaults(fn=cmd_glossary)

    s = sub.add_parser("review", help="weekly engineering review written by the analysis model (default: last completed week)")
    s.add_argument("week", nargs="?", help="ISO week like 2026-W39, 'current' or 'last'")
    s.add_argument("--regenerate", action="store_true")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("suggest", aliases=["suggestions"],
                       help="proposed fixes (instruction lines, config changes, setup steps); nothing is written until you apply one")
    s.add_argument("action", nargs="?", choices=["list", "show", "apply", "dismiss", "done", "undo", "move", "refresh"],
                   help="list (default), show ID (the diff), apply ID..., dismiss ID, done ID (a setup step you ran), "
                        "undo ID (take an applied one back out), move ID --to user|project, refresh")
    s.add_argument("ids", nargs="*", type=int, metavar="ID")
    s.add_argument("-p", "--project", help="only this project's suggestions (path or name)")
    s.add_argument("--all", action="store_true", help="also applied, dismissed, stale and done ones")
    s.add_argument("--json", action="store_true")
    s.add_argument("-y", "--yes", action="store_true", help="with apply: don't ask before writing")
    s.add_argument("--reason", help="with dismiss: why (kept for you)")
    s.add_argument("--to", choices=["user", "project"],
                   help="with move: the user-level file (every project) or the files of the projects it came from")
    s.set_defaults(fn=cmd_suggest)

    s = sub.add_parser("friction", help="what goes wrong: recurring failure causes across your sessions, and tool error rates")
    s.add_argument("-p", "--project", help="only this project (path or name)")
    s.add_argument("--days", type=int, help="only the last N days")
    s.add_argument("--json", action="store_true")
    s.add_argument("--noise", action="store_true", help="also show failures that are expected (test runs, read-only checks, provider hiccups)")
    s.set_defaults(fn=cmd_friction)

    s = sub.add_parser("forget", help="remove a session from the vault for good (e.g. it contained secrets)")
    s.add_argument("session")
    s.add_argument("--delete-transcript", action="store_true", help="also delete Claude Code's original transcript")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(fn=cmd_forget)

    s = sub.add_parser("sources", aliases=["connectors"], help="which coding agents are connected and how")
    s.set_defaults(fn=cmd_sources)

    agents = ["claude", "codex", "codex-cloud", "copilot", "bob", "antigravity"]
    clients = ["claude-desktop", "cursor", "windsurf", "gemini"]
    s = sub.add_parser("connect", help="start recording an agent (claude, codex, codex-cloud, copilot, bob, antigravity), or give an MCP client "
                                       "(claude-desktop, cursor, windsurf, gemini) Chronicle's MCP server")
    s.add_argument("name", choices=agents + clients)
    s.add_argument("--exe", help="command the agent should run for Chronicle's MCP server")
    s.add_argument("--no-sync", action="store_true")
    s.set_defaults(fn=cmd_connect, disconnect=False)

    s = sub.add_parser("disconnect", help="stop recording an agent, or remove the MCP server from a client (recorded sessions are kept)")
    s.add_argument("name", choices=agents + clients)
    s.set_defaults(fn=cmd_connect, disconnect=True, exe=None, no_sync=True)

    s = sub.add_parser("import", help="import chats from a claude.ai or ChatGPT data export (the .zip, its folder, or conversations.json)")
    s.add_argument("path")
    s.add_argument("--analyze", action="store_true", help="queue the imported chats for analysis (uses your Claude plan)")
    s.add_argument("--screen", action="store_true", help="then screen them: which are worth analyzing (`chronicle screen`)")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("screen", help="sort imported chats into worth analyzing, maybe and not worth it, reading only "
                                      "their openings; nothing is analyzed until you queue them")
    s.add_argument("--source", choices=["chatgpt", "claude-ai"], help="only this export (default: both)")
    s.add_argument("--limit", type=int, help="screen (or list) at most N chats, newest first")
    s.add_argument("--sample", type=int, metavar="N", help="screen N chats picked at random, to try it first")
    s.add_argument("--redo", action="store_true", help="screen chats again that were screened already")
    s.add_argument("--dry-run", action="store_true", help="count what would be screened; nothing is sent")
    s.add_argument("--list", choices=["analyze", "maybe", "skip"], help="show the chats screened as this, with why")
    s.add_argument("--json", action="store_true", help="with --list: as JSON")
    s.add_argument("--queue", action="store_true", help="queue the chats worth analyzing for the background analysis")
    s.add_argument("--maybe", action="store_true", help="with --queue: the maybes too")
    s.set_defaults(fn=cmd_screen)

    s = sub.add_parser("context", help="print the knowledge digest a new session in this directory would get")
    s.add_argument("--cwd")
    s.set_defaults(fn=cmd_context)

    s = sub.add_parser("config", help="show or edit config.toml")
    s.add_argument("action", nargs="?", choices=["show", "path", "edit", "set"], default="show")
    s.add_argument("key", nargs="?", help="with set: SECTION.KEY, e.g. analysis.backend")
    s.add_argument("value", nargs="?", help="with set: the value (TOML, or a bare word)")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("mcp", help="run the MCP server (stdio); registered by `install` and `connect`")
    s.add_argument("--print-config", action="store_true", help="print a JSON entry to add Chronicle to any MCP client by hand")
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("tailnet", help="reach the dashboard from your phone and other computers through Tailscale")
    s.add_argument("action", nargs="?", choices=["on", "off", "status"], default="status")
    s.add_argument("--anyone", action="store_true", help="with on: let anyone in your tailnet in, not just your login")
    s.set_defaults(fn=cmd_tailnet)

    s = sub.add_parser("hub", help="one archive for several computers: this one records them all (enable), "
                                   "or sends its sessions to one that does (join)")
    s.add_argument("action", nargs="?", choices=["status", "enable", "join", "leave", "disable"], default="status")
    s.add_argument("url", nargs="?", help="with join: the hub's address")
    s.add_argument("--token", help="with join: the token the hub's `chronicle hub enable` printed")
    s.add_argument("--url", dest="url_opt", help=argparse.SUPPRESS)
    s.add_argument("--rotate", action="store_true", help="with enable: make a new token (computers must join again)")
    s.add_argument("--no-push", action="store_true", help="with join: don't send this computer's sessions yet")
    s.set_defaults(fn=cmd_hub)

    s = sub.add_parser("push", help="send this computer's new sessions to its hub now (the background job does this)")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(fn=cmd_push)

    s = sub.add_parser("hook", help=argparse.SUPPRESS)
    s.add_argument("event", choices=["session-end", "session-start", "stop", "pre-compact"])
    s.set_defaults(fn=cmd_hook)

    s = sub.add_parser("ingest-session", help=argparse.SUPPRESS)
    s.add_argument("transcript", nargs="?")
    s.add_argument("--ended", action="store_true")
    s.add_argument("--work", action="store_true")
    s.set_defaults(fn=cmd_ingest_session)
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["hook"] and len(argv) >= 2:  # fast path: no argparse/rich import cost
        from .hooks import hook_main

        return hook_main(argv[1])
    if argv[:1] == ["statusline"]:  # Claude Code runs this after every turn: same fast path
        from .statusline import main as statusline_main

        return statusline_main()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        from .config import chronicle_home

        parser.print_help()
        if not (chronicle_home() / "config.toml").exists():
            print("\nNew here? Run `chronicle install` to pick which coding agents to record and start the dashboard.")
        return 0
    try:
        return args.fn(args) or 0
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0
