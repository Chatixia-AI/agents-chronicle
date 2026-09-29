# Sources: Claude Code, Codex, GitHub Copilot, IBM Bob

[← Chronicle](../README.md) · [Docs index](README.md)

`chronicle sources` (or the dashboard's **Sources** tab) shows each coding agent: detected or not, version,
sessions on disk vs. recorded and analyzed, how it is recorded, and whether its hook and MCP server are in
place. Connect or disconnect from the dashboard or with `chronicle connect <agent>` / `chronicle disconnect <agent>`
(`claude`, `codex`, `codex-cloud`, `copilot`, `bob`; recorded sessions are always kept). Every source maps onto the same session
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

**Codex Cloud** (tasks at chatgpt.com/codex) is a separate opt-in (`chronicle connect codex-cloud`), because it
goes online: every sync runs `codex cloud list` with your Codex login (`codex login`), then `codex cloud diff` for
each new or changed task. Each task becomes a Codex session (`source = codex-cloud`) with its title, repository,
status, changed files with line counts, the diff and a link to the task; it joins your local project when the
repository name matches one. The Codex CLI does not give a cloud task's conversation, so these sessions have no
prompts and are not analyzed. The task and its diff are archived in `~/.claude-chronicle/archive/codex-cloud/` and
stay after the task expires in the cloud. If listing fails (not logged in, offline), the Sources card says why and
the next sync tries again.

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

**Chats on claude.ai and ChatGPT** are not stored on your Mac, so they come in from a data export: on claude.ai,
**Settings › Privacy › Export data**; on ChatGPT, **Settings › Data controls › Export data**. The email's link
downloads a `.zip`. Import it with **Import export…** on the Sources page (card *Chat exports*), or
`chronicle import <zip>` (the unpacked folder or `conversations.json` work too); which service it came from is
recognized from its contents. Each chat becomes a session (agent `claude-ai` or `chatgpt`, `source =
claude-ai-export` or `chatgpt-export`) with its prompts, replies, thinking, tool calls (claude.ai artifacts,
ChatGPT's Python, browsing and image steps, with their output) and notes of attached files and images. claude.ai
chats in a project are grouped under `claude.ai/<project>`, the rest under `claude.ai`; ChatGPT chats under
`chatgpt.com`. A ChatGPT chat is read along the branch ChatGPT shows, so edited prompts and regenerated answers you
moved away from are left out. Import a newer export any time: new and changed chats are added, unchanged ones
skipped. Only the chats are read and archived (`conversations.json`, and claude.ai's `projects.json` for project
names); the account files (`users.json`, `user.json`) and ChatGPT's `chat.html` are never opened, and a zip uploaded
from the dashboard is deleted once imported. Imported chats are **not analyzed automatically**, since years of chats
would use up your Claude plan's limits at once: open a chat and choose **Analyze now**, or import with `--analyze`
to queue them all. The exports have no token counts, so chats show no cost. Claude Code on the web sessions are not
in the claude.ai export; `claude --teleport <id>` brings one onto your Mac as an ordinary Claude Code transcript.
Codex Cloud tasks are a separate source (above).

Claude Desktop, Cursor, Windsurf and Gemini CLI aren't recorded, but they can use the MCP server too. See
[MCP server](mcp.md).
