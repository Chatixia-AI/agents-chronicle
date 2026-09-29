# Data and privacy

[← Chronicle](../README.md) · [Docs index](README.md)

**What leaves your machine:** one thing. When a session is analyzed, a condensed digest of it (secrets redacted
first) goes to Claude through your own Claude Code login, with `claude -p`: the same service that produced the
transcript. Nothing is sent to Chronicle's authors or any other service, and there is no telemetry.

| Stored locally | Where |
| --- | --- |
| Database: sessions, events, knowledge, glossary, reviews | `~/.claude-chronicle/chronicle.db` (SQLite) |
| Raw transcripts, kept forever (gzip) | `~/.claude-chronicle/archive/` |
| Markdown vault | `~/.claude-chronicle/notes/` |
| Logs | `~/.claude-chronicle/logs/` |
| Backups of agent config files Chronicle edits | `~/.claude-chronicle/backups/` |
| The app's launcher script and window storage | `~/.claude-chronicle/bin/chronicle`, `~/.claude-chronicle/webview/` |

## Details

- **Redaction.** API keys, tokens and similar secrets are replaced in the digest before any call. The raw archive
  keeps the original transcripts unchanged, on your disk only.
- **Analysis runs sandboxed.** `claude -p` runs with `--no-session-persistence --safe-mode --tools ""
  --strict-mcp-config`: no transcript is written for the analysis itself, no hooks, plugins or MCP servers load,
  and the model can only answer. `analysis.auto = false` turns automatic analysis off.
- **The dashboard** binds to 127.0.0.1, rejects foreign `Host` headers (DNS rebinding) and requires a custom header
  on state-changing requests (CSRF). In the app window, the page can call only three window actions (theme, drag,
  zoom).
- **Other agents' stores are only read.** SQLite databases are opened read-only and archived as snapshots; Bob's
  login state is never read. Connecting an agent edits its MCP config, backed up to `~/.claude-chronicle/backups/`
  first.
- **Deleting.** `chronicle forget <id> [--delete-transcript]` removes a session for good; `chronicle uninstall
  --purge` deletes everything.
