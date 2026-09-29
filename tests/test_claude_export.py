"""Importing a claude.ai data export."""

import copy
import gzip
import json
import threading
import time
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer

import pytest

from chronicle.claude_export import (NOT_ANALYZED, ExportError, import_export, import_status, load_conversations,
                                     parse_conversation)
from chronicle.db import connect as db_connect

PROJECT = "11111111-1111-1111-1111-111111111111"
CHAT = "22222222-2222-2222-2222-222222222222"
EMPTY = "33333333-3333-3333-3333-333333333333"
LOOSE = "44444444-4444-4444-4444-444444444444"

CONVERSATIONS = [
    {
        "uuid": CHAT, "name": "Rate limiter design", "summary": "", "project_uuid": PROJECT,
        "created_at": "2026-05-01T09:00:00.000000Z", "updated_at": "2026-05-01T09:05:00.000000Z",
        "account": {"uuid": "acct"},
        "chat_messages": [
            {"uuid": "m1", "sender": "human", "created_at": "2026-05-01T09:00:00.000000Z", "text": "How should I rate limit my API?",
             "content": [{"type": "text", "text": "How should I rate limit my API?", "start_timestamp": "2026-05-01T09:00:00Z"}],
             "attachments": [{"file_name": "api.py", "file_size": 120, "file_type": "text/x-python", "extracted_content": "def handler(): ..."}],
             "files": [{"file_name": "diagram.png"}]},
            {"uuid": "m2", "sender": "assistant", "created_at": "2026-05-01T09:01:00.000000Z", "text": "",
             "content": [
                 {"type": "thinking", "thinking": "Token bucket fits a bursty API.", "start_timestamp": "2026-05-01T09:01:00Z"},
                 {"type": "text", "text": "Use a token bucket per API key.", "start_timestamp": "2026-05-01T09:01:05Z"},
                 {"type": "tool_use", "name": "artifacts", "input": {"id": "limiter", "type": "application/vnd.ant.code",
                                                                      "title": "limiter.py", "command": "create"}},
                 {"type": "tool_result", "name": "artifacts", "content": [{"type": "text", "text": "OK"}], "is_error": False},
             ]},
            {"uuid": "m3", "sender": "human", "created_at": "2026-05-01T09:04:00.000000Z", "text": "And across instances?",
             "content": [{"type": "text", "text": "And across instances?"}]},
            {"uuid": "m4", "sender": "assistant", "created_at": "2026-05-01T09:05:00.000000Z", "text": "Keep the buckets in Redis.",
             "content": [{"type": "text", "text": "Keep the buckets in Redis."}]},
        ],
    },
    {"uuid": EMPTY, "name": "", "created_at": "2026-05-02T10:00:00Z", "updated_at": "2026-05-02T10:00:00Z", "chat_messages": []},
    {"uuid": LOOSE, "name": "Quick question", "created_at": "2026-05-03T10:00:00Z", "updated_at": "2026-05-03T10:01:00Z",
     "chat_messages": [  # an older export: text only, no content blocks
         {"uuid": "n1", "sender": "human", "created_at": "2026-05-03T10:00:00Z", "text": "What does EXPLAIN ANALYZE do?"},
         {"uuid": "n2", "sender": "assistant", "created_at": "2026-05-03T10:01:00Z", "text": "It runs the query and times each step."}]},
]
PROJECTS = [{"uuid": PROJECT, "name": "Backend", "description": "", "docs": []}]


def write_export(path, conversations=CONVERSATIONS):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("conversations.json", json.dumps(conversations))
        z.writestr("projects.json", json.dumps(PROJECTS))
        z.writestr("users.json", json.dumps([{"uuid": "u", "full_name": "Ada", "email_address": "ada@example.com"}]))
    return path


