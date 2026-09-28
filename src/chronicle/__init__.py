"""Chronicle: a local, self-analyzing archive of every coding-agent session (Claude Code, Codex, Copilot, Bob)."""

from importlib.metadata import PackageNotFoundError, version

try:  # single source of truth: pyproject.toml, via the installed package's metadata
    __version__ = version("agents-chronicle")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+unknown"
