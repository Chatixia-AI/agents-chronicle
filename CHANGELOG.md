# Changelog

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
