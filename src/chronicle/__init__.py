"""Chronicle: a local, self-analyzing archive of every coding-agent session (Claude Code, Codex, Copilot, Bob, Antigravity)."""

from importlib.metadata import PackageNotFoundError, version

try:  # single source of truth: pyproject.toml, via the installed package's metadata
    __version__ = version("interlatch")
except PackageNotFoundError:
    try:  # an install from before the rename, under the package's old name
        __version__ = version("agents-chronicle")
    except PackageNotFoundError:  # running from a source tree that was never installed
        __version__ = "0.0.0+unknown"
