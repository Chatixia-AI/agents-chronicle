# Sources: Claude Code, Codex, GitHub Copilot, IBM Bob

[← Chronicle](../README.md) · [Docs index](README.md)

`chronicle sources` (or the dashboard's **Sources** tab) shows each coding agent: detected or not, version,
sessions on disk vs. recorded and analyzed, how it is recorded, and whether its hook and MCP server are in
place. Connect or disconnect from the dashboard or with `chronicle connect <agent>` / `chronicle disconnect <agent>`
(`claude`, `codex`, `copilot`, `bob`; recorded sessions are always kept). Every source maps onto the same session
model, so sessions from all agents share the dashboard, analysis, knowledge bases, glossary and MCP tools.

**Codex** (`~/.codex`) is opt-in. Connecting it:

- records `sources.codex_dirs` in the config, archives `~/.codex/sessions` (rollouts), `session_index.jsonl`
  and Codex's own memory notes, and parses rollouts into the same session model: prompts (the IDE-context
  envelope is unwrapped), replies, tool calls (`exec_command`, `apply_patch`, `write_stdin`, web, MCP, subagents;
  a code-mode `exec` script is named after the tool it calls), file edits (`FileChange` items or patches), real
  exit codes (result chunks, `CommandExecution` items, and long-running cells finished by `wait`), token usage
  per response, compactions and interrupts;
- registers the MCP server in Codex (`codex mcp add chronicle`), so Codex can search every session, Claude's too;
- **recovers Claude Code sessions** that Codex Desktop imported: when Claude Code has already deleted the
  original transcript, Codex's copy becomes a full session (`source = codex-import`); duplicates are skipped.

Codex has no session-end hook (and its single `notify` slot may be taken by another app), so Codex sessions
are picked up by the 15-minute background sync once idle. GPT token costs use OpenAI list prices; newer GPT
models without a published price are estimated at GPT-5 rates.

**GitHub Copilot** is opt-in (`chronicle connect copilot`). It records two stores:

- Copilot agent sessions in `~/.copilot/session-state/<id>/events.jsonl` (Copilot CLI and VS Code's Copilot
  agent host): prompts, replies, reasoning, tool calls with results and durations, and line totals. Token usage
  per call (with cache splits) comes from `~/.copilot/session-store.db`, archived as a SQLite snapshot.
- Copilot Chat in VS Code: `User/workspaceStorage/<hash>/chatSessions/*.jsonl`. Each file is a patch log that is
  replayed into the final chat. The agent loop gives tool calls, results and edits; empty chat panels are skipped.
  These logs do not split cached input from uncached input, so they carry token counts but no cost estimate.

Connecting also registers the MCP server in VS Code (`User/mcp.json`) and the Copilot CLI (`~/.copilot/mcp-config.json`).
Both files are backed up to `~/.claude-chronicle/backups/` first, and other servers in them are kept.

**IBM Bob** is opt-in (`chronicle connect bob`). It reads tasks and messages from `~/.bob/db/bob.db`, read-only,
and archives a SQLite snapshot of that database; nothing else in `~/.bob` (e.g. login state) is read. The Bob IDE
keeps no conversation files locally, so only the tasks in that database are recorded. Connecting registers the MCP
server in `~/.bob/settings/mcp_settings.json`.
