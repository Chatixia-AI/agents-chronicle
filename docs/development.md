# Development

[← Chronicle](../README.md) · [Docs index](README.md)

## Tests and a local install

```bash
uv sync && uv run pytest -q        # 88 tests, ~12 s: a fake `claude` binary and synthetic Codex, Copilot and Bob stores
# redeploy: --reinstall is required, uv caches local builds keyed on pyproject.toml only
uv tool install --force --reinstall --python 3.13 . && chronicle install   # install restarts the agents
```

## macOS app

`uv run --extra app chronicle app` runs it from the checkout (menu-bar actions that only make sense
in the bundle, such as Open at Login, are hidden). `./packaging/macos/build.sh` builds `dist/Chronicle.app` and
`dist/Chronicle-<version>-<arch>.dmg` (PyInstaller, ~30 s; `packaging/macos/Chronicle.spec`). One binary is both the
app (no arguments) and the CLI (any arguments), which is how hooks and MCP servers run it. Unsigned builds are ad-hoc
signed and run on the Mac that built them; to distribute, set `CHRONICLE_CODESIGN_IDENTITY` (a Developer ID
Application certificate) and `NOTARY_KEYCHAIN_PROFILE` (from `xcrun notarytool store-credentials`), and the script
signs, notarizes and staples the DMG. `packaging/macos/make_icon.py` redraws the icon (the `.icns`, and `web/icon.png`, which the dashboard and a from-source app window use). `desktop.py` extends
pywebview's Cocoa app delegate, hence the `<7` pin on pywebview.

## Releasing

Bump `version` in `pyproject.toml`, then publish a GitHub release tagged `v<version>`.
`.github/workflows/release.yml` runs the tests, publishes `agents-chronicle` to PyPI (trusted publishing,
environment `pypi`) and attaches the DMG to the release (signed and notarized when the `MACOS_*` / `APPLE_*`
secrets are set; see the workflow header). Running the workflow by hand (**Actions → Release → Run workflow**)
is a dry run: tests plus a DMG kept as a workflow artifact, nothing published.

### One-time setup before the first release

1. On PyPI, add a *pending publisher* (Account → Publishing): project `agents-chronicle`, owner
   `kayeungadrian-tam`, repository `agents-chronicle`, workflow `release.yml`, environment `pypi`.
2. In the GitHub repository, create an environment named `pypi` (Settings → Environments).
3. To ship a signed, notarized DMG (Apple Developer Program membership): export the *Developer ID Application*
   certificate with its key as a `.p12`, and add the secrets `MACOS_CERT_P12` (base64 of the file),
   `MACOS_CERT_PASSWORD`, `MACOS_CODESIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID` and `APPLE_APP_PASSWORD`
   (an app-specific password from account.apple.com). Without them the DMG is ad-hoc signed and users have to
   approve it in Privacy & Security.

## Diagrams

The diagrams in `docs/diagrams/` are `.excalidraw.svg` files: they render as images and open for editing in the
Excalidraw VS Code extension (`pomdtr.excalidraw-editor`) or on excalidraw.com; saving writes back to the same file.

## Code layout

`parser.py` (Claude transcript format), `codex_parser.py` (Codex rollouts), `copilot_parser.py` (Copilot agent
sessions + VS Code chat logs), `bob_parser.py` (Bob tasks), `agents.py` (agent names), `connectors.py` (Sources),
`ingest.py` (archive + store), `digest.py` / `analyze.py` /
`llm.py` (analysis), `synthesize.py` (knowledge bases), `glossary.py`, `reviews.py`, `worker.py` (queue), `server.py` + `web/`
(dashboard), `mcp_server.py`, `export_md.py`, `hooks.py` / `install.py`, `desktop.py` (macOS app), `cli.py`; `packaging/macos/` builds the app.

## Demo data

`docs/demo/make_demo.py` builds a Chronicle home from made-up sessions: a fictional developer with five projects
and about six weeks of work. It writes synthetic Claude Code transcripts and runs the real pipeline over them
(sync, analysis, knowledge bases, glossary, weekly reviews). A stand-in `claude` answers each analysis with
hand-written summaries and knowledge, so it costs nothing and needs no login. The screenshots in `docs/images/`
come from it.

```bash
uv run python docs/demo/make_demo.py /tmp/chronicle-demo
CHRONICLE_HOME=/tmp/chronicle-demo/home uv run python -m chronicle ui --port 8898 --open
```
