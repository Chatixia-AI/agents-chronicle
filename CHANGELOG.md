# Changelog

## Unreleased

- **Suggestions go to the right file:** a preference about how you work (one the analysis marked *global*) is now
  proposed once for your user-level `CLAUDE.md` or `AGENTS.md`, not once for each project it came up in. Other global
  knowledge, like a gotcha about a tool, stays in its project's file, since the user-level file is read in every
  session. Each waiting card can move: **Move to every project**, or from the user level back to the projects it came
  from (`chronicle suggest move ID --to user|project`). Chronicle remembers the choice for that lesson or cause, its
  other waiting cards move along, and your edited wording comes too. Lines you dismissed or applied no longer use up
  one of a file's 8 places, so the next ones come up. A card whose lesson moved to another file, or that is waiting
  for a place, now leaves the queue quietly instead of showing as stale.
  [Moving a line](docs/suggestions.md#moving-a-line)
- **Easier to read at a glance:** on Suggestions, the status filter is one joined switch and **What goes wrong** is a
  link, so **Check again** is the only button in the header. The rail icons show their name and what the section
  holds as soon as you point at them or tab to them, in the app window too.

## 0.6.0 (2026-10-02)

- **Screen imported chats before analyzing them:** years of claude.ai and ChatGPT chats are mostly lookups, rewrites
  and everyday questions, and analyzing all of them would take your plan's limits for days. **Screen N chats** on the
  export's card (Sources › Chat exports) or `chronicle screen` sorts them into *worth analyzing*, *maybe* and *not
  worth it*, each with a topic and a one-line reason, reading only each chat's opening. Rules settle the certain cases
  without a model call (no reply, too short, translating or summarizing pasted text); Haiku (`analysis.screen_model`)
  reads the rest, 60 chats a call, knowing which projects you work on, and keeps anything about your own work at least
  *maybe*. Nothing is analyzed until you choose **Queue N worth analyzing** (`chronicle screen --queue`, `--maybe` for
  the maybes too). The Sessions list gets a *Screening* filter and shows each chat's verdict and reason until it is
  analyzed; `chronicle screen --list analyze` does the same on the command line, `--sample 200` tries it first, and
  `chronicle import --screen` screens right after importing. A chat is screened again when a newer export changes it,
  and a chat queued for analysis now stays queued when a newer export updates it.
  [Screening imported chats](docs/sources.md#screening-imported-chats)
- **Knowledge earns its trust:** every knowledge item now has a stage, *tentative*, *seen once*, *established* or
  *canonical*, computed from how many sessions confirmed it and over how long, never guessed by the model. When
  synthesis finds the same lesson in another session it reports the pair as a duplicate, and the surviving item
  takes over that session: two sessions make it established, three over at least two weeks (or a pin) make it
  canonical, and the reason is kept ("confirmed in 3 sessions over 19 days"). Search, the MCP tools and the
  SessionStart digest list the most trusted knowledge first and label it (`[gotcha · established ×3]`);
  knowledge-base bullets, knowledge cards and the knowledge table show the stage. A superseded item now names the
  item that replaced it and why (duplicate, outdated, contradicted), and established or canonical knowledge that a
  newer session overturns is listed under **Overturned** in that week's review. Existing items get their stage on
  upgrade. [How knowledge earns trust](docs/analysis.md#how-knowledge-earns-trust)
- **Every waiting session says why:** a session that is not analyzed yet explains it on its page (still active and
  analyzed around 14:20, retrying at 16:05 after a timeout, project excluded, too few prompts, from before install
  with backfill off, failed four times…), and **Status** and `chronicle status` count the queue per reason. Sessions
  that will never be analyzed without a change are now counted as *held* instead of *queued*, and the status bar no
  longer counts ready sessions twice. When the whole queue is stopped (paused, automatic analysis off, analyzer not
  found) that is said too.
- **Real context and plan usage from the status line (optional):** `chronicle install --statusline` records, per
  Claude Code session, the peak context window use and, on Pro and Max plans, how far the 5-hour and 7-day limits
  moved while it ran. Claude Code shares these only with its status line, so Chronicle wraps yours: it records the
  numbers, then runs your own status line with the same input, so it looks exactly as before (with none, it shows
  model, context and limits). Session pages and **Status** show the numbers; sessions without a record stay unknown
  rather than zero. `chronicle uninstall` restores your status line.
- **What goes wrong, and fixes to approve:** Chronicle now finds the failures that keep coming back across your
  sessions, from failed tool calls and the friction notes analysis writes, with no model call: Playwright refusing a
  screenshot path or a busy browser, edits on stale context, zsh globs that match nothing, `sleep` polling blocked,
  a missing `timeout`, ports already taken, relative `cd`s, several sessions in one tree, and more. Expected failures
  (tests failing in a dev loop, read-only checks, provider outages, calls you turned down) are kept apart as noise.
  The **What goes wrong** page and `chronicle friction` show each cause's sessions, projects, 12-week trend and
  whether it is still happening, plus the tools that fail most.
- **Suggestions:** one queue of proposed fixes for those causes, and for knowledge confirmed often enough to tell your
  agents: a line for `CLAUDE.md` or `AGENTS.md` (user level, or the project's), the Playwright MCP arguments for
  `~/.claude.json`, or a setup step such as `setopt NO_NOMATCH`, which Chronicle shows and never runs. Nothing is
  written until you apply one: **Preview** shows the diff, the file is backed up first, the line goes inside
  Chronicle's own `<!-- BEGIN chronicle -->` block at the end of the file, and **Undo** takes it back out. You can
  edit the line before applying. Warnings flag a public repository (checked with `gh`), text that looks sensitive,
  and files git doesn't track. A dismissed suggestion never comes back, and one whose cause stopped happening goes
  stale. The queue refreshes after each background sync; the rail shows a badge for new ones, Home shows the top 3,
  and `[suggestions] notify = true` adds a desktop notification. On the command line: `chronicle suggest` (`show`,
  `apply`, `dismiss`, `done`, `undo`, `refresh`). [Suggestions and What goes wrong](docs/suggestions.md)
- **Fixed: a partly downloaded export was "not a chat export".** A large ChatGPT export (gigabytes of
  attachments) whose download stopped early lacks the end of the zip, so it was rejected outright. ChatGPT puts the
  chats first, so Chronicle now reads them from such a zip and says the download was incomplete; if the cut falls
  inside the chats, it says to download the export again.

## 0.5.1 (2026-10-01)

- **Hear about new versions:** turn on **Notify me about new versions** (Status › Updates, or say yes when
  `chronicle install` asks) and the background sync asks pypi.org once a day, dashboard open or not, and shows a
  desktop notification once per release saying how to update. macOS shows it in Notification Center, Linux through
  `notify-send`. Off by default; it sends nothing about you. `chronicle install --notify-updates` (or
  `--no-notify-updates`) answers without asking.

## 0.5.0 (2026-10-01)

- **On your phone:** `chronicle tailnet on` puts the dashboard on your Tailscale network with Tailscale Serve, at
  `https://<computer>.<tailnet>.ts.net/`, for your Tailscale login only (`[server] allowed_hosts` and
  `allowed_users`); nothing is opened to the internet. On a phone the dashboard puts its sections in a tab bar at
  the bottom, uses the whole width, keeps clear of the notch and opens Sessions as cards; **Add to Home Screen**
  gives it an icon and opens it like an app.
- **One archive for several computers:** `chronicle hub enable` makes a computer the hub, and prints the `chronicle
  hub join` command to run on the others. They send their Claude Code and Codex sessions to the hub as each one ends
  and every 15 minutes (`chronicle push` sends now); the hub records and analyzes them, once, and a computer that
  already analyzed sessions hands those analyses over when it joins. Sessions from each computer are filed under the
  hub's projects by git remote, or by `[hub] path_map`. A session's page names the computer it ran on, and the new
  **Settings › Devices** page lists the computers. See [Phone and other computers](docs/devices.md).
- **Install builds the Glossary and the Map:** `chronicle install` now explains that the Glossary and the Map are
  built from analyzed sessions, says how many are waiting and how long the background would take, and offers to
  analyze them now (all, or the newest 20) with a progress bar for each stage: sessions, knowledge bases, glossary,
  map themes. `--analyze all|N|later` answers without asking. Before, a fresh install left both pages empty for
  hours while the background worked through the backlog 6 sessions at a time.
- Ctrl-C during `chronicle analyze` (or install) now stops after the sessions already in progress instead of
  running the rest of the queue.
- Where nothing can run in the background, `chronicle install` no longer says past sessions are analyzed there.
- **Linux:** `chronicle install` runs the background sync and the dashboard as systemd user units, so a Linux box
  can be the hub.

## 0.4.0 (2026-09-30)

- **Search all sessions:** the Search page (now also in the rail) lists every session that mentions a word or
  phrase, with how many times, ordered by most mentions, newest or oldest. Each session shows its mentions in
  transcript order with the terms highlighted and who said them; **Show all** lists every mention. Clicking one
  opens the transcript at that message with the terms still highlighted, including inside folded tool calls.

## 0.3.0 (2026-09-30)

- **Analyze with Codex:** sessions, knowledge bases, the glossary and weekly reviews can now be written by OpenAI
  Codex instead of Claude Code, through your own Codex login. Pick it in **Status › Analysis**, with `chronicle
  config set analysis.backend codex`, or for one run with `chronicle analyze --backend codex`; `codex_model` picks
  the model. `chronicle install` offers Codex when Claude Code is not installed, so Chronicle no longer needs
  Claude Code at all. Codex runs sandboxed like Claude does: no session is saved for the analysis, none of your
  hooks, plugins, MCP servers, `AGENTS.md` or skills load, every tool feature is off, and Chronicle discards any
  reply that follows a tool call. Codex reports tokens but no price, so Codex analyses show no cost.
- `chronicle config set <section.key> <value>` changes one setting from the command line.
- A configured `claude_bin` or `codex_bin` that does not exist now fails the analysis cleanly instead of stopping
  the background run.

## 0.2.1 (2026-09-30)

- Chronicle moved to the [Chatixia-AI](https://github.com/Chatixia-AI) organization, and the documentation to
  <https://chronicle.chatixia.net/>. Old GitHub links redirect.
- `chronicle --version` works; 0.1.2 announced it but never shipped the flag.
- `chronicle search` shows snippet labels dimmed instead of printing `[dim]` markup literally.

## 0.2.0 (2026-09-30)

- **Knowledge overview:** the Knowledge section opens on a page with a card each for the Map, All knowledge, the
  Glossary and Weekly reviews, each with a glance at what is inside; the full list moved to **All knowledge**
  (`#/knowledge/all`; older `#/knowledge?kind=…` links still work).
- **Weekly reviews you can skim:** one week at a time, picked from a strip of weeks: a three-line TL;DR, the week's
  numbers against the week before, active time per day, where the time went, outcomes and the knowledge captured,
  then themes and short lists (shipped, learned, still open, slowed you down, try next) whose items open to their
  full text. The long write-up is folded away. New reviews are written to word limits and include the TL;DR.
- **Knowledge bases and the global playbook you can skim:** a TL;DR, a few figures, chips that jump to each
  section, a filter, and each section as a card of short bullets that open to their detail and the sessions they
  came from; the overview is folded away. Synthesis now writes a TL;DR, a short overview and a title per bullet,
  within word limits; existing knowledge bases pick this up the next time they are synthesized.
- **Guided setup:** `chronicle install` (or `chronicle setup`) lists the coding agents and MCP clients it finds,
  asks which to record, imports their past sessions, asks whether to run in the background from login (the
  15-minute sync and the always-on dashboard; previously always installed) and ends with the dashboard address,
  offering to open it. `--no-launchd` / `--no-ui` now also remove those agents if installed, so
  `chronicle install --no-launchd --no-ui` turns background running off.
  `--yes` (or no terminal) takes the defaults; re-running asks only about newly installed agents. Running
  `chronicle` on its own now shows help and, before setup, points to `chronicle install`.
- **Claude.ai and ChatGPT chats:** import a claude.ai or ChatGPT data export with **Settings › Sources › Chat
  exports › Import export…** or `chronicle import <zip>`; the format is recognized. Chats become sessions you can
  search, browse and analyze on demand; re-importing a newer export adds only new and changed chats. The account
  files in the export are never read.
- **Codex Cloud tasks:** `chronicle connect codex-cloud` (or **Settings › Sources › Codex Cloud**) records the tasks
  you ran at chatgpt.com/codex, through the `codex cloud` CLI: title, repository, changed files, the diff and a link,
  archived for good. Opt-in, since it goes online. The CLI has no task conversations, so these are not analyzed.
- **Update from the dashboard:** Settings › Status › Updates upgrades Chronicle with whatever installed it (uv
  tool, pipx, pip; a checkout install is reinstalled when its files changed) and restarts the dashboard; the
  desktop app links to the latest release. Checking PyPI happens only when you click **Check for updates**. An
  update on offer shows a notification (once per release, or per new commit for a checkout install), a dot on
  Settings and a chip in the status bar; a checkout's Updates card lists the commits and files it would bring in.
  **Check for updates daily** (off by default, `[updates] check_daily`) asks PyPI once a day while the dashboard
  is open; the last answer survives a restart. See [Updating](docs/install.md#updating).
- **Map search finds everything:** **Find terms** opens every match on the map at once (terms by name, alias or
  definition, plus themes, categories, projects and agents by name), highlights them, trims the branches on the way
  to just the path, and lists the matches in the side panel. The search is kept in the link.
- The Sessions list and a project's session table have an **Agent** column (sortable), with the same colour per agent as
  the Sources page; Codex Cloud tasks show as Codex · Cloud.
- The Sessions sidebar sorts and groups by last activity, so a long-running session stays under Today.
- **MCP page:** Settings › MCP shows which agents and clients have Chronicle's MCP server (adding or removing
  the other clients moved here from Sources), ready-to-copy config for most clients, VS Code, Codex and Claude
  Code, the tools and what to ask.
- **Export sessions:** **Export** on a session page, or on a selection in the Sessions list, downloads Markdown
  (overview and conversation), JSON (every event) or the original transcript; several sessions come as a .zip with
  an index. `chronicle export <id>… --format md|json|raw` does the same from a terminal. Secrets are redacted except
  in the original transcript.
- **Analyze a selection:** tick sessions in the Sessions list (shift-click for a range, or **Select all matching**)
  and choose **Analyze** to run them in one background job, skipped ones such as imported chats included.
- **Activity:** clicking the status bar opens what is running, with a progress bar, time so far and an estimate of
  time left, plus the analysis queue and recent results. The dashboard serves the page it started with, so an
  upgrade (or an edit to a checkout) never pairs a new page with old code before the restart.
- **Sources** is a list: a row per coding agent, chat export and MCP client that opens to its checks and actions.
  A connected agent with a failing check opens on its own.
- **New dashboard design:** a simpler VS Code layout in Apple's Liquid Glass style. An icon rail and per-section
  sidebar replace the top navigation, with a glass toolbar and breadcrumbs, a status bar, and a ⌘K palette that
  searches sessions, knowledge, projects and glossary terms and runs commands. New **Appearance** settings (theme,
  Reduce transparency).
- **Session pages** lead with headline figures, the summary and its knowledge, then switch between **Transcript**
  (one-line tool calls; **Load earlier** for links into the middle of a session) and **Details**, with an outline of
  prompts and changed files that follows the scroll.
- **macOS app:** no title bar. The sidebar is native glass with the traffic lights on it; the toolbar drags and
  zooms the window; the window follows the page's theme and the macOS Reduce transparency setting.
- New app icon, favicon and per-page titles.
- **MCP for more clients:** `chronicle connect claude-desktop`, `cursor`, `windsurf` or `gemini` (or **Settings ›
  MCP › Other MCP clients**) gives them Chronicle's MCP server; `chronicle mcp --print-config` prints an entry
  for any other client. Tool results are now redacted like analysis digests, and the tools are marked read-only.
  New [MCP server](docs/mcp.md) docs page.
- MIT license. Documentation split into a short README and pages under `docs/` (English and Japanese), with
  screenshots made from demo data (`docs/demo/make_demo.py`).
- The source is public, and the documentation is online at <https://chronicle.chatixia.net/> (English and Japanese), built from
  `docs/` and the READMEs with MkDocs.

## 0.1.2 (2026-09-28)

- **Map:** stack any of four levels (Category, Theme, Project, Agent); terms open into the knowledge items and
  sessions behind them.
- **Themes:** Claude groups large glossary categories into named themes (`chronicle glossary --themes`).
- `chronicle --version` reports the installed version.
- Japanese README.

## 0.1.1 (2026-09-28)

- User-facing text describes Chronicle as agent-neutral (Claude Code, Codex, GitHub Copilot, IBM Bob).

## 0.1.0 (2026-09-28)

- First release on PyPI as `agents-chronicle`, and the macOS desktop app (menu bar, background sync, DMG).
- Records Claude Code, Codex, GitHub Copilot and IBM Bob sessions; analyzes them with `claude -p` into summaries and
  knowledge; project knowledge bases, glossary and Map, weekly reviews, Markdown vault, CLI and MCP server.
