# Install

[← Chronicle](../README.md) · [Docs index](README.md)

Chronicle runs on macOS and needs a logged-in [Claude Code](https://claude.com/claude-code) (`claude`) or [Codex](https://github.com/openai/codex) (`codex`), which does the analysis. Setup uses Claude Code when it is installed and offers Codex when it is not; switch any time in **Status › Analysis** or with `chronicle config set analysis.backend codex`. There are two ways to run it; both use the same data in `~/.claude-chronicle` and can coexist.

## Desktop app

1. Download `Chronicle-<version>-arm64.dmg` from the
   [latest release](https://github.com/Chatixia-AI/agents-chronicle/releases/latest) (Apple silicon, macOS 13+).
2. Open it and drag **Chronicle** into **Applications**, then open it from there.
3. On first launch, choose **Connect** to record Claude Code sessions. This adds the `SessionEnd` hook and the MCP
   server (as `chronicle connect claude` does) and makes Chronicle open at login.

If macOS says Chronicle "cannot be opened" or "cannot verify the developer", that release was not notarized:
open **System Settings → Privacy & Security**, click **Open Anyway** next to the Chronicle message, and confirm.
There is no Intel build yet; on an Intel Mac use the command line install.

Chronicle then lives in the menu bar. It serves the dashboard in its own window and does the 15-minute
background sync itself, so it needs no launchd agents; closing the window keeps it running. The window has no
title bar: the sidebar is native macOS glass (it blurs whatever is behind the window) with the traffic lights on
top of it, and the window moves by its toolbar or the strip above the sidebar. The menu-bar icon has:

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

To remove Chronicle, run `~/.claude-chronicle/bin/chronicle uninstall` (hooks and MCP
servers; data is kept), turn off **Open at Login**, and delete the app.

## Command line

```bash
uv tool install --python 3.13 agents-chronicle   # puts `chronicle` on PATH (~/.local/bin)
chronicle install                                # pick the agents to record, import, start the dashboard
```

Needs [uv](https://docs.astral.sh/uv/) (or `pipx install agents-chronicle`). To install from a checkout instead,
run `uv tool install --python 3.13 .` in it.

`chronicle install` (also `chronicle setup`) walks through setup:

1. Checks the agent that analyzes sessions (Claude Code by default). If it is missing and Codex is installed, offers
   to analyze with Codex instead; with neither, sessions are recorded but not analyzed until one is installed.
2. Lists the coding agents on this Mac (Claude Code, Codex, GitHub Copilot, IBM Bob) and the MCP-only clients it
   finds (Claude Desktop, Cursor, Windsurf, Gemini CLI), with how many sessions each has on disk.
3. Asks, for each one found and not yet connected, whether to record it (default yes), and whether to give each
   MCP client Chronicle's tools. Codex Cloud is offered after Codex and defaults to no, since it goes online.
   Declining Claude Code stops Chronicle scanning `~/.claude`.
4. Connects the chosen ones, exactly as `chronicle connect <name>` does ([Sources](sources.md)), and imports their
   past sessions (skip with `--no-sync`; the background sync does it then).
5. Asks whether to run Chronicle in the background, starting at login (default yes): the 15-minute sync and the
   always-on dashboard below. If you say no, Claude Code sessions are still recorded and analyzed as they end;
   run `chronicle sync --work` for the rest and `chronicle ui --open` for the dashboard. Not asked again once the
   agents run; `--no-launchd --no-ui` turns them off. With the background sync on, it also asks once whether to
   show a desktop notification when a new version of Chronicle is out (`--notify-updates` or
   `--no-notify-updates` answers without asking).
6. Explains analysis: each past session is read through your Claude Code (or Codex) login, which counts toward
   your plan's usage, and the knowledge it yields builds each project's knowledge base, then the **Glossary**, then
   the **Map**. Until sessions are analyzed, those two stay empty. It says how many sessions are waiting and how
   long the background takes over them (6 every 15 minutes), then asks whether to analyze them now with a
   progress bar per stage (sessions, knowledge bases, glossary, map themes): all of them, or the newest 20 for a
   first Glossary and Map in minutes. Ctrl-C stops, keeping what is done; the rest is analyzed in the background.
   `--analyze all`, `--analyze N` (the newest N) or `--analyze later` answers without asking.
7. Prints the dashboard address; on a first install it offers to open it.

Without a terminal, or with `--yes`, it takes the defaults without asking (analysis: later). Re-running it is safe: connected
agents are refreshed without a question, so it asks only about agents installed since. `--dry-run` shows what it
would do and changes nothing.

For Claude Code, and for the Mac itself, it sets up four things (each can be skipped with `--no-hooks`,
`--no-launchd`, `--no-ui`, `--no-mcp`). `--no-launchd` and `--no-ui` also remove their agent if it is installed, so
`chronicle install --no-launchd --no-ui` turns background running off and keeps everything else:

| Piece | What it does |
| --- | --- |
| `SessionEnd` hook in `~/.claude/settings.json` | Hands the ended transcript to a detached process that archives, ingests and analyzes it. Returns in milliseconds; a backup of `settings.json` is kept in `~/.claude-chronicle/backups/`. |
| launchd `com.claude-chronicle.sync` | `chronicle sync --work` every 15 minutes: catches anything the hook missed, processes the analysis queue, synthesizes knowledge bases, exports notes. |
| launchd `com.claude-chronicle.ui` | Keeps the dashboard at <http://127.0.0.1:8765/>. |
| MCP server `chronicle` (user scope) | Lets Claude Code search your past sessions and knowledge. |

Optional: `chronicle install --inject-context` also adds a `SessionStart` hook that gives each new
session a short digest of the project's knowledge base (off by default; preview it with `chronicle context`).

Optional: `chronicle install --statusline` records each Claude Code session's real context use and, on Pro and Max
plans, how far the 5-hour and 7-day limits moved while it ran (Claude Code shares these only with the status line).
It sets `statusLine` in `~/.claude/settings.json` to `chronicle statusline`, which saves the snapshot under
`~/.claude-chronicle/statusline/` and then runs the status line you already had, with the same input, so it looks
exactly as before; your original is kept in `~/.claude-chronicle/statusline/wrapped.json`. If you had none, it
shows model, context and limits, and Claude Code then hides most of its footer key hints. The sync copies each
session's numbers into the database (the session page and **Status**). `chronicle uninstall` puts your own status
line back.

Remove everything with `chronicle uninstall` (data is kept; `--purge` deletes it too). It also restores your own
status line if `--statusline` wrapped it.

To use the desktop app from a command-line install, add the `app` extra and run `chronicle app`:
`uv tool install --python 3.13 'agents-chronicle[app]'`. If you switch to the app for good, `chronicle uninstall`
first and let the app connect Claude Code, so the launchd agents do not run alongside it (harmless, but redundant).

## Updating

**Settings › Status › Updates** shows how Chronicle was installed and updates it the same way:

| Installed with | Update button runs |
| --- | --- |
| `uv tool install agents-chronicle` | `uv tool upgrade agents-chronicle`, after **Check for updates** finds a newer release |
| `uv tool install .` (a checkout) | `uv tool upgrade --reinstall agents-chronicle`, offered when the checkout's files changed after the install; no network check |
| `pipx` or `pip` | `pipx upgrade agents-chronicle` or `pip install --upgrade agents-chronicle` |
| The desktop app | Nothing: **Download** opens the latest release to drag into Applications |

Only **Check for updates** goes online (to pypi.org), or, if you turn on **Check for updates daily** on the same
card, a check once a day while the dashboard is open. **Notify me about new versions** (also offered by `chronicle
install`) has the background sync check once a day instead, dashboard open or not, and show a desktop notification
once per release saying how to update: macOS Notification Center, or `notify-send` on Linux. On macOS clicking the
notification opens Script Editor, which posts it for Chronicle; the notification text says where to update. The
last answer is kept across restarts. Once an update is known, a notification says so (once per release, or per new commit in a checkout; **Later**
dismisses it), Settings gets a dot and the status bar shows **Update to …**. A checkout's Updates card lists the
commits and changed files a reinstall would bring in.
A dashboard run by `chronicle ui` (or its launchd agent) restarts itself afterwards and open tabs reload; a
`chronicle app` from the command line needs quitting and reopening. The button waits while a sync or analysis runs.
From a terminal, run the same command yourself.

Something not working? See [Troubleshooting](troubleshooting.md).
