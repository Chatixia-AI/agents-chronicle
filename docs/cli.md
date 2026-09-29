# Command line

[← Chronicle](../README.md) · [Docs index](README.md)

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
| `chronicle glossary [term] [-p project] [--rebuild --all] [--themes]` | Your vocabulary: internal names, acronyms, domain terms with definitions and usage; `--themes` groups big categories into themes for the Map |
| `chronicle review [2026-W39\|current]` | Weekly engineering review written by Claude (automatic for each completed week) |
| `chronicle forget <id> [--delete-transcript]` | Remove a session from the vault for good (it is never re-ingested) |
| `chronicle sources` | Which agents are connected, and how |
| `chronicle connect <agent>` / `disconnect <agent>` | Start/stop recording `claude`, `codex`, `copilot` or `bob` (data is kept) |
| `chronicle connect <client>` / `disconnect <client>` | Add or remove the MCP server in `claude-desktop`, `cursor`, `windsurf` or `gemini` |
| `chronicle mcp [--print-config]` | Run the MCP server (clients start it), or print a config entry for any other MCP client |
| `chronicle status` | Health: hooks, agents, MCP, queue, failures |
| `chronicle config [edit]` | Show or edit `~/.claude-chronicle/config.toml` |

## Other ways in

**Markdown vault:** `~/.claude-chronicle/notes` (open it as an Obsidian vault): `Home.md`,
`Sessions/YYYY/MM/*.md` with YAML frontmatter, `Projects/*.md` (knowledge base + session list),
`Knowledge/<Kind>.md`, `Reviews/YYYY-Www.md`, `Glossary.md`, `Global Playbook.md`.

**Inside your agents** (MCP tools, registered in Claude Code and in each connected agent): `search_knowledge`, `search_sessions`, `get_session`,
`get_transcript`, `project_knowledge`, `glossary`, `recent_sessions`. Ask e.g. *"have we hit this error before?"*
or *"what is the deployer_ip rule?"*.

The MCP server is registered when you connect an agent (see [Sources](sources.md)). [MCP server](mcp.md) covers
each tool and how to connect other clients.
