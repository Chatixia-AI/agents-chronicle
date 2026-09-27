# Claude Chronicle

Records every Claude Code (and, when connected, OpenAI Codex) session into a local vault, keeps the raw
transcripts forever, and uses Claude Code itself (headless `claude -p`) to turn each session into an overview
plus reusable knowledge. Browse everything in a local dashboard, an Obsidian-compatible Markdown vault, the CLI,
or from inside Claude Code through an MCP server.

```text
 Claude Code session ends ──SessionEnd hook──┐          every 15 min (launchd) ──┐
                                             ▼                                   ▼
 ~/.claude/projects/*.jsonl ──► archive (gzip, never deleted) ──► parse ──► SQLite + FTS5
   (+ subagents, workflows,                                                   │
    memory notes, history)                                                    ▼
                                                              analysis queue (idle/ended sessions)
                                                                              │  claude -p (Sonnet)
                                                                              ▼
                                        session overview + knowledge items (fix, gotcha, decision …)
                                                                              │  claude -p
                                                                              ▼
                                               per-project knowledge bases + global playbook
                                                                              │
                          dashboard :8765 ◄───────┬───────► Markdown vault ◄──┴──► MCP server (Claude Code)
                                                  └───────► CLI
```

## Why

- **Claude Code deletes transcripts after 30 days** (`cleanupPeriodDays`). Chronicle mirrors every
  file under `~/.claude/projects` into `~/.claude-chronicle/archive` (JSONL gzip-compressed) and never
  deletes it. Sessions whose transcripts were already gone are partially recovered from
  `~/.claude/history.jsonl` (prompts only, marked *history*).
- **Knowledge evaporates.** Fixes, gotchas, decisions and project facts discovered in a session are
  extracted, deduplicated per project, and made searchable, including by Claude itself in later sessions.

## Install

```bash
uv tool install --python 3.13 /path/to/chronicle   # puts `chronicle` on PATH (~/.local/bin)
chronicle sync                                     # archive + ingest everything now
chronicle install                                  # hooks, background agents, MCP server
```

`chronicle install` does four things (each can be skipped with `--no-hooks`, `--no-launchd`, `--no-ui`,
`--no-mcp`; preview with `--dry-run`):

| Piece | What it does |
| --- | --- |
| `SessionEnd` hook in `~/.claude/settings.json` | Hands the ended transcript to a detached process that archives, ingests and analyzes it. Returns in milliseconds; a backup of `settings.json` is kept in `~/.claude-chronicle/backups/`. |
| launchd `com.claude-chronicle.sync` | `chronicle sync --work` every 15 minutes: catches anything the hook missed, processes the analysis queue, synthesizes knowledge bases, exports notes. |
| launchd `com.claude-chronicle.ui` | Keeps the dashboard at <http://127.0.0.1:8765/>. |
| MCP server `chronicle` (user scope) | Lets Claude Code search your past sessions and knowledge. |

Optional: `chronicle install --inject-context` also adds a `SessionStart` hook that gives each new
session a short digest of the project's knowledge base (off by default; preview it with `chronicle context`).

Remove everything with `chronicle uninstall` (data is kept; `--purge` deletes it too).

## Sources: Claude Code and Codex

