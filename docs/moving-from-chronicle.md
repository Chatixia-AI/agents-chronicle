# Moving from Chronicle

[← Interlatch](../README.md) · [Docs index](README.md)

Interlatch was called Chronicle. It is the same program under a new name: your sessions, knowledge, settings and
hub keep working, and moving takes one install.

## Update

**From the command line:** the package on PyPI is now `interlatch` (it was `agents-chronicle`). Switch to it with the
extras you had (`uv tool list --show-extras` shows them). Uninstall first: the two packages' commands clash.

```bash
uv tool uninstall agents-chronicle
uv tool install --python 3.13 'interlatch[app]'   # or plain interlatch, without the desktop app
```

**Update** in **Settings › Status › Updates** offers the same switch. Until you make it, `uv tool upgrade
agents-chronicle` keeps working: the last `agents-chronicle` release installs Interlatch and keeps both commands.

**The desktop app:** download `Interlatch-<version>-arm64.dmg` from the
[latest release](https://github.com/Chatixia-AI/agents-chronicle/releases/latest), drag **Interlatch** into
**Applications** and open it. It is a new app to macOS, so Chronicle.app stays where it was: delete it once
Interlatch has started.

## What moves by itself

The first time Interlatch runs on a computer that had Chronicle, it moves the setup over. `interlatch migrate` does the
same by hand, says what it changed, and does nothing on a computer that has already moved.

| What | Before | After |
| --- | --- | --- |
| Data folder | `~/.claude-chronicle` | `~/.interlatch`, with a link left at the old path so anything that still points there keeps working |
| MCP server, in every agent and MCP client it was added to | `chronicle`, tools `mcp__chronicle__…` | `interlatch`, tools `mcp__interlatch__…` |
| Claude Code hooks and status line | run `chronicle` | run `interlatch` |
| Login items (macOS launchd) | `com.claude-chronicle.sync`, `com.claude-chronicle.ui` | `com.interlatch.sync`, `com.interlatch.ui` |
| Login items (Linux systemd) | `chronicle-sync.timer`, `chronicle-ui.service` | `interlatch-sync.timer`, `interlatch-ui.service` |
| Permissions your agents were given for its tools | `mcp__chronicle__…` | `mcp__interlatch__…`, so agents aren't asked again |
| Lines it added to `CLAUDE.md` and `AGENTS.md` | `<!-- chronicle:friction:… -->` | `<!-- interlatch:friction:… -->` |

Every file it edits is backed up to `~/.interlatch/backups/` first, as when you connect an agent. The database keeps
its name (`chronicle.db`), and so do the other files in the folder.

## What keeps working

- **The `chronicle` command.** It is the same program as `interlatch`, so scripts and habits that call `chronicle …`
  still work. The docs use `interlatch`.
- **Environment variables.** Each `CHRONICLE_*` variable is still read; its `INTERLATCH_*` name (`INTERLATCH_HOME`,
  `INTERLATCH_HUB_URL`, …) wins when both are set.
- **Hubs.** A hub and the computers that send to it can move in any order: old and new versions keep talking to each
  other, and invites, sign-ins and tokens stay valid. A [hub in Docker](docker.md#update) moves with the current
  `compose.yaml`, which runs the image `ghcr.io/chatixia-ai/interlatch-hub`; its `.env`, volumes and data stay as
  they are. One that keeps its old `compose.yaml` keeps getting releases too, under the old image name.
- **A copy in Postgres** and a hub's team store keep their schemas and tables.
- **Links.** chronicle.chatixia.net now forwards to [interlatch.com](https://interlatch.com).

## The VS Code extension

The extension has a new name and identifier, **Interlatch** (`chatixia.interlatch`), so VS Code sees it as a new
extension and won't update the old one to it. Install it ([VS Code extension](vscode.md)) and uninstall
**Chronicle**; while both are installed, Interlatch suggests that once. Your `chronicle.*` settings are still read:
each `interlatch.*` setting you leave unset takes the old one's value.

Something not working? See [Troubleshooting](troubleshooting.md).
