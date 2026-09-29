# Configuration

[← Chronicle](../README.md) · [Docs index](README.md)

Settings live in `~/.claude-chronicle/config.toml`; `chronicle config` shows them and `chronicle config edit` opens
the file. Changes apply on the next sync or worker run. `CHRONICLE_HOME` relocates everything.

## `[sources]`

| Key | Default | |
| --- | --- | --- |
| `claude_dirs` | `["~/.claude"]` | Claude Code config directories to scan; several are supported |
| `codex_dirs` | `[]` | `["~/.codex"]` once Codex is connected |
| `codex_cloud` | `false` | `true` once Codex Cloud is connected: list its tasks through the codex CLI every sync |
| `copilot_dirs` | `[]` | `~/.copilot` and VS Code `User` directories once Copilot is connected |
| `bob_dirs` | `[]` | `["~/.bob"]` once Bob is connected |
| `import_history` | `true` | recover prompts of sessions Claude Code already deleted, from `history.jsonl` |
| `import_memory` | `true` | import Claude's auto-memory notes (`projects/*/memory/*.md`) as knowledge |
| `exclude_projects` | `[]` | glob patterns of project paths to ignore entirely, e.g. `["/Users/me/secret/*"]` |

## `[analysis]`

| Key | Default | |
| --- | --- | --- |
| `auto` | `true` | analyze sessions automatically once they go idle |
| `model` / `effort` | `sonnet` / `medium` | any `claude --model` alias |
| `max_budget_usd` | `3.0` | spend cap per `claude -p` call, API-equivalent USD |
| `idle_minutes` | `20` | a session must have ended or been idle this long before it is analyzed |
| `min_prompts` | `1` | sessions with fewer human prompts are skipped |
| `max_per_run` / `concurrency` | `6` / `2` | analyses per 15-minute run, and parallel `claude -p` processes |
| `backfill` | `true` | also analyze sessions recorded before install (newest first) |
| `chunk_chars` | `150000` | characters of condensed transcript per call; longer sessions are map-reduced |
| `timeout_seconds` | `900` | wall-clock limit per call |
| `claude_bin` | `""` | path to `claude` (found automatically when empty) |

## `[synthesis]`, `[export]`, `[server]`, `[inject]`

| Key | Default | |
| --- | --- | --- |
| `synthesis.auto` / `model` / `min_new_items` | `true` / `sonnet` / `3` | rebuild a project's knowledge base once it gains this many new items |
| `export.markdown` | `true` | mirror everything into the Markdown vault |
| `export.notes_dir` | `""` | where the vault lives (empty: `~/.claude-chronicle/notes`) |
| `server.host` / `port` | `127.0.0.1` / `8765` | the dashboard; the app uses a free port when this one is taken |
| `inject.session_start` / `max_chars` | `false` / `3000` | give new sessions a digest of the project's knowledge base (SessionStart hook) |
