"""Release helpers for .github/workflows/release.yml (stdlib only, so the workflow runs it with the runner's python3).

    python3 packaging/release.py next patch|minor|major   the version after the latest vX.Y.Z tag
    python3 packaging/release.py notes VERSION            the changelog's "## Unreleased" section, as release notes
    python3 packaging/release.py date VERSION DATE        rename "## Unreleased" to "## VERSION (DATE)" in CHANGELOG.md
    python3 packaging/release.py entry BASE               fail when the commits since BASE change what ships but add
                                                          nothing under "## Unreleased" (.github/workflows/changelog.yml)

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
SHIPPED = ("src/", "ee/src/", "docker/", "vscode-extension/")  # what users get: a change here needs a changelog entry


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


def not_ready(text: str, tags: list[str]) -> str | None:
    """Why the changelog cannot be released yet, or None."""
    last = ".".join(map(str, latest(tags)))
    if last != "0.0.0" and not re.search(rf"^## {re.escape(last)}\b", text, re.M):
        # the last release's changelog pull request is not merged: its lines are still under Unreleased
        return (f"CHANGELOG.md has no '## {last}' section: merge the changelog pull request for {last} first "
                f"(none open? open one from the changelog-{last} branch: {REPO_URL}/compare/main...changelog-{last}?expand=1)")
    if not unreleased(text):
        return "CHANGELOG.md has nothing under '## Unreleased' to release"
    return None


def missing_entry(base: str, head: str, changed: list[str]) -> str | None:
    """Why a pull request needs a changelog entry it doesn't have, or None: it changes what ships (SHIPPED) and leaves
    the Unreleased section as it was (base and head are CHANGELOG.md before and after)."""
    shipped = [f for f in changed if f.startswith(SHIPPED)]
    if not shipped or (unreleased(head) and unreleased(head) != unreleased(base)):
        return None
    more = f" and {len(shipped) - 3} more" if len(shipped) > 3 else ""
    return (f"this pull request changes {', '.join(shipped[:3])}{more} but adds nothing under '## Unreleased' in "
            "CHANGELOG.md: add a line there saying what users will notice (start the section if it's missing), or "
            "label the pull request no-changelog if they won't notice anything")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def main(argv: list[str]) -> int:
    cmd, *args = argv or ["help"]
    text = CHANGELOG.read_text()
    if cmd == "next" and len(args) == 1:
        tags = git("tag", "--list", "v*").splitlines()
        if why := not_ready(text, tags):
            print(f"::error::{why}", file=sys.stderr)
            return 1
        print(next_version(tags, args[0]))
    elif cmd == "notes" and len(args) == 1:
        print(notes(text, args[0]))
    elif cmd == "date" and len(args) == 2:
        CHANGELOG.write_text(date(text, *args))
    elif cmd == "entry" and len(args) == 1:
        base = git("merge-base", args[0], "HEAD").strip()
        changed = git("diff", "--name-only", base, "HEAD").splitlines()
        before = subprocess.run(["git", "show", f"{base}:CHANGELOG.md"], capture_output=True, text=True).stdout
        if why := missing_entry(before, text, changed):
            print(f"::error file=CHANGELOG.md::{why}", file=sys.stderr)
            return 1
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
