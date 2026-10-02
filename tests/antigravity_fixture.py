"""A synthetic Google Antigravity home (~/.gemini/antigravity) mirroring the real formats.

NEW_ID is a conversation from a current version (untruncated step log written out of step order and in mid-line
chunks, a title, a conversation database with protobuf metadata); OLD_ID one from an older version (a truncated step
log whose tool arguments are JSON-encoded, an encrypted .pb); EMPTY_ID a log without a prompt; UNREAD_ID a
conversation kept only in the encrypted store.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

NEW_ID = "71a9ef40-0000-4000-8000-000000000001"
OLD_ID = "8bf52945-0000-4000-8000-000000000002"
EMPTY_ID = "e0e0e0e0-0000-4000-8000-000000000003"
UNREAD_ID = "dddddddd-0000-4000-8000-000000000004"
FOLDER = "/Users/test/Projects/agy-app"
GAME = "/Users/test/Projects/game"
TRAILER = "No need to comment on this change if the user doesn't ask about it."


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte, n = n & 0x7F, n >> 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def pb(*fields) -> bytes:
    """A protobuf message from (field number, int | str | bytes) pairs."""
    out = b""
    for num, v in fields:
        if isinstance(v, int):
            out += _varint(num << 3) + _varint(v)
        else:
            v = v.encode() if isinstance(v, str) else v
            out += _varint(num << 3 | 2) + _varint(len(v)) + v
    return out


def _user(i, ts, request, *, preamble="", model=None):
    text = f"{preamble}<USER_REQUEST>\n{request}\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\nThe current local time is: {ts}.\n</ADDITIONAL_METADATA>"
    if model:
        text += f"\n<USER_SETTINGS_CHANGE>\nThe user changed setting `Model Selection` from None to {model}. {TRAILER}\n</USER_SETTINGS_CHANGE>"
    return {"step_index": i, "source": "USER_EXPLICIT", "type": "USER_INPUT", "status": "DONE", "created_at": ts, "content": text}


def _plan(i, ts, *, text=None, thinking=None, calls=(), tokens=None):
    row = {"step_index": i, "source": "MODEL", "type": "PLANNER_RESPONSE", "status": "DONE", "created_at": ts}
    if tokens:
        row.update(zip(("input_tokens", "cache_read_tokens", "output_tokens"), tokens, strict=True))
    if text:
        row["content"] = text
    if thinking:
        row["thinking"] = thinking
    if calls:
        row["tool_calls"] = [{"name": n, "args": a} for n, a in calls]
    return row


def _result(i, ts, kind, start, end, text, status="DONE"):
    return {"step_index": i, "source": "MODEL", "type": kind, "status": status, "created_at": ts,
            "content": f"Created At: {start}\nCompleted At: {end}\n\n{text}"}


def _write_log(path: Path, rows: list[dict], tail: str = "") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows) + tail
    path.write_text(text)
    return text


def write_antigravity_home(home: Path) -> Path:
    brain = home / "brain"
    # ---- a current-version conversation
    conv = brain / NEW_ID
    new = [
        _user(0, "2026-10-02T09:00:00Z", "fix the failing test", model="Gemini 3.8 Flash (High)"),
        _plan(1, "2026-10-02T09:00:01Z", thinking="Run the tests first", tokens=(1000, 0, 50),
              calls=[("run_command", {"CommandLine": "pytest -q", "Cwd": FOLDER, "WaitMsBeforeAsync": 5000,
                                      "toolAction": "Running tests", "toolSummary": "Test run"})]),
        _result(2, "2026-10-02T09:00:03Z", "GENERIC", "2026-10-02T18:00:01+09:00", "2026-10-02T18:00:03+09:00",
                "The command exited with code 1.\nOutput:\n1 failed"),
        _result(4, "2026-10-02T09:00:05Z", "GENERIC", "2026-10-02T18:00:04+09:00", "2026-10-02T18:00:05+09:00",
                "File Path: `file:///Users/test/Projects/agy-app/app.py`"),  # finished before its call was logged
        _plan(3, "2026-10-02T09:00:04Z", tokens=(200, 1000, 40),
              calls=[("view_file", {"AbsolutePath": f"{FOLDER}/app.py", "toolSummary": "App code"}),
                     ("replace_file_content", {"TargetFile": f"{FOLDER}/app.py", "ReplacementContent": "x = 1",
                                               "toolSummary": "Fix off-by-one"})]),
        _result(5, "2026-10-02T09:00:06Z", "GENERIC", "2026-10-02T18:00:05+09:00", "2026-10-02T18:00:06+09:00",
                "The following changes were made to app.py"),
        {"step_index": 6, "source": "SYSTEM", "type": "SYSTEM_MESSAGE", "status": "DONE", "created_at": "2026-10-02T09:00:07Z",
         "content": "The following is a <SYSTEM_MESSAGE> not actually sent by the user.\n\n<SYSTEM_MESSAGE>\n[Message] "
                    "timestamp=2026-10-02T09:00:07Z sender=x/task-9 priority=MESSAGE_PRIORITY_HIGH content=Task id "
                    "\"x/task-9\" finished with result:\nok\n</SYSTEM_MESSAGE>"},
        _plan(7, "2026-10-02T09:00:08Z", text="Fixed the off-by-one; the tests pass.", tokens=(100, 1200, 30)),
    ]
    full = _write_log(conv / ".system_generated" / "logs" / "transcript_full.jsonl", new, tail='{"step_index":8,"sou')
    _write_log(conv / ".system_generated" / "logs" / "transcript.jsonl", new)
    chunks = conv / ".system_generated" / "logs" / "chunks" / "transcript_full"
    chunks.mkdir(parents=True)
    cut = len(full.encode()) // 2 + 3  # mid-line, like Antigravity's ~100 KB pieces
    (chunks / "00000000.jsonl").write_bytes(full.encode()[:cut])
    (chunks / "00000001.jsonl").write_bytes(full.encode()[cut:])
    (conv / "task.md").write_text("# Fix the failing test\n- [x] run tests\n")
    (conv / "task.md.metadata.json").write_text(json.dumps({"artifactType": "ARTIFACT_TYPE_TASK", "summary": "Checklist"}))
    (conv / "icon_1790965371732.jpg").write_bytes(b"\xff\xd8\xff" + b"\0" * 64)
    (home / "annotations").mkdir(parents=True)
    (home / "annotations" / f"{NEW_ID}.pbtxt").write_text(
        'title:"Fix the failing test \\343\\201\\202"  last_user_view_time:{seconds:1790965090  nanos:784000000}')
    (home / "conversations").mkdir(parents=True)
    db = sqlite3.connect(home / "conversations" / f"{NEW_ID}.db")
    db.execute("CREATE TABLE trajectory_metadata_blob (id text DEFAULT 'main', data blob, PRIMARY KEY (id))")
    db.execute("CREATE TABLE gen_metadata (idx integer, data blob, size integer NOT NULL DEFAULT 0, PRIMARY KEY (idx))")
    workspace = pb((1, f"file://{FOLDER}"), (2, f"file://{FOLDER}"),
                   (3, pb((1, "org/agy-app"), (2, "git@github.com:org/agy-app.git"))), (4, "feature/fix-test"))
    db.execute("INSERT INTO trajectory_metadata_blob VALUES ('main', ?)",
               (pb((1, workspace), (2, pb((1, 1790964964))), (6, NEW_ID), (18, "p-1")),))
    for i in range(3):
        gen = pb((1, pb((19, "gemini-3.8-flash"), (20, pb((1, "used_claude"), (2, "false"))))), (4, f"gen-{i}"))
        db.execute("INSERT INTO gen_metadata (idx, data) VALUES (?, ?)", (i, gen))
    db.commit()
    db.close()

    # ---- an older-version conversation: truncated log, every tool argument JSON-encoded
    conv = brain / OLD_ID
    artifact = f"{conv}/task.md"
    old = [
        _user(0, "2026-05-23T06:18:48Z", "build a game", model="Gemini 3.5 Flash (Medium)"),
        {"step_index": 1, "source": "SYSTEM", "type": "CONVERSATION_HISTORY", "status": "DONE", "created_at": "2026-05-23T06:18:48Z"},
        _plan(2, "2026-05-23T06:18:49Z", text="I will list the folder.",
              calls=[("list_dir", {"DirectoryPath": json.dumps(GAME), "toolSummary": '"Folder list"'})]),
        _result(3, "2026-05-23T06:18:51Z", "LIST_DIRECTORY", "2026-05-23T06:18:51Z", "2026-05-23T06:18:51Z", '{"name":".git"}'),
        _plan(4, "2026-05-23T06:18:52Z", calls=[("write_to_file", {
            "TargetFile": json.dumps(f"{GAME}/main.ts"), "CodeContent": '"console.log(', "Overwrite": "true"})]),
        _result(5, "2026-05-23T06:18:53Z", "CODE_ACTION", "2026-05-23T06:18:53Z", "2026-05-23T06:18:53Z", "Created file main.ts"),
        _plan(6, "2026-05-23T06:18:54Z", calls=[("write_to_file", {"TargetFile": json.dumps(artifact), "IsArtifact": "true"})]),
        {"step_index": 7, "source": "SYSTEM", "type": "ERROR_MESSAGE", "status": "DONE", "created_at": "2026-05-23T06:18:55Z",
         "error": "There was a problem parsing the tool call."},
        _user(8, "2026-05-23T06:25:13Z", "", preamble=f"Comments on artifact URI: file://{conv}/implementation_plan.md\n\n"
                                                      "The user has approved this document.\n\n\n"),
        _plan(9, "2026-05-23T06:25:14Z", calls=[("run_command", {"CommandLine": '"pnpm -v"', "Cwd": json.dumps(GAME)})]),
        _result(10, "2026-05-23T06:30:35Z", "RUN_COMMAND", "2026-05-23T06:25:15Z", "2026-05-23T06:30:35Z",
                "Encountered error in step execution: user denied permission", status="ERROR"),
        _plan(11, "2026-05-23T06:30:40Z", text="Done."),
    ]
    _write_log(conv / ".system_generated" / "logs" / "transcript.jsonl", old)
    (home / "conversations" / f"{OLD_ID}.pb").write_bytes(bytes(range(256)))

    # ---- a log that never got a prompt, and a conversation only in the encrypted store
    _write_log(brain / EMPTY_ID / ".system_generated" / "logs" / "transcript.jsonl",
               [{"step_index": 0, "source": "SYSTEM", "type": "CONVERSATION_HISTORY", "status": "DONE", "created_at": "2026-05-01T00:00:00Z"}])
    (home / "conversations" / f"{UNREAD_ID}.pb").write_bytes(bytes(range(64)))
    return home
