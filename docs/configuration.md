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
| `antigravity_dirs` | `[]` | `["~/.gemini/antigravity"]` once Antigravity is connected |
| `import_history` | `true` | recover prompts of sessions Claude Code already deleted, from `history.jsonl` |
| `import_memory` | `true` | import Claude's auto-memory notes (`projects/*/memory/*.md`) as knowledge |
| `exclude_projects` | `[]` | glob patterns of project paths to ignore entirely, e.g. `["/Users/me/secret/*"]` |

## `[analysis]`

| Key | Default | |
| --- | --- | --- |
| `auto` | `true` | analyze sessions automatically once they go idle |
| `backend` | `claude` | which agent analyzes sessions, through your own login: `claude` (Claude Code) or `codex` (Codex). Also in **Status › Analysis** |
| `model` / `effort` | `sonnet` / `medium` | Claude: any `claude --model` alias. `effort` also sets Codex's reasoning effort (`max` becomes `xhigh`) |
| `codex_model` | `""` | Codex model, e.g. `gpt-5.5`; empty uses Codex's default |
| `screen_model` | `haiku` | model that screens imported chats (`chronicle screen`); it reads only each chat's opening, 60 chats a call |
| `language` | `en` | the language Chronicle writes in: summaries, knowledge, knowledge bases, the playbook, glossary definitions, weekly reviews, screening reasons and the lines it proposes for `CLAUDE.md` / `AGENTS.md`. `en` or `ja`; applies to what is analyzed from then on. Also in **Status › Analysis**. The dashboard's own language is chosen in the dashboard, per browser |
| `max_budget_usd` | `3.0` | spend cap per `claude -p` call, API-equivalent USD (Codex reports tokens only) |
| `idle_minutes` | `20` | a session must have ended or been idle this long before it is analyzed |
| `min_prompts` | `1` | sessions with fewer human prompts are skipped |
| `max_per_run` / `concurrency` | `6` / `2` | analyses per 15-minute run, and parallel analysis processes |
| `backfill` | `true` | also analyze sessions recorded before install (newest first) |
| `chunk_chars` | `150000` | characters of condensed transcript per call; longer sessions are map-reduced |
| `timeout_seconds` | `900` | wall-clock limit per call |
| `claude_bin` / `codex_bin` | `""` | path to `claude` / `codex` (found automatically when empty) |

## `[synthesis]`, `[export]`, `[server]`, `[inject]`, `[updates]`

| Key | Default | |
| --- | --- | --- |
| `synthesis.auto` / `model` / `min_new_items` | `true` / `sonnet` / `3` | rebuild a project's knowledge base once it gains this many new items |
| `export.markdown` | `true` | mirror everything into the Markdown vault |
| `export.notes_dir` | `""` | where the vault lives (empty: `~/.claude-chronicle/notes`) |
| `server.host` / `port` | `127.0.0.1` / `8765` | the dashboard; the app uses a free port when this one is taken |
| `server.allowed_hosts` | `[]` | other names the dashboard answers to besides 127.0.0.1 and localhost, e.g. its Tailscale name; `chronicle tailnet on` sets it ([Phone and other computers](devices.md#your-phone)) |
| `server.allowed_users` | `[]` | reached by one of those names through Tailscale Serve, only these Tailscale logins get in (empty: everyone in your tailnet); `chronicle tailnet on` sets it to yours |
| `inject.session_start` / `max_chars` | `false` / `3000` | give new sessions a digest of the project's knowledge base (SessionStart hook) |
| `updates.check_daily` | `false` | ask pypi.org for the latest version once a day while the dashboard is open (Status › Updates) |
| `updates.notify` | `false` | the background sync asks pypi.org once a day and shows a desktop notification once per new release (Status › Updates, or `chronicle install --notify-updates`) |

## `[suggestions]`

Proposed fixes for what keeps going wrong ([Suggestions and What goes wrong](suggestions.md)).

| Key | Default | |
| --- | --- | --- |
| `enabled` | `true` | refresh the suggestions after each background sync (no model is called). Nothing is written until you apply one; **Check again** and `chronicle suggest refresh` work either way |
| `notify` | `false` | show a desktop notification when a background sync finds new suggestions |

## `[hub]`

One archive for several computers ([Phone and other computers](devices.md#your-other-computers)).

| Key | Default | |
| --- | --- | --- |
| `url` | `""` | on a computer that sends its sessions to a hub: the hub's address. Set by `chronicle hub join`, cleared by `chronicle hub leave`; while it is set, this computer sends instead of recording and analyzing |
| `path_map` | `{}` | on the hub: folders on the other computers that hold the same projects as a folder here, e.g. `{ "/home/me/code" = "/Users/me/Projects" }`. Projects with a git remote are matched by it first |
| `folders` | `{}` | on a computer that sends to a hub: folders here whose sessions belong to a project on the hub, the folder and everything below it, e.g. `{ "/Users/me/work/notes" = "/Users/hub/Projects/demo-app" }`. Set by `chronicle hub add-folder` ([Same project, different folders](devices.md#same-project-different-folders)) |
| `share` | `"everything"` | on a computer that sends to a hub: `"everything"` sends its transcripts and the hub records and analyzes them; `"knowledge"` keeps recording and analyzing here and sends only each session's details, summary and project lessons ([Sharing knowledge only](devices.md#sharing-knowledge-only)) |
