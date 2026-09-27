"""A synthetic Codex home (~/.codex) mirroring the real rollout format."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import SID

CODEX_ID = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0001"
LEGACY_ID = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0002"
SUB_ID = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0003"
IMP_DUP = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0004"
IMP_NEW = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0005"
CODE_ID = "0199aaaa-bbbb-7ccc-8ddd-eeeeffff0006"
RECOVERED = "33333333-3333-3333-3333-333333333333"
CODEX_CWD = "/Users/test/Projects/codex-app"


def _l(ts: str, typ: str, payload: dict) -> str:
    return json.dumps({"timestamp": ts, "type": typ, "payload": payload})


def _msg(ts, role, text, phase=None):
    kind = "output_text" if role == "assistant" else "input_text"
    return _l(ts, "response_item", {"type": "message", "role": role, "phase": phase, "content": [{"type": kind, "text": text}]})


def _meta(tid, ts, *, originator="codex_vscode", source="vscode"):
    return _l(ts, "session_meta", {"id": tid, "timestamp": ts, "cwd": CODEX_CWD, "originator": originator,
                                   "cli_version": "0.147.0", "source": source, "git": {"branch": "feat/flaky"}})


def main_rollout() -> list[str]:
    usage = {"input_tokens": 1000, "cached_input_tokens": 800, "cache_write_input_tokens": 0, "output_tokens": 50,
             "reasoning_output_tokens": 20, "total_tokens": 1050}
    return [
        _meta(CODEX_ID, "2026-09-21T10:00:00.000Z"),
        _l("2026-09-21T10:00:00.100Z", "turn_context", {"cwd": CODEX_CWD, "model": "gpt-5.5", "approval_policy": "on-request"}),
        _msg("2026-09-21T10:00:00.200Z", "developer", "<permissions instructions>sandboxed</permissions instructions>"),
        _msg("2026-09-21T10:00:00.300Z", "user", "<environment_context>\n<cwd>/x</cwd>\n</environment_context>"),
        _msg("2026-09-21T10:00:01.000Z", "user",
             "# Context from my IDE setup:\n\n## Open tabs:\n- app.py\n\n## My request for Codex:\nFix the flaky test in tests/test_app.py"),
        _l("2026-09-21T10:00:02.000Z", "response_item", {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Looking at the test"}]}),
        _msg("2026-09-21T10:00:03.000Z", "assistant", "I'll run the tests first.", phase="commentary"),
        _l("2026-09-21T10:00:04.000Z", "response_item", {"type": "custom_tool_call", "call_id": "c1", "name": "exec", "input": "pytest tests/test_app.py -x"}),
        _l("2026-09-21T10:00:09.000Z", "response_item", {"type": "custom_tool_call_output", "call_id": "c1",
                                                         "output": "Exit code: 1\nWall time: 5s\nOutput:\nFAILED tests/test_app.py::test_x"}),
        _l("2026-09-21T10:00:10.000Z", "response_item", {"type": "custom_tool_call", "call_id": "c2", "name": "apply_patch",
                                                         "input": "*** Begin Patch\n*** Update File: app.py\n@@\n-old = 1\n+new = 2\n+extra = 3\n*** Add File: notes.md\n+hello\n*** End Patch"}),
        _l("2026-09-21T10:00:11.000Z", "response_item", {"type": "custom_tool_call_output", "call_id": "c2",
                                                         "output": [{"type": "input_text", "text": "Success. Updated the following files:\nM app.py\nA notes.md"}]}),
        _l("2026-09-21T10:00:12.000Z", "response_item", {"type": "function_call", "call_id": "c3", "name": "exec_command",
                                                         "arguments": json.dumps({"cmd": "git status", "workdir": CODEX_CWD})}),
        _l("2026-09-21T10:00:13.000Z", "response_item", {"type": "function_call_output", "call_id": "c3", "output": "Process exited with code 0\nOutput:\nclean"}),
        _l("2026-09-21T10:00:14.000Z", "token_usage_record", {"response_id": "resp_1", "turn_id": "t1", "usage": usage}),
        _l("2026-09-21T10:00:14.100Z", "event_msg", {"type": "token_count", "info": {"total_token_usage": usage, "last_token_usage": usage}}),
        _l("2026-09-21T10:00:15.000Z", "event_msg", {"type": "turn_aborted", "turn_id": "t1", "reason": "interrupted"}),
        _l("2026-09-21T10:01:00.000Z", "compacted", {"message": "summary", "window_number": 2}),
        _msg("2026-09-21T10:02:00.000Z", "user", "now make it deterministic"),
        _l("2026-09-21T10:02:05.000Z", "response_item", {"type": "function_call", "call_id": "c4", "namespace": "collaboration",
                                                         "name": "spawn_agent", "arguments": json.dumps({"message": "check the docs"})}),
        _l("2026-09-21T10:02:06.000Z", "response_item", {"type": "function_call_output", "call_id": "c4", "output": '{"agent_id": "a1"}'}),
        _msg("2026-09-21T10:03:00.000Z", "assistant", "Fixed the flaky test with a fixed seed.", phase="final_answer"),
    ]


def sub_rollout() -> list[str]:
    return [
        _meta(SUB_ID, "2026-09-21T10:02:05.500Z", source={"subagent": {"thread_spawn": {"parent_thread_id": CODEX_ID, "depth": 1}}}),
        _l("2026-09-21T10:02:05.600Z", "turn_context", {"cwd": CODEX_CWD, "model": "gpt-5.5"}),
        _msg("2026-09-21T10:02:06.000Z", "user", "check the docs"),
        _l("2026-09-21T10:02:10.000Z", "response_item", {"type": "function_call", "call_id": "s1", "name": "exec_command",
                                                         "arguments": json.dumps({"cmd": "npm test"})}),
        _l("2026-09-21T10:02:12.000Z", "response_item", {"type": "function_call_output", "call_id": "s1", "output": "done"}),
        _l("2026-09-21T10:02:12.100Z", "event_msg", {"type": "item_completed", "item": {
            "type": "CommandExecution", "command": "/bin/zsh -lc 'npm test'", "status": "failed", "exit_code": 1}}),
        _l("2026-09-21T10:02:20.000Z", "event_msg", {"type": "item_completed", "item": {"type": "FileChange", "status": "completed", "changes": {
            "docs/guide.md": {"type": "add", "content": "x\ny\n"},
            "/abs/app.py": {"type": "update", "unified_diff": "--- a/app.py\n+++ b/app.py\n@@\n-old\n+new\n"}}}}),
        _msg("2026-09-21T10:02:30.000Z", "assistant", "The docs say to seed the RNG."),
        _l("2026-09-21T10:02:31.000Z", "token_usage_record", {"response_id": "sub_1", "usage": {"input_tokens": 200, "cached_input_tokens": 0, "output_tokens": 30}}),
    ]


def legacy_rollout() -> list[str]:
    def tc(total, last):
        return _l("2026-09-20T09:00:05.000Z", "event_msg", {"type": "token_count", "info": {
            "total_token_usage": {"input_tokens": total, "total_tokens": total},
            "last_token_usage": {"input_tokens": last, "cached_input_tokens": 0, "output_tokens": 10, "total_tokens": last}}})
    return [
        _meta(LEGACY_ID, "2026-09-20T09:00:00.000Z"),
        _l("2026-09-20T09:00:00.100Z", "turn_context", {"cwd": CODEX_CWD, "model": "gpt-5.4"}),
        _msg("2026-09-20T09:00:01.000Z", "user", "explain the build"),
        tc(100, 100), tc(100, 100), tc(250, 150),  # the repeated total must be counted once
        _msg("2026-09-20T09:00:09.000Z", "assistant", "It uses make."),
    ]


def code_mode_rollout() -> list[str]:
    """Code mode: exec runs a JS script that calls the real tools; a long script finishes through wait."""
    def run(ts, cid, script):
        return _l(ts, "response_item", {"type": "custom_tool_call", "call_id": cid, "name": "exec", "input": script})

    def out(ts, cid, *texts):
        return _l(ts, "response_item", {"type": "custom_tool_call_output", "call_id": cid,
                                        "output": [{"type": "input_text", "text": t} for t in texts]})

    def chunk(code, text):
        return json.dumps({"chunk_id": "ab12", "wall_time_seconds": 0.1, "exit_code": code, "output": text})

    def call(ts, cid, name, args):
        return _l(ts, "response_item", {"type": "function_call", "call_id": cid, "name": name, "arguments": json.dumps(args)})

    def result(ts, cid, text):
        return _l(ts, "response_item", {"type": "function_call_output", "call_id": cid, "output": text})

    done = "Script completed\nWall time 0.1 seconds\nOutput:\n"
    return [
        _meta(CODE_ID, "2026-09-22T09:00:00.000Z"),
        _l("2026-09-22T09:00:00.100Z", "turn_context", {"cwd": CODEX_CWD, "model": "gpt-5.5"}),
        _msg("2026-09-22T09:00:01.000Z", "user", "find the lint problem and fix it"),
        # the command mentions tools.nope( inside a string: not a call
        run("2026-09-22T09:00:02.000Z", "e1", r'const r = await tools.exec_command({cmd:"rg -n \"await tools.nope(\" src",workdir:"/x"}); text(r);'),
        out("2026-09-22T09:00:03.000Z", "e1", done, chunk(2, "rg: regex parse error")),
        run("2026-09-22T09:00:04.000Z", "e2", r'text(await tools.apply_patch("*** Begin Patch\n*** Update File: lib.py\n@@\n-a = 1\n+a = \"é\"\n*** End Patch"))'),
        out("2026-09-22T09:00:05.000Z", "e2", done, "Success. Updated the following files:\nM lib.py"),
        run("2026-09-22T09:00:06.000Z", "e3", "// tools.fake_tool( is only a comment\n"
            'const [a, b] = await Promise.all([tools.exec_command({"cmd":"git status"}), tools.view_image({path:"/tmp/shot.png"})]); text(a);'),
        out("2026-09-22T09:00:07.000Z", "e3", done, chunk(0, "clean")),
        run("2026-09-22T09:00:08.000Z", "e4", 'await tools.mcp__playwright__browser_navigate({url: "http://localhost:3000"})'),
        out("2026-09-22T09:00:09.000Z", "e4", done),
        run("2026-09-22T09:01:00.000Z", "e5", 'const r = await tools.exec_command({cmd:"npm run build"}); text(r.output);'),
        out("2026-09-22T09:01:10.000Z", "e5", "Script running with cell ID 7\nWall time 10.0 seconds\nOutput:\n"),
        call("2026-09-22T09:01:11.000Z", "w1", "wait", {"cell_id": "7", "yield_time_ms": 30000}),
        result("2026-09-22T09:01:41.000Z", "w1", "Script running with cell ID 7\nWall time 30.0 seconds\nOutput:\n"),
        call("2026-09-22T09:01:42.000Z", "w2", "wait", {"cell_id": "7", "yield_time_ms": 30000}),
        result("2026-09-22T09:02:00.000Z", "w2", "Script failed\nWall time 3.0 seconds\nOutput:\n\nScript error:\nbuild exploded"),
        run("2026-09-22T09:03:00.000Z", "e6", 'const r = await tools.exec_command({cmd:"sleep 100"}); text(r.output);'),
        out("2026-09-22T09:03:05.000Z", "e6", "aborted by user after 5.0s"),
        _msg("2026-09-22T09:03:10.000Z", "assistant", "Fixed the lint error.", phase="final_answer"),
    ]


def imported_rollout(tid: str) -> list[str]:
    return [
        _meta(tid, "2026-08-01T08:00:00.000Z", originator="Codex Desktop"),
        _msg("2026-08-01T08:00:01.000Z", "user", "<command-name>/init</command-name>\n<command-message>init</command-message>"),
        _msg("2026-08-01T08:00:02.000Z", "user", "set up the repo"),
        _msg("2026-08-01T08:00:30.000Z", "assistant", "Done."),
    ]


def write_codex_home(root: Path) -> Path:
    day = root / "sessions" / "2026" / "09" / "21"
    day.mkdir(parents=True)
    files = {
        f"rollout-2026-09-21T10-00-00-{CODEX_ID}.jsonl": main_rollout(),
        f"rollout-2026-09-21T10-02-05-{SUB_ID}.jsonl": sub_rollout(),
        f"rollout-2026-09-20T09-00-00-{LEGACY_ID}.jsonl": legacy_rollout(),
        f"rollout-2026-08-01T08-00-00-{IMP_DUP}.jsonl": imported_rollout(IMP_DUP),
        f"rollout-2026-08-01T08-00-00-{IMP_NEW}.jsonl": imported_rollout(IMP_NEW),
    }
    for name, lines in files.items():
        (day / name).write_text("\n".join(lines) + "\n")
    (root / "session_index.jsonl").write_text(json.dumps({"id": CODEX_ID, "thread_name": "Fix flaky test", "updated_at": "2026-09-21T10:03:00Z"}) + "\n")
    (root / "external_agent_session_imports.json").write_text(json.dumps({"records": [
        {"imported_thread_id": IMP_DUP, "source_path": f"/Users/test/.claude/projects/x/{SID}.jsonl", "title": "duplicate"},
        {"imported_thread_id": IMP_NEW, "source_path": f"/Users/test/.claude/projects/x/{RECOVERED}.jsonl", "title": "Set up the repo"},
    ], "detected_connector_records": []}))
    mem = root / "memories"
    mem.mkdir()
    (mem / "MEMORY.md").write_text(f"# Task Group: codex-app seeding\n\nscope: tests\napplies_to: cwd={CODEX_CWD}; reuse_rule=safe\n\n## Task 1: seed the RNG\n")
    (mem / ".git").mkdir()
    (mem / ".git" / "config").write_text("[core]\n")
    (root / "config.toml").write_text('notify = ["/Applications/Other.app/notifier", "turn-ended"]\n')
    return root
