"""Synthetic GitHub Copilot (VS Code chat + agent) and IBM Bob stores mirroring the real formats."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

CHAT_ID = "c0c0c0c0-1111-2222-3333-444444444444"
EMPTY_CHAT = "c0c0c0c0-0000-0000-0000-000000000000"
AGENT_ID = "a9a9a9a9-1111-2222-3333-444444444444"
BOB_TASK = "b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0"
BOB_EMPTY = "b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1"
BOB_TOOLS = "b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"  # Bob's own toolCalls shape, with a subagent inside
BOB_SUB = "5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b"
FOLDER = "/Users/test/Projects/copilot-app"
T0 = 1790000000000  # ms


def _ops(*ops) -> str:
    return "\n".join(json.dumps(o) for o in ops) + "\n"


def write_vscode_user(root: Path) -> Path:
    ws = root / "workspaceStorage" / "abc123"
    (ws / "chatSessions").mkdir(parents=True)
    (ws / "workspace.json").write_text(json.dumps({"folder": f"file://{FOLDER}"}))
    request = {
        "requestId": "request_1", "timestamp": T0 + 1000, "modelId": "copilot/claude-sonnet-4.6",
        "message": {"text": "Add a health endpoint and run the tests"},
        "modeInfo": {"modeName": "agent"}, "agent": {"id": "github.copilot.editsAgent"},
        "response": [
            {"kind": "thinking", "value": "Plan the endpoint"},
            {"value": "Added `/health` and the tests pass."},
            {"kind": "textEditGroup", "uri": {"fsPath": f"{FOLDER}/app.py"},
             "edits": [[{"text": "@app.get('/health')\ndef health():\n    return {'ok': True}\n",
                         "range": {"startLineNumber": 10, "startColumn": 1, "endLineNumber": 10, "endColumn": 1}}]]},
        ],
        "result": {"timings": {"totalElapsed": 30000}, "metadata": {
            "promptTokens": 12000, "outputTokens": 300, "resolvedModel": "claude-sonnet-4-6",
            "toolCallRounds": [
                {"response": "", "thinking": {"text": "Check the app first"}, "toolCalls": [
                    {"id": "t1", "name": "read_file", "arguments": json.dumps({"filePath": f"{FOLDER}/app.py"})}]},
                {"response": "", "toolCalls": [
                    {"id": "t2", "name": "run_in_terminal", "arguments": json.dumps({"command": "pytest -q"})}]},
                {"response": "Added `/health` and the tests pass.", "toolCalls": []},
            ],
            "toolCallResults": {"t1": {"content": [{"value": "from fastapi import FastAPI"}]},
                                "t2": {"content": [{"value": "3 passed"}]}}}},
    }
    (ws / "chatSessions" / f"{CHAT_ID}.jsonl").write_text(_ops(
        {"kind": 0, "v": {"version": 3, "sessionId": CHAT_ID, "creationDate": T0, "requests": [], "inputState": {"inputText": ""}}},
        {"kind": 1, "k": ["inputState", "inputText"], "v": "Add a health"},
        {"kind": 2, "k": ["requests"], "v": [dict(request, response=[], result=None)]},
        {"kind": 2, "k": ["requests", 0, "response"], "v": [{"value": "partial"}]},
        {"kind": 2, "k": ["requests", 0, "response"], "i": 0, "v": request["response"]},  # truncate + replace
        {"kind": 1, "k": ["requests", 0, "result"], "v": request["result"]},
        {"kind": 1, "k": ["customTitle"], "v": "Health endpoint"},
    ))
    (ws / "chatSessions" / f"{EMPTY_CHAT}.jsonl").write_text(_ops(
        {"kind": 0, "v": {"version": 3, "sessionId": EMPTY_CHAT, "creationDate": T0, "requests": []}}))
    return root


def write_copilot_home(root: Path) -> Path:
    sdir = root / "session-state" / AGENT_ID
    sdir.mkdir(parents=True)
    (sdir / "workspace.yaml").write_text(f"id: {AGENT_ID}\ncwd: {FOLDER}\nclient_name: cli\nname: Fix the flaky test\nuser_named: false\n")
    ev = lambda t, ts, **d: json.dumps({"type": t, "timestamp": ts, "id": ts, "data": d})
    (sdir / "events.jsonl").write_text("\n".join([
        ev("session.start", "2026-09-21T10:00:00.000Z", sessionId=AGENT_ID, copilotVersion="1.2.3", context={"cwd": FOLDER}),
        ev("user.message", "2026-09-21T10:00:01.000Z", content="Fix the flaky test"),
        ev("assistant.message", "2026-09-21T10:00:03.000Z", model="gpt-5.6-luna", content="Running the tests.", reasoningText="Look at the test"),
        ev("tool.execution_start", "2026-09-21T10:00:04.000Z", toolCallId="c1", toolName="bash", arguments={"command": "pytest -x"}),
        ev("tool.execution_complete", "2026-09-21T10:00:09.000Z", toolCallId="c1", success=False, result={"content": "1 failed"}),
        ev("tool.execution_start", "2026-09-21T10:00:10.000Z", toolCallId="c2", toolName="edit", arguments={"path": f"{FOLDER}/test_app.py"}),
        ev("tool.execution_complete", "2026-09-21T10:00:11.000Z", toolCallId="c2", success=True, result={"content": "ok"}),
        ev("assistant.message", "2026-09-21T10:00:20.000Z", model="gpt-5.6-luna", content="Seeded the RNG; the test is stable."),
        ev("session.shutdown", "2026-09-21T10:00:30.000Z", codeChanges={"linesAdded": 4, "linesRemoved": 1, "filesModified": [f"{FOLDER}/test_app.py"]}),
    ]) + "\n")
    db = sqlite3.connect(root / "session-store.db")
    db.execute("CREATE TABLE assistant_usage_events (id INTEGER PRIMARY KEY, session_id TEXT, turn_index INTEGER, agent_id TEXT, model TEXT, "
               "input_tokens INTEGER, output_tokens INTEGER, cache_read_tokens INTEGER, cache_write_tokens INTEGER, duration_ms INTEGER, created_at TEXT)")
    db.executemany("INSERT INTO assistant_usage_events(session_id, turn_index, model, input_tokens, output_tokens, cache_read_tokens, "
                   "cache_write_tokens, duration_ms, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                   [(AGENT_ID, 0, "gpt-5.6-luna", 10000, 200, 0, 9990, 3000, "2026-09-21T10:00:03.000Z"),
                    (AGENT_ID, 0, "gpt-5.6-luna", 10500, 150, 9990, 500, 2000, "2026-09-21T10:00:20.000Z")])
    db.commit()
    db.close()
    (root / "mcp-config.json").write_text(json.dumps({"mcpServers": {"other": {"type": "http", "url": "http://x"}}}))
    return root


def write_bob_home(root: Path) -> Path:
    (root / "db").mkdir(parents=True)
    (root / "settings").mkdir()
    (root / "settings" / "mcp_settings.json").write_text(json.dumps({"mcpServers": {}}))
    (root / "settings" / "auth-secrets.json").write_text('{"token": "must-never-be-read"}')
    db = sqlite3.connect(root / "db" / "bob.db")
    db.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, parent_id TEXT, title TEXT NOT NULL DEFAULT '', "
               "status TEXT, first_message TEXT, directory TEXT NOT NULL, version TEXT, git_sha TEXT, git_branch TEXT, env TEXT, "
               "costs TEXT, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, task_type TEXT, last_error TEXT)")
    db.execute("CREATE TABLE messages (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, role TEXT NOT NULL, data TEXT NOT NULL, created_at INTEGER NOT NULL)")
    costs = json.dumps({"input": 900, "output": 120, "cacheRead": 4000, "cacheWrite": 0, "cost": 0.02})
    db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (BOB_TASK, f"file:{FOLDER}", None, "Dashboard by site", "error", None, "", "1.0", None, "main", None, costs,
                T0, T0 + 60000, "normal", "rate limited"))
    db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (BOB_EMPTY, f"file:{FOLDER}", None, "", "active", None, "", None, None, None, None, None, T0, T0, "normal", None))
    msgs = [
        ("m1", "system", {"role": "system", "content": "<role_definition>You are Bob</role_definition>"}),
        ("m2", "user", {"role": "user", "content": "<task>Show progress by site</task>\n<environment_details>cwd: x</environment_details>"}),
        ("m3", "assistant", {"role": "assistant", "content": "Listing files.", "tool_calls": [
            {"id": "tc1", "type": "function", "function": {"name": "list_files", "arguments": json.dumps({"path": FOLDER})}}]}),
        ("m4", "tool", {"role": "tool", "tool_call_id": "tc1", "content": "app.py\nviews.py"}),
    ]
    for i, (mid, role, data) in enumerate(msgs):
        db.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (mid, BOB_TASK, role, json.dumps(data), T0 + i * 1000))
    _bob_tools_task(db)
    db.commit()
    db.close()
    return root


def _bob_tools_task(db) -> None:
    """The shape Bob writes today: toolCalls, results linked by toolUsage.signature, per-message spend, a subagent's
    conversation inside its spawn_subagent result, and workspace-relative paths."""
    costs = json.dumps({"cost": 0.35, "contextTokens": 30000})  # no token split, only Bob's own figure
    db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (BOB_TOOLS, f"file:{FOLDER}", None, "Explainer page", "active", None, FOLDER, None, None, None, None, costs,
                T0, T0 + 60000, "normal", None))

    def call(cid, name, args):
        return {"id": cid, "name": name, "arguments": args}

    def result(cid, name, args, content, *, error=False, **meta):
        return {"role": "tool", "content": content, "toolUsage": {"signature": {"id": cid, "name": name, "arguments": args,
                                                                                "isError": error}},
                "_meta": {"durationMs": 40, **meta}}

    page = {"path": "docs/explainer.html", "content": "<!DOCTYPE html><html><body>hi</body></html>"}
    art = {"id": "x", "title": "Explainer", "html": "<script></script>"}
    notes = {"path": "notes/findings.md", "content": "# Findings"}
    brief = {"name": "explore", "description": "Find how the dashboard groups sites"}
    sub = [
        {"role": "system", "content": "You are a fast codebase exploration agent."},
        {"role": "user", "content": "Find how the dashboard groups sites", "_meta": {"timestamp": T0 + 3500}},
        {"role": "assistant", "content": "", "toolCalls": [call("s1", "write_file", notes)],
         "_meta": {"timestamp": T0 + 3600, "spend": {"cost": 0.01, "contextTokens": 5000}}},
        result("s1", "write_file", notes, "Created file: notes/findings.md"),
        {"role": "assistant", "content": "Done.", "_meta": {"timestamp": T0 + 3800, "spend": {"cost": 0.002, "contextTokens": 5200}}},
    ]
    msgs = [
        ("n1", "user", {"role": "user", "content": "<user_message>Make an explainer page</user_message>"}),
        ("n2", "assistant", {"role": "assistant", "content": "Researching first.", "toolCalls": [call("t1", "spawn_subagent", brief)],
                             "_meta": {"spend": {"cost": 0.1, "contextTokens": 20000}}}),
        ("n3", "tool", result("t1", "spawn_subagent", brief, "<task_result>Sites group by region</task_result>",
                              subagentId=BOB_SUB, agentType="explore") | {"messages": sub}),
        ("n4", "assistant", {"role": "assistant", "content": "", "toolCalls": [call("t2", "create_html_artifact", art)],
                             "_meta": {"spend": {"cost": 0.11, "contextTokens": 25000}}}),
        ("n5", "tool", result("t2", "create_html_artifact", art, "Error from tool create_html_artifact: no <script>", error=True)),
        ("n6", "assistant", {"role": "assistant", "content": "Writing a file instead.", "toolCalls": [call("t3", "write_file", page)],
                             "_meta": {"spend": {"cost": 0.128, "contextTokens": 30000}}}),
        ("n7", "tool", result("t3", "write_file", page, "Created file: docs/explainer.html", changes={
            f"file://{FOLDER}/docs/explainer.html": {"before": "", "after": page["content"], "patch":
                "--- a\n+++ b\n@@ -0,0 +1,2 @@\n+<!DOCTYPE html>\n+<html><body>hi</body></html>\n"}})),
    ]
    for i, (mid, role, data) in enumerate(msgs):
        db.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (mid, BOB_TOOLS, role, json.dumps(data), T0 + i * 1000))
