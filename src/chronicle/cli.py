"""Command line interface: `chronicle <command>`."""

from __future__ import annotations

import argparse
import json
import sys


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
    from .util import setup_logging

    cfg = _cfg()
    setup_logging(cfg.logs_dir, verbose=args.verbose)
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
    if args.dry_run:
        from .digest import build_digest

        total = 0
        for sid in ids:
            header, d = build_digest(conn, sid, cfg.analysis.chunk_chars)
            total += d.chars
            print(f"{sid[:8]}  level {d.level}  {d.chars:>9,} chars  {len(d.chunks)} chunk(s)")
        print(f"{len(ids)} session(s), {total:,} chars (~{total // 4:,} input tokens) with model {args.model or cfg.analysis.model}")
        return 0
    conn.close()
    if args.concurrency:
        cfg.analysis.concurrency = args.concurrency
    print(f"analyzing {len(ids)} session(s) with {args.model or cfg.analysis.model}…")
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
                console.print(f"      [dim]{sn['kind']}:[/] {sn['text']}", highlight=False, markup=False)
    return 0


def cmd_knowledge(args) -> int:
    from .search import search_knowledge

    cfg = _cfg()
    conn = _conn(cfg)
    console = _console()
    rows = search_knowledge(conn, args.query, project=args.project, kind=args.kind, limit=args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1, default=str))
        return 0
    for k in rows:
        console.print(f"[cyan]{k['kind']}[/] [bold]{k['title']}[/] [dim]({k.get('project_name') or '-'}, "
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
    from .install import UI_LABEL, hooks_installed, launchd_status, mcp_registered
    from .util import human_cost, local_str
    from .worker import PAUSE_KEY, count_pending

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
    console.print(f"  {ok(hooks.get('SessionEnd'))} SessionEnd hook   {ok(hooks.get('SessionStart'))} SessionStart context hook"
                  f"{' (optional)' if not cfg.inject_session_start else ''}")
    ui = launchd_status(UI_LABEL)
    console.print(f"  {ok(ld.get('loaded'))} background sync agent (runs: {ld.get('runs', '-')}, last exit: {ld.get('last_exit', '-')})")
    console.print(f"  {ok(ui.get('loaded'))} dashboard agent: http://127.0.0.1:{cfg.server_port}/")
    console.print(f"  {ok(mcp_registered())} MCP server registered   {ok(cfg.claude_bin())} claude CLI: {cfg.claude_bin() or 'not found'}")
    console.print(f"  sessions: {sum(counts.values())} · " + " · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    console.print(f"  analysis queue: {pending['ready']} ready now, {pending['queued']} pending/stale · "
                  f"model {cfg.analysis.model} · auto={'on' if cfg.analysis.auto else 'off'} · spent {human_cost(spent)}")
    paused = kv_get(conn, PAUSE_KEY)
    if paused:
        console.print(f"  analysis paused until {local_str(paused)}")
    console.print(f"  last sync: {local_str(kv_get(conn, 'last_sync'))} · db {cfg.db_path.stat().st_size / 1e6:.0f} MB · notes {cfg.notes_dir}")
    for r in conn.execute("SELECT id, analysis_reason FROM sessions WHERE analysis_status='error' ORDER BY ended_at DESC LIMIT 5"):
        console.print(f"  [red]error[/] {r['id'][:8]}: {(r['analysis_reason'] or '')[:160]}", highlight=False)
    return 0


def cmd_install(args) -> int:
    from .db import kv_get, kv_set
    from .install import executable, install_hooks, install_launchd, install_mcp, install_ui_agent
    from .util import utcnow_iso

    cfg = _cfg()
    exe = args.exe or executable()
    actions = []
    if " -m " in exe:
        print(f"note: `chronicle` is not on PATH; hooks will run `{exe}`. Install with `uv tool install` for a stable path.")
    if not args.no_hooks:
        actions += install_hooks(cfg, exe, inject=args.inject_context, dry_run=args.dry_run)
    if args.inject_context and not args.dry_run:
        _set_config_value(cfg, "inject", "session_start", "true")
    if not args.no_launchd:
        actions += install_launchd(cfg, exe, interval=args.interval * 60, dry_run=args.dry_run)
    if not args.no_ui:
        actions += install_ui_agent(cfg, exe, dry_run=args.dry_run)
    if not args.no_mcp:
        actions += install_mcp(cfg, exe, dry_run=args.dry_run)
    for a in actions:
        print(f"• {a}")
    if not args.dry_run:
        conn = _conn(cfg)
        if not kv_get(conn, "installed_at"):
            kv_set(conn, "installed_at", utcnow_iso())
            conn.commit()
        conn.close()
        print(f"\nConfig: {cfg.config_path}\nData:   {cfg.home}\nNext:   chronicle sync --work   ·   chronicle ui")
    return 0


def _set_config_value(cfg, section: str, key: str, value: str) -> None:
    from .config import set_config_value

    set_config_value(cfg, section, key, value)


def cmd_uninstall(args) -> int:
    import shutil

    from .connectors import mcp_clients_status, remove_mcp_client
    from .install import uninstall_hooks, uninstall_launchd, uninstall_mcp

    cfg = _cfg()
    actions = uninstall_hooks(cfg) + uninstall_launchd() + uninstall_mcp(cfg)
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
    if args.action == "path":
        print(cfg.config_path)
    elif args.action == "edit":
        editor = os.environ.get("EDITOR", "open" if sys.platform == "darwin" else "vi")
        subprocess.call([*editor.split(), str(cfg.config_path)])
    else:
        print(cfg.config_path.read_text())
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
        print(f"grouping {len(due)} categor{'y' if len(due) == 1 else 'ies'} into themes with Claude…")
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
        print(f"building {len(targets)} glossar{'y' if len(targets) == 1 else 'ies'} with Claude…")
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
    print(f"writing review for {key} with Claude…")
    try:
        generate_review(conn, cfg, key)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    _console().print(Markdown(conn.execute("SELECT markdown FROM reviews WHERE period = ?", (key,)).fetchone()[0]))
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
    if counts["new"] + counts["updated"]:
        print("queued for analysis (`chronicle work` runs it now)" if args.analyze
              else "not analyzed: open a chat and choose Analyze now, or re-run with --analyze to queue them all")
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


def cmd_context(args) -> int:
    import os

    from .hooks import build_session_context

    cfg = _cfg()
    print(build_session_context(cfg, args.cwd or os.getcwd()) or "(no knowledge recorded for this directory yet)")
    return 0


# ---------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chronicle",
        description="Record, archive and analyze every coding-agent session (Claude Code, Codex, GitHub Copilot, IBM Bob); "
                    "extract reusable knowledge.",
    )
    sub = p.add_subparsers(dest="command", required=True, metavar="<command>")

    s = sub.add_parser("install", help="install hooks, the background agent and the MCP server")
    s.add_argument("--no-hooks", action="store_true")
    s.add_argument("--no-launchd", action="store_true")
    s.add_argument("--no-mcp", action="store_true")
    s.add_argument("--no-ui", action="store_true", help="don't keep the dashboard running in the background")
    s.add_argument("--inject-context", action="store_true", help="also add a SessionStart hook that injects project knowledge")
    s.add_argument("--interval", type=int, default=15, help="background sync interval in minutes (default 15)")
    s.add_argument("--exe", help="command used by hooks/launchd (default: the installed `chronicle`)")
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
    s.add_argument("--dry-run", action="store_true", help="show digest sizes instead of calling Claude")
    s.add_argument("--concurrency", type=int, help="parallel claude processes for this run")
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
    s.add_argument("--rebuild", action="store_true", help="rebuild with Claude (-p PROJECT or --all)")
    s.add_argument("--all", action="store_true")
    s.add_argument("--themes", action="store_true", help="group big categories into themes with Claude (the Map's Theme level)")
    s.add_argument("--force", action="store_true", help="with --themes: regroup categories that have not changed")
    s.set_defaults(fn=cmd_glossary)

    s = sub.add_parser("review", help="weekly engineering review written by Claude (default: last completed week)")
    s.add_argument("week", nargs="?", help="ISO week like 2026-W39, 'current' or 'last'")
    s.add_argument("--regenerate", action="store_true")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("forget", help="remove a session from the vault for good (e.g. it contained secrets)")
    s.add_argument("session")
    s.add_argument("--delete-transcript", action="store_true", help="also delete Claude Code's original transcript")
    s.add_argument("-y", "--yes", action="store_true")
    s.set_defaults(fn=cmd_forget)

    s = sub.add_parser("sources", aliases=["connectors"], help="which coding agents are connected and how")
    s.set_defaults(fn=cmd_sources)

    agents = ["claude", "codex", "codex-cloud", "copilot", "bob"]
    clients = ["claude-desktop", "cursor", "windsurf", "gemini"]
    s = sub.add_parser("connect", help="start recording an agent (claude, codex, codex-cloud, copilot, bob), or give an MCP client "
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
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("context", help="print the knowledge digest a new session in this directory would get")
    s.add_argument("--cwd")
    s.set_defaults(fn=cmd_context)

    s = sub.add_parser("config", help="show or edit config.toml")
    s.add_argument("action", nargs="?", choices=["show", "path", "edit"], default="show")
    s.set_defaults(fn=cmd_config)

    s = sub.add_parser("mcp", help="run the MCP server (stdio); registered by `install` and `connect`")
    s.add_argument("--print-config", action="store_true", help="print a JSON entry to add Chronicle to any MCP client by hand")
    s.set_defaults(fn=cmd_mcp)

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
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0
