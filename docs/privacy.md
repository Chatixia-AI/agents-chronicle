# Data and privacy

[← Chronicle](../README.md) · [Docs index](README.md)

**What leaves your machine:** one thing. When a session is analyzed, a condensed digest of it (secrets redacted
first) goes to the agent you chose for analysis, through your own login: Anthropic with Claude Code (`claude -p`,
the default) or OpenAI with Codex (`codex exec`). Nothing is sent to Chronicle's authors or any other service, and there is no telemetry. The one other
connection is the update check: it asks pypi.org for the latest version number and sends nothing about you. It
runs when you click **Check for updates** on the Status page, and once a day only if you turn on **Check for
updates daily** there (off by default). If you connect Codex Cloud, each sync also runs the
`codex cloud` CLI, which fetches your own tasks from OpenAI with your Codex login; nothing is sent the other way.
Importing a claude.ai or ChatGPT export reads only the chats, never the account files (`users.json`, `user.json`).

| Stored locally | Where |
| --- | --- |
| Database: sessions, events, knowledge, glossary, reviews | `~/.claude-chronicle/chronicle.db` (SQLite) |
| Raw transcripts, kept forever (gzip) | `~/.claude-chronicle/archive/` |
| Markdown vault | `~/.claude-chronicle/notes/` |
| Logs | `~/.claude-chronicle/logs/` |
| Backups of agent config files Chronicle edits | `~/.claude-chronicle/backups/` |
| Status-line usage per session (only with `--statusline`) | `~/.claude-chronicle/statusline/` |
| The app's launcher script and window storage | `~/.claude-chronicle/bin/chronicle`, `~/.claude-chronicle/webview/` |

## Details

- **Redaction.** API keys, tokens and similar secrets are replaced in the digest before any call. The raw archive
  keeps the original transcripts unchanged, on your disk only.
- **Analysis runs sandboxed.** No session is written for the analysis itself, none of your hooks, plugins, MCP
  servers or instruction files load, and the model can only answer. `claude -p` runs with
  `--no-session-persistence --safe-mode --tools "" --strict-mcp-config`; `codex exec` runs `--ephemeral` and
  `--ignore-user-config` in a read-only sandbox with every tool feature off, and Chronicle discards any reply that
  follows a tool call ([details](analysis.md#how-analysis-works)). `analysis.auto = false` turns automatic analysis
  off.
- **The dashboard** binds to 127.0.0.1, rejects foreign `Host` headers (DNS rebinding) and requires a custom header
  on state-changing requests (CSRF). In the app window, the page can call only three window actions (theme, drag,
  zoom).
- **Exports** (Export on a session, or on a selection in the Sessions list) are redacted like everything the
  dashboard shows, in Markdown and JSON. **Original transcript** is the agent's own file as archived, unredacted:
  check it before sharing.
- **MCP tools** read the database and answer on stdio; nothing listens on the network. Their results join the
  client's conversation and so reach that client's model, with secrets redacted as in the digests. Give the server
  only to clients whose model provider you trust with your sessions. See [MCP server](mcp.md#privacy).
- **Other agents' stores are only read.** SQLite databases are opened read-only and archived as snapshots; Bob's
  login state is never read. Connecting an agent edits its MCP config, backed up to `~/.claude-chronicle/backups/`
  first.
- **Deleting.** `chronicle forget <id> [--delete-transcript]` removes a session for good; `chronicle uninstall
  --purge` deletes everything.
