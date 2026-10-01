# Command line

[← Chronicle](../README.md) · [Docs index](README.md)

| Command | |
| --- | --- |
| `chronicle install [--yes] [--analyze all\|N\|later] [--[no-]notify-updates] [--dry-run]` | Setup: lists the agents found, asks which to record, imports them, offers to analyze them now with progress (which builds the Glossary and the Map), starts the dashboard ([Install](install.md#command-line)) |
| `chronicle app` | The desktop app (window + menu bar); needs the `app` extra |
| `chronicle ui [--open]` | Dashboard (also always running at :8765 after install; if it is, `chronicle ui` says so and `--open` opens it). Sessions, Knowledge, Projects and Glossary switch between Cards and List (a sortable table; click a row for details), remembered per page |
| `chronicle sessions [-p project] [--since 7d]` | List sessions |
| `chronicle show <id-prefix> [--transcript\|--markdown\|--json]` | Session overview or full conversation |
| `chronicle search <words>` | Full-text search over transcripts + knowledge (any language, 3+ chars) |
| `chronicle knowledge [query] [-k gotcha] [-p project]` | Browse extracted knowledge |
| `chronicle projects` / `chronicle stats [--since 30d]` | Per-project and overall statistics |
| `chronicle analyze <id> \| --pending [--limit N] [--dry-run] [--backend codex]` | Analyze now (`--dry-run` shows digest sizes, no tokens spent; `--backend` picks the agent for this run only) |
| `chronicle synthesize [--project P] [--global] [--all]` | Rebuild knowledge bases |
| `chronicle export [--full]` | Rewrite the Markdown vault |
| `chronicle export <id>… [--format md\|json\|raw] [--out PATH]` | Export sessions: one file, or a .zip of several (`raw`: the original transcript) |
| `chronicle glossary [term] [-p project] [--rebuild --all] [--themes]` | Your vocabulary: internal names, acronyms, domain terms with definitions and usage; `--themes` groups big categories into themes for the Map |
| `chronicle review [2026-W39\|current]` | Weekly engineering review written by the analysis model (automatic for each completed week) |
| `chronicle import <zip> [--analyze]` | Import chats from a claude.ai or ChatGPT data export (the .zip, its folder, or `conversations.json`); repeatable. See [Sources](sources.md) |
| `chronicle forget <id> [--delete-transcript]` | Remove a session from the vault for good (it is never re-ingested) |
| `chronicle sources` | Which agents are connected, and how |
| `chronicle connect <agent>` / `disconnect <agent>` | Start/stop recording `claude`, `codex`, `codex-cloud`, `copilot` or `bob` (data is kept) |
| `chronicle connect <client>` / `disconnect <client>` | Add or remove the MCP server in `claude-desktop`, `cursor`, `windsurf` or `gemini` |
| `chronicle mcp [--print-config]` | Run the MCP server (clients start it), or print a config entry for any other MCP client |
| `chronicle status` | Health: hooks, agents, MCP, queue, failures |
| `chronicle tailnet on\|off\|status [--anyone]` | Open the dashboard on your phone and other devices through Tailscale Serve, to your Tailscale login only (`--anyone`: everyone in your tailnet) ([Phone and other computers](devices.md#your-phone)) |
| `chronicle hub enable [--rotate]` | Make this computer the hub for your others; prints the `chronicle hub join` command to run on them |
| `chronicle hub join <address> --token <token>` / `hub leave` | Send this computer's sessions to a hub instead of recording them here, or stop ([Your other computers](devices.md#your-other-computers)) |
| `chronicle hub status` / `hub disable` | The computers sending to this hub; stop accepting them |
| `chronicle push` | On a computer that joined a hub: send its new sessions now (the hook and the background sync do this) |
| `chronicle config [edit]` | Show or edit `~/.claude-chronicle/config.toml` |
| `chronicle config set <section.key> <value>` | Change one setting, e.g. `chronicle config set analysis.backend codex` ([Configuration](configuration.md)) |

## Other ways in

**Markdown vault:** `~/.claude-chronicle/notes` (open it as an Obsidian vault): `Home.md`,
`Sessions/YYYY/MM/*.md` with YAML frontmatter, `Projects/*.md` (knowledge base + session list),
`Knowledge/<Kind>.md`, `Reviews/YYYY-Www.md`, `Glossary.md`, `Global Playbook.md`.

**Inside your agents** (MCP tools, registered in Claude Code and in each connected agent): `search_knowledge`, `search_sessions`, `get_session`,
`get_transcript`, `project_knowledge`, `glossary`, `recent_sessions`. Ask e.g. *"have we hit this error before?"*
or *"what is the deployer_ip rule?"*.

The MCP server is registered when you connect an agent (see [Sources](sources.md)). [MCP server](mcp.md) covers
each tool and how to connect other clients.
