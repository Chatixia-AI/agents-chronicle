"""The coding agents Chronicle records, and how each is named."""

AGENTS = {  # id -> (full name, short name, speaker label in digests)
    "claude": ("Claude Code", "Claude", "CLAUDE"),
    "codex": ("OpenAI Codex", "Codex", "CODEX"),
    "copilot": ("GitHub Copilot", "Copilot", "COPILOT"),
    "bob": ("IBM Bob", "Bob", "BOB"),
    "claude-ai": ("Claude.ai", "Claude.ai", "CLAUDE"),  # chats imported from a claude.ai data export
}


def full_name(agent: str | None) -> str:
    return AGENTS.get(agent or "claude", (agent or "agent",) * 3)[0]


def short_name(agent: str | None) -> str:
    return AGENTS.get(agent or "claude", (agent or "agent",) * 3)[1]


def speaker(agent: str | None) -> str:
    return AGENTS.get(agent or "claude", ("", "", (agent or "agent").upper()))[2]