def test_parse_conversation():
    ps = parse_conversation(CONVERSATIONS[0], {PROJECT: "Backend"})
    assert ps.id == CHAT and ps.custom_title == "Rate limiter design" and ps.project_path == "claude.ai/Backend"
    assert ps.n_prompts == 2 and ps.first_prompt.startswith("How should I rate limit my API?")
    assert "[attached api.py, 18 chars]" in ps.first_prompt and "[file diagram.png]" in ps.first_prompt and ps.n_images == 1
    assert [t.name for t in ps.tool_calls] == ["artifacts"]
    kinds = [e.kind for e in ps.events]
    assert kinds == ["prompt", "thinking", "text", "tool_use", "tool_result", "prompt", "text"]
    assert ps.started_at == "2026-05-01T09:00:00.000Z" and ps.ended_at == "2026-05-01T09:05:00.000Z"
    assert parse_conversation(CONVERSATIONS[1], {}) is None
    loose = parse_conversation(CONVERSATIONS[2], {})
    assert loose.project_path == "claude.ai" and loose.n_prompts == 1 and loose.events[1].text.startswith("It runs")


def test_rejects_other_exports():
    with pytest.raises(ExportError, match="ChatGPT"):
        load_conversations(json.dumps([{"title": "x", "mapping": {}}]).encode())


def test_import_and_reimport(env):
    cfg = env["cfg"]
    conn = db_connect(cfg.db_path)
    counts = import_export(cfg, conn, write_export(env["tmp"] / "data-2026-05-04.zip"))
    assert counts == {"conversations": 3, "new": 2, "updated": 0, "unchanged": 0, "empty": 1, "excluded": 0}
    row = dict(conn.execute("SELECT * FROM sessions WHERE id = ?", (CHAT,)).fetchone())
    assert row["agent"] == "claude-ai" and row["source"] == "claude-ai-export" and row["project_name"] == "Backend"
    assert row["analysis_status"] == "skipped" and row["analysis_reason"] == NOT_ANALYZED
    archived = list((cfg.archive_dir / "claude-ai").glob("*/*"))
    assert sorted(p.name for p in archived) == ["conversations.json.gz", "projects.json.gz"]  # users.json is not kept
    with gzip.open(archived[0].parent / "conversations.json.gz") as f:
        assert len(json.load(f)) == 3
    hits = conn.execute("SELECT COUNT(*) FROM events WHERE session_id = ? AND text LIKE '%token bucket%'", (CHAT,)).fetchone()[0]
    assert hits

    again = import_export(cfg, conn, env["tmp"] / "data-2026-05-04.zip")
    assert again["unchanged"] == 2 and again["empty"] == 1 and again["new"] == again["updated"] == 0
    newer = copy.deepcopy(CONVERSATIONS)
    newer[2]["chat_messages"] += [{"uuid": "n3", "sender": "human", "created_at": "2026-05-05T08:00:00Z", "text": "Thanks!"}]
    newer[2]["updated_at"] = "2026-05-05T08:00:00Z"
    counts = import_export(cfg, conn, write_export(env["tmp"] / "data-2026-05-06.zip", newer), analyze=True)
    assert counts["updated"] == 1 and counts["unchanged"] == 1
    assert conn.execute("SELECT n_prompts FROM sessions WHERE id = ?", (LOOSE,)).fetchone()[0] == 2
    status = import_status(conn)
    assert status["sessions"] == 2 and status["last_import"]["file"] == "data-2026-05-06.zip"


def test_import_from_dashboard_upload(env):
    from chronicle.server import App, make_handler

    app = App(env["cfg"])
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = make_handler(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    body = write_export(env["tmp"] / "export.zip").read_bytes()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/import/claude-export", data=body, method="POST",
                                     headers={"X-Chronicle": "1", "Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=10) as r:
            assert json.loads(r.read())["started"]
        for _ in range(100):
            job = app.jobs.snapshot().get("import", {})
            if job.get("state") != "running":
                break
            time.sleep(0.05)
        assert job["state"] == "done" and "2 new" in job["result"]
        assert not list((env["cfg"].home / "imports").glob("*"))  # the upload is deleted after the import
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/imports", timeout=10) as r:
            assert json.loads(r.read())["claude_ai"]["sessions"] == 2
    finally:
        httpd.shutdown()