`chronicle sources` (or the dashboard's **Sources** tab) shows each coding agent: detected or not, version,
sessions on disk vs. recorded and analyzed, how it is recorded, and whether its hook and MCP server are in
place. Connect or disconnect from the dashboard or with `chronicle connect codex` / `chronicle disconnect codex`
(recorded sessions are always kept).

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

## Using it

| Command | |
| --- | --- |
| `chronicle ui [--open]` | Dashboard (also always running at :8765 after install). Sessions, Knowledge, Projects and Glossary switch between Cards and List (a sortable table; click a row for details), remembered per page |
| `chronicle sessions [-p project] [--since 7d]` | List sessions |
| `chronicle show <id-prefix> [--transcript\|--markdown\|--json]` | Session overview or full conversation |
| `chronicle search <words>` | Full-text search over transcripts + knowledge (any language, 3+ chars) |
| `chronicle knowledge [query] [-k gotcha] [-p project]` | Browse extracted knowledge |
| `chronicle projects` / `chronicle stats [--since 30d]` | Per-project and overall statistics |
| `chronicle analyze <id> \| --pending [--limit N] [--dry-run]` | Analyze now (`--dry-run` shows digest sizes, no tokens spent) |
| `chronicle synthesize [--project P] [--global] [--all]` | Rebuild knowledge bases |
| `chronicle export [--full]` | Rewrite the Markdown vault |
| `chronicle glossary [term] [-p project] [--rebuild --all]` | Your vocabulary: internal names, acronyms, domain terms with definitions and usage |
| `chronicle review [2026-W39\|current]` | Weekly engineering review written by Claude (automatic for each completed week) |
| `chronicle forget <id> [--delete-transcript]` | Remove a session from the vault for good (it is never re-ingested) |
| `chronicle sources` | Which agents are connected, and how |
| `chronicle connect codex` / `disconnect codex` | Start/stop recording an agent (data is kept) |
| `chronicle status` | Health: hooks, agents, MCP, queue, failures |
| `chronicle config [edit]` | Show or edit `~/.claude-chronicle/config.toml` |

**Dashboard:** overview (KPIs with deltas, daily activity, 26-week calendar, hour-of-week grid, projects,
tools, models, outcomes), sortable/filterable session list, session pages (summary, knowledge,
context-window chart with compactions, tools, files, subagents, PRs, full transcript replay with
collapsible tool calls and subagent threads), knowledge browser (pin/dismiss), project knowledge
bases, global playbook, glossary, weekly reviews, search with jump-to-message. Glossary terms are underlined
wherever they appear (transcripts, knowledge, summaries): hover for the definition, click for the entry.
Every chart has a table view; light and dark themes.

**Markdown vault:** `~/.claude-chronicle/notes` (open it as an Obsidian vault): `Home.md`,
`Sessions/YYYY/MM/*.md` with YAML frontmatter, `Projects/*.md` (knowledge base + session list),
`Knowledge/<Kind>.md`, `Reviews/YYYY-Www.md`, `Glossary.md`, `Global Playbook.md`.

**Inside Claude Code** (MCP tools): `search_knowledge`, `search_sessions`, `get_session`,
`get_transcript`, `project_knowledge`, `glossary`, `recent_sessions`. Ask e.g. *"have we hit this error before?"*
or *"what is the deployer_ip rule?"*.

**Glossary:** built by Claude from each project's distilled knowledge (not the raw transcripts), one call per
project plus a cross-project pass, refreshed whenever a project's knowledge base is re-synthesized. Each term has
a category, aliases (abbreviations, translations of Japanese business terms), a definition, a per-project usage
note, related terms, and full-text statistics: how many sessions mention it, first and last seen, top sessions.

## What gets recorded

Per session: project, branch, Claude Code version, start/end, wall and active time (idle gaps over
15 min excluded), human prompts (including ones queued while Claude worked), slash commands,
interrupts, compactions, every tool call with duration and success, files read/edited with
line counts, subagents and workflows with their own usage, skills, MCP servers, hooks, PRs and
artifacts, and token usage per API call (deduplicated per message) with an API-list-price cost
estimate. Estimates match Claude Code's own `cost-state` to the cent for single-process sessions;
subscription billing differs.

Per analyzed session: title, summary, goal, outcome, work types, tags, highlights, open threads,
friction, sentiment, and knowledge items:

| Kind | Meaning |
| --- | --- |
| fix | a failure, its root cause, and the fix |
| gotcha | a pitfall and how to avoid it |
| learning | an insight about a technology or the codebase |
| decision | a design choice and its rationale |
| pattern | a reusable technique or snippet |
| command | a useful invocation |
| fact | project layout, config, endpoints, deployment |
| preference | how you want Claude to work |
| reference | an external pointer |
| todo | a follow-up |

Claude's own auto-memory notes (`projects/*/memory/*.md`) are imported as knowledge too.

## How analysis works

1. A session is queued once it ends (hook) or has been idle for `idle_minutes`.
2. The transcript is condensed into a digest at the richest detail level that fits `chunk_chars`
   (full prompts and replies, one line per tool call, error excerpts, subagent reports). Very long
   sessions are split at prompt boundaries and map-reduced. Secrets are redacted first.
3. `claude -p` runs with `--no-session-persistence --safe-mode --tools "" --strict-mcp-config`:
   no transcript is written for the analysis itself, no hooks/plugins/MCP load, and the model can only answer.
   `CHRONICLE_INTERNAL=1` makes the hooks inert for these runs.
4. The JSON reply is validated leniently (with one repair pass) and stored. When a project gains
   `min_new_items` new items, its knowledge base is re-synthesized; items that are outdated or
   duplicated get marked *superseded* (pinned and memory items are never superseded). Once every session of
   a finished week is analyzed, Claude writes that week's review (themes, accomplishments, learnings, open
   threads, recurring friction, concrete workflow suggestions).
