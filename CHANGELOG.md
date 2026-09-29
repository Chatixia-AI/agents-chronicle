# Changelog

## Unreleased

- **Codex Cloud tasks:** `chronicle connect codex-cloud` (or **Settings › Sources › Codex Cloud**) records the tasks
  you ran at chatgpt.com/codex, through the `codex cloud` CLI: title, repository, changed files, the diff and a link,
  archived for good. Opt-in, since it goes online. The CLI has no task conversations, so these are not analyzed.
- **Update from the dashboard:** Settings › Status › Updates upgrades Chronicle with whatever installed it (uv
  tool, pipx, pip; a checkout install is reinstalled when its files changed) and restarts the dashboard; the
  desktop app links to the latest release. Checking PyPI happens only when you click **Check for updates**. See
  [Updating](docs/install.md#updating).
- The Sessions sidebar sorts and groups by last activity, so a long-running session stays under Today.
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
  Sources › Other MCP clients**) gives them Chronicle's MCP server; `chronicle mcp --print-config` prints an entry
  for any other client. Tool results are now redacted like analysis digests, and the tools are marked read-only.
  New [MCP server](docs/mcp.md) docs page.
- MIT license. Documentation split into a short README and pages under `docs/` (English and Japanese), with
  screenshots made from demo data (`docs/demo/make_demo.py`).

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
