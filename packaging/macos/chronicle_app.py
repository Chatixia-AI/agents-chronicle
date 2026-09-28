"""Entry point of Chronicle.app's executable.

The one binary is the app (no arguments) and the `chronicle` CLI (any arguments): Claude Code's hooks and
MCP servers run it through ~/.claude-chronicle/bin/chronicle with a subcommand.
"""

import sys


def run() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-psn_")]  # Finder adds -psn_… on old macOS
    if args:
        from chronicle.cli import main

        return main(args)
    from chronicle.desktop import main

    return main()


if __name__ == "__main__":
    sys.exit(run())