5. Usage-limit or auth errors pause analysis for an hour; other failures back off 30 min → 2 h → 8 h.
   Calls have a wall-clock deadline, and a call frozen by the Mac going to sleep is killed right after wake and
   re-queued without counting as a failure. Sessions that continue after being analyzed are re-analyzed.

Cost: a typical session costs a few cents API-equivalent with Sonnet; `chronicle analyze --pending --dry-run`
estimates the backlog. `max_budget_usd` caps each call.

## Configuration (`~/.claude-chronicle/config.toml`)

| Key | Default | |
| --- | --- | --- |
| `sources.claude_dirs` | `["~/.claude"]` | multiple Claude config dirs are supported |
| `sources.codex_dirs` | `[]` | `["~/.codex"]` once Codex is connected |
| `sources.exclude_projects` | `[]` | glob patterns of project paths to ignore entirely |
| `analysis.auto` | `true` | analyze automatically |
| `analysis.model` / `effort` | `sonnet` / `medium` | any `claude --model` alias |
| `analysis.max_per_run` / `concurrency` | `6` / `2` | throttle per 15-minute run |
| `analysis.backfill` | `true` | also analyze sessions recorded before install |
| `analysis.idle_minutes` | `20` | |
| `synthesis.auto` / `min_new_items` | `true` / `3` | |
| `export.markdown` / `notes_dir` | `true` / `~/.claude-chronicle/notes` | |
| `server.port` | `8765` | |
| `inject.session_start` | `false` | knowledge digest in new sessions |

`CHRONICLE_HOME` relocates everything.

## Data & privacy

Everything stays on this machine: `~/.claude-chronicle/{chronicle.db, archive/, notes/, logs/}`.
The only thing sent anywhere is the redacted digest, sent to Claude through your own Claude Code
installation (the same service that produced the transcript). The dashboard binds to 127.0.0.1,
rejects foreign `Host` headers (DNS rebinding) and requires a custom header on state-changing requests (CSRF).

## Development

```bash
uv sync && uv run pytest -q        # 68 tests, ~8 s, uses a fake `claude` binary and a synthetic Codex home
# redeploy: --reinstall is required, uv caches local builds keyed on pyproject.toml only
uv tool install --force --reinstall --python 3.13 . && chronicle install   # install restarts the agents
```

Layout: `parser.py` (Claude transcript format), `codex_parser.py` (Codex rollouts), `connectors.py` (Sources),
`ingest.py` (archive + store), `digest.py` / `analyze.py` /
`llm.py` (analysis), `synthesize.py` (knowledge bases), `glossary.py`, `reviews.py`, `worker.py` (queue), `server.py` + `web/`
(dashboard), `mcp_server.py`, `export_md.py`, `hooks.py` / `install.py`, `cli.py`.
