"""Release helpers for .github/workflows/release.yml (stdlib only, so the workflow runs it with the runner's python3).

    python3 packaging/release.py next patch|minor|major   the version after the latest vX.Y.Z tag
    python3 packaging/release.py notes VERSION            the changelog's "## Unreleased" section, as release notes
    python3 packaging/release.py date VERSION DATE        rename "## Unreleased" to "## VERSION (DATE)" in CHANGELOG.md

The version itself lives in the git tags (hatch-vcs), so a release commits nothing before it is tagged.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
REPO_URL = "https://github.com/Chatixia-AI/agents-chronicle"
BUMPS = ("major", "minor", "patch")


def latest(tags: list[str]) -> tuple[int, int, int]:
    found = [tuple(int(n) for n in m.groups()) for t in tags if (m := re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", t.strip()))]
    return max(found, default=(0, 0, 0))


def next_version(tags: list[str], bump: str) -> str:
    major, minor, patch = latest(tags)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"bump must be one of {', '.join(BUMPS)}, not {bump!r}")


def unreleased(text: str) -> str:
    """The body of the "## Unreleased" section (empty when there is none)."""
    m = re.search(r"^## Unreleased[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def notes(text: str, version: str) -> str:
    """Release notes: the Unreleased section, its repository links made absolute (they point at the release's tag)."""
    body = unreleased(text)
    return re.sub(r"\]\((?!https?://|#|mailto:)([^)]+)\)", lambda m: f"]({REPO_URL}/blob/v{version}/{m.group(1)})", body)


def date(text: str, version: str, day: str) -> str:
    new, n = re.subn(r"^## Unreleased[ \t]*$", f"## {version} ({day})", text, count=1, flags=re.M)
    if not n:
        raise ValueError("CHANGELOG.md has no '## Unreleased' section")
    return new


def main(argv: list[str]) -> int:
    cmd, *args = argv or ["help"]
    text = CHANGELOG.read_text()
    if cmd == "next" and len(args) == 1:
        if not unreleased(text):
            print("::error::CHANGELOG.md has nothing under '## Unreleased' to release", file=sys.stderr)
            return 1
        tags = subprocess.run(["git", "tag", "--list", "v*"], capture_output=True, text=True, check=True).stdout
        print(next_version(tags.splitlines(), args[0]))
    elif cmd == "notes" and len(args) == 1:
        print(notes(text, args[0]))
    elif cmd == "date" and len(args) == 2:
        CHANGELOG.write_text(date(text, *args))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
