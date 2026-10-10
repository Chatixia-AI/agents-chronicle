- **Your Chronicle setup moves over by itself:** the first time the dashboard or the background sync starts,
  Interlatch moves `~/.claude-chronicle` to `~/.interlatch` (a link stays at the old path, so nothing that still names
  it breaks) and updates everything that ran Chronicle: the Claude Code hooks and status line, the MCP server in each
  agent (now named `interlatch`, with permission rules for `mcp__chronicle__` tools renamed), the block in your
  `CLAUDE.md` / `AGENTS.md` files and the login items. `chronicle` keeps working as another name for the
  `interlatch` command, and `interlatch migrate --dry-run` shows what the move changes. An install of the
  `agents-chronicle` package offers the move to `interlatch` under **Status › Updates**.
