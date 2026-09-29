import json
from pathlib import Path

import pytest

from chronicle.bob_parser import load_tasks, parse_bob_task
from chronicle.config import load_config
from chronicle.copilot_parser import (load_chat, load_usage, parse_copilot_agent, parse_vscode_chat, uri_path,
                                      workspace_folder)
from chronicle.db import connect as db_connect
from chronicle.ingest import sync

from copilot_fixture import (AGENT_ID, BOB_EMPTY, BOB_TASK, CHAT_ID, EMPTY_CHAT, FOLDER, write_bob_home,
                             write_copilot_home, write_vscode_user)


@pytest.fixture()
def stores(env, monkeypatch):
    t = env["tmp"]
    env["vscode"] = write_vscode_user(t / "Code" / "User")
    env["copilot"] = write_copilot_home(t / "copilot")
    env["bob"] = write_bob_home(t / "bob")
    monkeypatch.setenv("COPILOT_HOME", str(env["copilot"]))
    monkeypatch.setenv("BOB_HOME", str(env["bob"]))
    monkeypatch.setattr("chronicle.connectors.vscode_user_dirs", lambda: [env["vscode"]])
    return env


def test_vscode_chat_replays_patches(stores):
    f = next((stores["vscode"] / "workspaceStorage").glob(f"*/chatSessions/{CHAT_ID}.jsonl"))
    state = load_chat(f)
    assert state["customTitle"] == "Health endpoint" and state["requests"][0]["response"][0]["kind"] == "thinking"
    ps = parse_vscode_chat(f, workspace_folder(f))
    assert ps.id == CHAT_ID and ps.project_path == FOLDER and ps.custom_title == "Health endpoint"
    assert ps.n_prompts == 1 and ps.first_prompt == "Add a health endpoint and run the tests"
    assert [t.name for t in ps.tool_calls] == ["read_file", "run_in_terminal"] and ps.tool_calls[1].command == "pytest -q"
    app = ps.files[f"{FOLDER}/app.py"]
    assert app.reads == 1 and app.edits == 1 and app.lines_added == 3
    assert ps.api_calls[0].input_tokens == 12000 and ps.primary_model == "claude-sonnet-4-6"
    assert round(ps.duration_s) == 31  # creation → request end
    assert parse_vscode_chat(f.with_name(f"{EMPTY_CHAT}.jsonl")) is None
    assert uri_path("vscode-remote://ssh-remote%2Bvm/root/app") == "vm:/root/app"


def test_copilot_agent_session(stores):
    usage = load_usage(stores["copilot"])
    ps = parse_copilot_agent(stores["copilot"] / "session-state" / AGENT_ID, usage[AGENT_ID])
    assert ps.id == AGENT_ID and ps.project_path == FOLDER and ps.entrypoint == "copilot:cli" and ps.cc_version == "1.2.3"
    assert ps.n_prompts == 1 and [e.kind for e in ps.events].count("thinking") == 1
    bash, edit = ps.tool_calls
    assert bash.is_error and bash.duration_ms == 5000 and bash.command == "pytest -x" and not edit.is_error
    assert ps.lines_added == 4 and ps.lines_removed == 1
    first = ps.api_calls[0]
    assert (first.input_tokens, first.cache_write_tokens) == (10, 9990) and ps.totals()["cost"] > 0


def test_bob_task(stores):
    tasks = load_tasks(stores["bob"])
    assert {t["id"] for t in tasks} == {BOB_TASK, BOB_EMPTY}
    ps = parse_bob_task(next(t for t in tasks if t["id"] == BOB_TASK))
    assert ps.project_path == FOLDER and ps.first_prompt == "Show progress by site" and ps.custom_title == "Dashboard by site"
    assert ps.tool_calls[0].name == "list_files" and ps.n_api_errors == 1
    assert ps.api_calls[0].cost_usd == 0.02
    assert parse_bob_task(next(t for t in tasks if t["id"] == BOB_EMPTY)) is None


