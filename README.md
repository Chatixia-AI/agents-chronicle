# Claude Chronicle

Records every coding-agent session on this machine (Claude Code, and when connected OpenAI Codex, GitHub
Copilot and IBM Bob) into a local vault, keeps the raw transcripts forever, and uses Claude Code itself (headless
`claude -p`) to turn each session into an overview plus reusable knowledge. Browse everything in a local dashboard,
an Obsidian-compatible Markdown vault, the CLI, or from inside the agents themselves through an MCP server.

![How Chronicle works: sources, archive, parse, SQLite, analysis with claude -p, knowledge, and the dashboard, vault, CLI and MCP server](docs/diagrams/architecture.excalidraw.svg)

## Why

- **Claude Code deletes transcripts after 30 days** (`cleanupPeriodDays`). Chronicle mirrors every
  file under `~/.claude/projects` into `~/.claude-chronicle/archive` (JSONL gzip-compressed) and never
  deletes it. Sessions whose transcripts were already gone are partially recovered from
  `~/.claude/history.jsonl` (prompts only, marked *history*).
- **Knowledge evaporates.** Fixes, gotchas, decisions and project facts discovered in a session are
  extracted, deduplicated per project, and made searchable, including by Claude itself in later sessions.

## Install

Chronicle runs on macOS and needs a logged-in [Claude Code](https://claude.com/claude-code) (`claude`), which
does the analysis. There are two ways to run it; both use the same data in `~/.claude-chronicle` and can coexist.

### Desktop app

1. Download `Chronicle-<version>-arm64.dmg` from the
   [latest release](https://github.com/kayeungadrian-tam/agents-chronicle/releases/latest) (Apple silicon, macOS 13+).
2. Open it and drag **Chronicle** into **Applications**, then open it from there.
3. On first launch, choose **Connect** to record Claude Code sessions. This adds the `SessionEnd` hook and the MCP
   server (as `chronicle connect claude` does) and makes Chronicle open at login.

If macOS says Chronicle "cannot be opened" or "cannot verify the developer", that release was not notarized:
open **System Settings → Privacy & Security**, click **Open Anyway** next to the Chronicle message, and confirm.
There is no Intel build yet; on an Intel Mac use the command line install.

Chronicle then lives in the menu bar. It serves the dashboard in its own window and does the 15-minute
background sync itself, so it needs no launchd agents; closing the window keeps it running. The menu-bar icon has:

| Menu item | |
| --- | --- |
| Open Chronicle / Open in Browser | The dashboard, in the app window or your browser |
| Sync Now | Archive, ingest and analyze now instead of at the next 15-minute run; the line above it shows the last sync |
| Connect Claude Code… | Shown until Claude Code is connected (if you chose *Not Now* at first launch) |
| Open at Login | On after connecting; turn it off to run Chronicle only when you open it |
| Install Command-Line Tool | Links the app's own `chronicle` command into `~/.local/bin` (skipped if one exists) |
| Open Data Folder | `~/.claude-chronicle` |

Codex, Copilot and Bob are connected from the dashboard's **Sources** page. Hooks and MCP registrations point
at `~/.claude-chronicle/bin/chronicle`, a small script the app rewrites on every launch, so moving or updating the
app does not break them. Quitting stops the sync until the next launch; an analysis cut off by quitting runs
again at the next sync.

Known issues when the app is used without a command-line install:

- The dashboard's **Status** and **Sources** pages and `chronicle status` show *Background sync* as not running,
  because they only check the launchd agent. The app's own sync is running; the menu-bar menu shows when it
  last ran.
- `analysis.backfill = false` has no effect: the app's Connect step does not record the install date that
  `chronicle install` records, so sessions from before connecting are analyzed too. To apply the setting, run
  `~/.claude-chronicle/bin/chronicle install --no-launchd --no-ui` once, which records the date and reinstalls
  the hook and MCP server.

To remove Chronicle, run `~/.claude-chronicle/bin/chronicle uninstall` (hooks and MCP
servers; data is kept), turn off **Open at Login**, and delete the app.

### Command line

```bash
uv tool install --python 3.13 agents-chronicle   # puts `chronicle` on PATH (~/.local/bin)
chronicle sync                                   # archive + ingest everything now
chronicle install                                # hooks, background agents, MCP server
chronicle connect codex                          # optional: codex, copilot, bob (see Sources)
```

Needs [uv](https://docs.astral.sh/uv/) (or `pipx install agents-chronicle`). To install from a checkout instead,
run `uv tool install --python 3.13 .` in it. `chronicle install` does four things (each can be skipped with
`--no-hooks`, `--no-launchd`, `--no-ui`, `--no-mcp`; preview with `--dry-run`):

| Piece | What it does |
| --- | --- |
| `SessionEnd` hook in `~/.claude/settings.json` | Hands the ended transcript to a detached process that archives, ingests and analyzes it. Returns in milliseconds; a backup of `settings.json` is kept in `~/.claude-chronicle/backups/`. |
| launchd `com.claude-chronicle.sync` | `chronicle sync --work` every 15 minutes: catches anything the hook missed, processes the analysis queue, synthesizes knowledge bases, exports notes. |
| launchd `com.claude-chronicle.ui` | Keeps the dashboard at <http://127.0.0.1:8765/>. |
| MCP server `chronicle` (user scope) | Lets Claude Code search your past sessions and knowledge. |

Optional: `chronicle install --inject-context` also adds a `SessionStart` hook that gives each new
session a short digest of the project's knowledge base (off by default; preview it with `chronicle context`).

Remove everything with `chronicle uninstall` (data is kept; `--purge` deletes it too).

To use the desktop app from a command-line install, add the `app` extra and run `chronicle app`:
`uv tool install --python 3.13 'agents-chronicle[app]'`. If you switch to the app for good, `chronicle uninstall`
first and let the app connect Claude Code, so the launchd agents do not run alongside it (harmless, but redundant).

## Sources: Claude Code, Codex, GitHub Copilot, IBM Bob

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

## Using it

| Command | |
| --- | --- |
| `chronicle app` | The desktop app (window + menu bar); needs the `app` extra |
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
| `chronicle connect <agent>` / `disconnect <agent>` | Start/stop recording `claude`, `codex`, `copilot` or `bob` (data is kept) |
| `chronicle status` | Health: hooks, agents, MCP, queue, failures |
| `chronicle config [edit]` | Show or edit `~/.claude-chronicle/config.toml` |

**Dashboard:** overview (active-time headline with active days and longest run; stat tiles with sparklines and
a per-day rate until a full prior period exists to compare against; daily chart with a 7-day average; outcome
breakdown; activity calendar with streaks; busiest hour; projects, tools with failed calls, models and agents),
sortable/filterable session list, project cards with 12 weeks of activity, session pages (summary, knowledge,
context-window chart with compactions, tools, files, subagents, PRs, full transcript replay with
collapsible tool calls and subagent threads), knowledge browser (pin/dismiss), project knowledge
bases, global playbook, glossary, a mindmap of the glossary (see Map below), weekly reviews, search with
jump-to-message. Glossary terms are underlined
wherever they appear (transcripts, knowledge, summaries): hover for the definition, click for the entry.
Every chart has a table view; light and dark themes.

**Markdown vault:** `~/.claude-chronicle/notes` (open it as an Obsidian vault): `Home.md`,
`Sessions/YYYY/MM/*.md` with YAML frontmatter, `Projects/*.md` (knowledge base + session list),
`Knowledge/<Kind>.md`, `Reviews/YYYY-Www.md`, `Glossary.md`, `Global Playbook.md`.

**Inside your agents** (MCP tools, registered in Claude Code and in each connected agent): `search_knowledge`, `search_sessions`, `get_session`,
`get_transcript`, `project_knowledge`, `glossary`, `recent_sessions`. Ask e.g. *"have we hit this error before?"*
or *"what is the deployer_ip rule?"*.

**Glossary:** built by Claude from each project's distilled knowledge (not the raw transcripts), one call per
project plus a cross-project pass, refreshed whenever a project's knowledge base is re-synthesized. Each term has
a category, aliases (abbreviations, translations of Japanese business terms), a definition, a per-project usage
note, related terms, and full-text statistics: how many sessions mention it, first and last seen, top sessions.

**Map:** the dashboard's **Map** page draws the glossary as a collapsible mindmap, built from data Chronicle
already has (no extra Claude calls). **By category** goes from categories to terms; **By project** goes from
projects to their categories to terms, with *Everywhere* holding the cross-project terms. Click a node to open or
close it, and a term to see its definition, where each project uses it, related terms (click to jump there) and
the knowledge items it was distilled from. Drag or scroll to move, pinch or ⌘-scroll to zoom; **Find a term**
opens the path to it, and the view glides to keep an opened branch on screen. Colour marks the category (the eight
largest have their own hue, the rest share grey); a term's dot grows with the number of sessions that mention it
(1, 2–4, 5+). With nothing selected, the side panel lists the terms shared by the most projects and the most
discussed ones. File
names and commands are hidden until you turn on **Files & commands**, no branch draws more than 10 children
(12 at the top): the most-discussed come first, and *+N more* lists the rest in the side panel, filterable as you
type, where picking one adds just that node to the map (search and related-term links do the same). Every glossary entry links to its place on the map (*on the map →*).

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

Claude's own auto-memory notes (`projects/*/memory/*.md`) and Codex's memory notes are imported as knowledge too.

Codex, Copilot and Bob sessions fill the same fields wherever their logs carry the data: Copilot Chat logs, for
instance, have no cache split (so no cost estimate), and Bob tasks have no per-call timings.

## How analysis works

![How a session becomes knowledge: queue, digest, claude -p, JSON validation, knowledge items, knowledge bases, glossary and weekly review](docs/diagrams/analysis.excalidraw.svg)

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

Cost: analysis runs through your Claude Code login. The reported cost is the API list-price equivalent: sessions
averaged about $0.38 each with Sonnet (digests average ~150k characters). On a Claude subscription that is drawn
from the plan's usage allowance rather than billed. `chronicle analyze --pending --dry-run` sizes a backlog, and
`max_budget_usd` caps each call.

## Configuration (`~/.claude-chronicle/config.toml`)

| Key | Default | |
| --- | --- | --- |
| `sources.claude_dirs` | `["~/.claude"]` | multiple Claude config dirs are supported |
| `sources.codex_dirs` | `[]` | `["~/.codex"]` once Codex is connected |
| `sources.copilot_dirs` | `[]` | `~/.copilot` and VS Code `User` dirs once Copilot is connected |
| `sources.bob_dirs` | `[]` | `["~/.bob"]` once Bob is connected |
| `sources.exclude_projects` | `[]` | glob patterns of project paths to ignore entirely |
| `analysis.auto` | `true` | analyze automatically |
| `analysis.model` / `effort` | `sonnet` / `medium` | any `claude --model` alias |
| `analysis.max_per_run` / `concurrency` | `6` / `2` | throttle per 15-minute run |
| `analysis.backfill` | `true` | also analyze sessions recorded before install |
| `analysis.idle_minutes` | `20` | |
| `synthesis.auto` / `min_new_items` | `true` / `3` | |
| `export.markdown` / `notes_dir` | `true` / `~/.claude-chronicle/notes` | |
| `server.port` | `8765` | the app uses a free port instead when this one is taken (e.g. by the launchd dashboard) |
| `inject.session_start` | `false` | knowledge digest in new sessions |

`CHRONICLE_HOME` relocates everything.

## Data & privacy

Everything stays on this machine: `~/.claude-chronicle/{chronicle.db, archive/, notes/, logs/}` (the app adds
`bin/chronicle`, the launcher its hooks call, and `webview/`, its window's storage).
The only thing sent anywhere is the redacted digest, sent to Claude through your own Claude Code
installation (the same service that produced the transcript). The dashboard binds to 127.0.0.1,
rejects foreign `Host` headers (DNS rebinding) and requires a custom header on state-changing requests (CSRF).
Other agents' stores are only read (SQLite databases through read-only connections and archived as snapshots);
Bob's login state is never read. Connecting an agent edits its MCP config, backed up to
`~/.claude-chronicle/backups/` first.

## Development

```bash
uv sync && uv run pytest -q        # 83 tests, ~10 s: a fake `claude` binary and synthetic Codex, Copilot and Bob stores
# redeploy: --reinstall is required, uv caches local builds keyed on pyproject.toml only
uv tool install --force --reinstall --python 3.13 . && chronicle install   # install restarts the agents
```

**macOS app:** `uv run --extra app chronicle app` runs it from the checkout (menu-bar actions that only make sense
in the bundle, such as Open at Login, are hidden). `./packaging/macos/build.sh` builds `dist/Chronicle.app` and
`dist/Chronicle-<version>-<arch>.dmg` (PyInstaller, ~30 s; `packaging/macos/Chronicle.spec`). One binary is both the
app (no arguments) and the CLI (any arguments), which is how hooks and MCP servers run it. Unsigned builds are ad-hoc
signed and run on the Mac that built them; to distribute, set `CHRONICLE_CODESIGN_IDENTITY` (a Developer ID
Application certificate) and `NOTARY_KEYCHAIN_PROFILE` (from `xcrun notarytool store-credentials`), and the script
signs, notarizes and staples the DMG. `packaging/macos/make_icon.py` redraws the icon. `desktop.py` extends
pywebview's Cocoa app delegate, hence the `<7` pin on pywebview.

**Releasing:** bump `version` in `pyproject.toml`, then publish a GitHub release tagged `v<version>`.
`.github/workflows/release.yml` runs the tests, publishes `agents-chronicle` to PyPI (trusted publishing,
environment `pypi`) and attaches the DMG to the release (signed and notarized when the `MACOS_*` / `APPLE_*`
secrets are set; see the workflow header). Running the workflow by hand (**Actions → Release → Run workflow**)
is a dry run: tests plus a DMG kept as a workflow artifact, nothing published.

One-time setup before the first release:

1. On PyPI, add a *pending publisher* (Account → Publishing): project `agents-chronicle`, owner
   `kayeungadrian-tam`, repository `agents-chronicle`, workflow `release.yml`, environment `pypi`.
2. In the GitHub repository, create an environment named `pypi` (Settings → Environments).
3. To ship a signed, notarized DMG (Apple Developer Program membership): export the *Developer ID Application*
   certificate with its key as a `.p12`, and add the secrets `MACOS_CERT_P12` (base64 of the file),
   `MACOS_CERT_PASSWORD`, `MACOS_CODESIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID` and `APPLE_APP_PASSWORD`
   (an app-specific password from account.apple.com). Without them the DMG is ad-hoc signed and users have to
   approve it in Privacy & Security.

Diagrams in `docs/diagrams/` are `.excalidraw.svg` files: they render as images and open for editing in the
Excalidraw VS Code extension (`pomdtr.excalidraw-editor`) or on excalidraw.com; saving writes back to the same file.

Layout: `parser.py` (Claude transcript format), `codex_parser.py` (Codex rollouts), `copilot_parser.py` (Copilot agent
sessions + VS Code chat logs), `bob_parser.py` (Bob tasks), `agents.py` (agent names), `connectors.py` (Sources),
`ingest.py` (archive + store), `digest.py` / `analyze.py` /
`llm.py` (analysis), `synthesize.py` (knowledge bases), `glossary.py`, `reviews.py`, `worker.py` (queue), `server.py` + `web/`
(dashboard), `mcp_server.py`, `export_md.py`, `hooks.py` / `install.py`, `desktop.py` (macOS app), `cli.py`; `packaging/macos/` builds the app.
