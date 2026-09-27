"""Process-level tests: MCP server, HTTP API, hooks, installer."""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from chronicle.db import connect
from chronicle.install import hooks_installed, install_hooks, uninstall_hooks

from conftest import CWD, SID


def _run_mcp(env, messages):
    proc = subprocess.run(
        [sys.executable, "-m", "chronicle", "mcp"],
        input="\n".join(json.dumps(m) for m in messages) + "\n",
        capture_output=True, text=True, timeout=60, env={**os.environ}, cwd=CWD if os.path.isdir(CWD) else None,
    )
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_mcp_server_protocol(synced):
    from chronicle.analyze import analyze_session

    analyze_session(synced["conn"], synced["cfg"], SID)
    out = _run_mcp(synced, [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_knowledge", "arguments": {"query": "TTL"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_session", "arguments": {"session_id": SID[:8]}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "search_sessions", "arguments": {"query": "logout", "project": "demo-app"}}},
        {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "get_transcript", "arguments": {"session_id": SID, "limit": 3}}},
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "recent_sessions", "arguments": {"days": 100000}}},
        {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "project_knowledge", "arguments": {"project": "demo-app"}}},
        {"jsonrpc": "2.0", "id": 9, "method": "nope"},
        {"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "get_session", "arguments": {"bogus": 1}}},
    ])
    by_id = {m["id"]: m for m in out}
    assert by_id[1]["result"]["protocolVersion"] == "2025-06-18"
    assert by_id[1]["result"]["serverInfo"]["name"] == "chronicle"
    assert {t["name"] for t in by_id[2]["result"]["tools"]} >= {"search_knowledge", "search_sessions", "get_session", "project_knowledge"}
    text = lambda i: by_id[i]["result"]["content"][0]["text"]  # noqa: E731
    assert "Token TTL compared in seconds vs ms" in text(3)
    assert "Fixed login token expiry bug" in text(4)
    assert "logout" in text(5).lower()
    assert "USER" in text(6) and "more: call again with offset=3" in text(6)
    assert SID[:8] in text(7)
    assert "Token TTL" in text(8)
    assert by_id[9]["error"]["code"] == -32601
    assert by_id[10]["result"]["isError"] is True
    assert len(out) == 10  # the notification got no reply