def test_sync_copilot_and_bob(stores):
    cfg = stores["cfg"]
    cfg.copilot_dirs = [stores["copilot"], stores["vscode"]]
    cfg.bob_dirs = [stores["bob"]]
    conn = db_connect(cfg.db_path)
    report = sync(cfg, conn)
    assert not report.errors
    rows = {r["id"]: dict(r) for r in conn.execute("SELECT id, agent, title, project_path, n_tool_calls FROM sessions WHERE agent != 'claude'")}
    assert rows[CHAT_ID]["agent"] == "copilot" and rows[CHAT_ID]["title"] == "Health endpoint"
    assert rows[AGENT_ID]["agent"] == "copilot" and rows[BOB_TASK]["agent"] == "bob"
    assert EMPTY_CHAT not in rows and BOB_EMPTY not in rows
    assert (cfg.archive_dir / "copilot" / "session-store.db").exists() and (cfg.archive_dir / "bob" / "bob.db").exists()
    archived = {p.name for p in cfg.archive_dir.rglob("*")}
    assert "auth-secrets.json" not in archived and f"{CHAT_ID}.jsonl.gz" in archived
    again = sync(cfg, conn)
    assert again.sessions_new == 0 and again.sessions_updated == 0


def test_connect_registers_mcp_and_keeps_other_servers(stores):
    from chronicle.connectors import all_status, connect, disconnect

    cfg = stores["cfg"]
    status = {c["name"]: c for c in all_status(cfg, db_connect(cfg.db_path))}
    assert status["copilot"]["detected"] and not status["copilot"]["connected"] and status["bob"]["on_disk"] == 1
    connect(cfg, "copilot", "/opt/bin/chronicle")
    connect(cfg, "bob", "/opt/bin/chronicle")
    cfg = load_config(cfg.home)
    assert stores["copilot"] in cfg.copilot_dirs and cfg.bob_dirs == [stores["bob"]]
    vs = json.loads((stores["vscode"] / "mcp.json").read_text())["servers"]["chronicle"]
    assert vs == {"type": "stdio", "command": "/opt/bin/chronicle", "args": ["mcp"]}
    cli = json.loads((stores["copilot"] / "mcp-config.json").read_text())["mcpServers"]
    assert set(cli) == {"other", "chronicle"}
    assert "chronicle" in json.loads((stores["bob"] / "settings" / "mcp_settings.json").read_text())["mcpServers"]
    disconnect(cfg, "copilot")
    disconnect(cfg, "bob")
    assert set(json.loads((stores["copilot"] / "mcp-config.json").read_text())["mcpServers"]) == {"other"}
    assert load_config(cfg.home).copilot_dirs == [] and load_config(cfg.home).bob_dirs == []


def test_mcp_clients_get_the_server_and_keep_their_settings(env, monkeypatch):
    from chronicle import connectors
    from chronicle.connectors import connect, disconnect, mcp_clients_status

    home = env["tmp"] / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(connectors, "APPLICATIONS", env["tmp"] / "Applications")
    monkeypatch.setattr(connectors.shutil, "which", lambda name: None)
    cfg = env["cfg"]
    status = {c["name"]: c for c in mcp_clients_status()}
    assert not status["cursor"]["detected"] and not status["cursor"]["registered"]
    assert connect(cfg, "cursor", "/opt/bin/chronicle") == ["Cursor not found on this Mac; nothing changed"]
    assert not (home / ".cursor").exists()

    (home / ".cursor").mkdir(parents=True)
    gemini = home / ".gemini" / "settings.json"
    gemini.parent.mkdir()
    gemini.write_text(json.dumps({"theme": "Dracula", "mcpServers": {"other": {"command": "x"}}}))
    (env["tmp"] / "Applications" / "Claude.app").mkdir(parents=True)
    for name in ("cursor", "gemini", "claude-desktop"):
        connect(cfg, name, "/opt/bin/chronicle")
    entry = {"command": "/opt/bin/chronicle", "args": ["mcp"]}
    assert json.loads((home / ".cursor" / "mcp.json").read_text()) == {"mcpServers": {"chronicle": entry}}
    desktop = home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    assert json.loads(desktop.read_text())["mcpServers"]["chronicle"] == entry
    data = json.loads(gemini.read_text())
    assert data["theme"] == "Dracula" and set(data["mcpServers"]) == {"other", "chronicle"}
    assert {c["name"] for c in mcp_clients_status() if c["registered"]} == {"cursor", "gemini", "claude-desktop"}
    assert "already registered" in connect(cfg, "cursor", "/opt/bin/chronicle")[0]
    assert load_config(cfg.home).claude_dirs == cfg.claude_dirs  # clients are not recording sources

    disconnect(cfg, "gemini")
    assert json.loads(gemini.read_text()) == {"theme": "Dracula", "mcpServers": {"other": {"command": "x"}}}