def test_http_api(synced):
    from chronicle.server import App, make_handler

    app = App(synced["cfg"])
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = make_handler(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def get(path, headers=None):
        req = urllib.request.Request(base + path, headers=headers or {})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()

    try:
        for path in ("/api/overview?days=all", "/api/sessions", f"/api/sessions/{SID}", f"/api/sessions/{SID[:8]}/events",
                     "/api/projects", "/api/knowledge", "/api/search?q=login", "/api/status", "/api/glossary",
                     "/api/glossary/terms", "/api/reviews", "/"):
            status, body = get(path)
            assert status == 200, path
        data = json.loads(get(f"/api/sessions/{SID}")[1])
        assert data["n_prompts"] == 2 and data["agents"][1]["agent_id"]
        sessions = json.loads(get("/api/sessions?sort=est_cost_usd&order=asc")[1])
        assert sessions["total"] == 2
        projects = json.loads(get("/api/projects")[1])  # project cards: 12 weekly buckets, outcomes, agents
        assert all(len(p["weekly"]) == 12 and isinstance(p["outcomes"], dict) and p["agents"] for p in projects)
        daily = json.loads(get("/api/overview?days=all")[1])["daily"]  # stat-tile sparklines
        assert daily and {"tool_calls", "lines_added"} <= set(daily[0])
        try:
            get("/api/status", {"Host": "attacker.example:80"})
            raise AssertionError("foreign Host header accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        req = urllib.request.Request(base + "/api/sync", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("POST without X-Chronicle header accepted")
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
        kid = synced["conn"].execute("SELECT id FROM knowledge LIMIT 1").fetchone()[0]
        req = urllib.request.Request(base + f"/api/knowledge/{kid}", data=b'{"pinned": true}', method="POST",
                                     headers={"X-Chronicle": "1", "Content-Type": "application/json"})
        assert json.loads(urllib.request.urlopen(req, timeout=10).read())["ok"] is True
    finally:
        httpd.shutdown()


def test_install_hooks_preserves_existing_settings(env, tmp_path):
    cfg = env["cfg"]
    settings = env["claude_dir"] / "settings.json"
    settings.write_text(json.dumps({
        "permissions": {"defaultMode": "auto"},
        "hooks": {"SessionEnd": [{"hooks": [{"type": "command", "command": "other-tool --flag"}]}],
                  "Stop": [{"hooks": [{"type": "command", "command": "notify-me"}]}]},
    }))
    install_hooks(cfg, "/opt/bin/chronicle", inject=True)
    install_hooks(cfg, "/opt/bin/chronicle", inject=True)  # idempotent
    data = json.loads(settings.read_text())
    assert data["permissions"] == {"defaultMode": "auto"}
    cmds = [h["command"] for g in data["hooks"]["SessionEnd"] for h in g["hooks"]]
    assert cmds.count("/opt/bin/chronicle hook session-end") == 1 and "other-tool --flag" in cmds
    assert hooks_installed(cfg) == {"SessionEnd": True, "SessionStart": True}
    assert list((cfg.home / "backups").glob("settings.json.*.bak"))
    uninstall_hooks(cfg)
    data = json.loads(settings.read_text())
    assert [h["command"] for g in data["hooks"]["SessionEnd"] for h in g["hooks"]] == ["other-tool --flag"]
    assert "SessionStart" not in data["hooks"] and data["hooks"]["Stop"]


def test_session_end_hook_detaches_and_ingests(env):
    payload = json.dumps({"session_id": SID, "transcript_path": str(env["main"]), "cwd": CWD, "hook_event_name": "SessionEnd"})
    t0 = time.monotonic()
    proc = subprocess.run([sys.executable, "-m", "chronicle", "hook", "session-end"], input=payload, capture_output=True,
                          text=True, timeout=30, env={**os.environ, "FAKE_CLAUDE_MODE": "ok"})
    elapsed = time.monotonic() - t0
    assert proc.returncode == 0 and elapsed < 5, (proc.stderr, elapsed)
    deadline = time.monotonic() + 60
    status = None
    while time.monotonic() < deadline:
        if env["cfg"].db_path.exists():
            conn = connect(env["cfg"].db_path)
            row = conn.execute("SELECT ended_flag, analysis_status FROM sessions WHERE id=?", (SID,)).fetchone()
            conn.close()
            if row and row["analysis_status"] == "done":
                status = dict(row)
                break
        time.sleep(0.5)
    assert status == {"ended_flag": 1, "analysis_status": "done"}, (env["home"] / "logs" / "hooks.log").read_text()


def test_hooks_are_inert_for_internal_runs(env):
    proc = subprocess.run([sys.executable, "-m", "chronicle", "hook", "session-end"], input="{}", capture_output=True,
                          text=True, timeout=30, env={**os.environ, "CHRONICLE_INTERNAL": "1"})
    assert proc.returncode == 0
    time.sleep(1)
    assert not env["cfg"].db_path.exists() or connect(env["cfg"].db_path).execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_session_start_context(synced):
    from chronicle.analyze import analyze_session
    from chronicle.hooks import build_session_context
    from chronicle.synthesize import synthesize_project

    analyze_session(synced["conn"], synced["cfg"], SID)
    synthesize_project(synced["conn"], synced["cfg"], CWD)
    ctx = build_session_context(synced["cfg"], CWD + "/src")
    assert ctx and "demo-app" in ctx and "Token TTL unit mismatch." in ctx and len(ctx) <= synced["cfg"].inject_max_chars
    assert build_session_context(synced["cfg"], "/somewhere/else") is None


def test_dashboard_picks_up_config_changes(synced):
    from chronicle.config import set_config_value
    from chronicle.server import App

    app = App(synced["cfg"])
    assert app.cfg.codex_dirs == []
    import time as _t

    _t.sleep(0.01)
    set_config_value(app.cfg, "sources", "codex_dirs", '["~/.codex"]')
    app.refresh_config()
    assert app.cfg.codex_dirs and app.cfg.codex_dirs[0].name == ".codex"
