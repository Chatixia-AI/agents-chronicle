"""Release helpers for .github/workflows/release.yml (stdlib only, so the workflow runs it with the runner's python3).

    python3 packaging/release.py next patch|minor|major   the version after the latest vX.Y.Z tag
    python3 packaging/release.py notes VERSION            the changelog.d/ files VERSION releases, as release notes
    python3 packaging/release.py fold VERSION DATE        add "## VERSION (DATE)" with those files' lines to CHANGELOG.md,
                                                          and print the files to delete
    python3 packaging/release.py entry BASE               fail when the commits since BASE change what ships but add no
                                                          file to changelog.d/ (.github/workflows/changelog.yml)

Each pull request that users will notice adds its own file to changelog.d/. A release's notes are the files added since
the previous tag, so a pull request merged at any moment lands in exactly one release: nothing is renamed, and nothing
waits for the changelog pull request a release opens afterwards. The version itself lives in the git tags
(hatch-vcs), so a release commits nothing before it is tagged.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
FRAGMENTS = "changelog.d"
REPO_URL = "https://github.com/Chatixia-AI/agents-chronicle"
BUMPS = ("major", "minor", "patch")
SHIPPED = ("src/", "ee/src/", "docker/", "vscode-extension/")  # what users get: a change here needs a changelog entry
VERSION_HEADING = re.compile(r"^## (\d+)\.(\d+)\.(\d+)\b", re.M)


def parse(version: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", version.strip())
    return tuple(int(n) for n in m.groups()) if m else None


def latest(tags: list[str]) -> tuple[int, int, int]:
    found = [v for t in tags if t.strip().startswith("v") and (v := parse(t))]
    return max(found, default=(0, 0, 0))


def previous(tags: list[str], version: str) -> str | None:
    """The highest vX.Y.Z tag below version, or None for the first release."""
    below = [v for t in tags if t.strip().startswith("v") and (v := parse(t)) and v < parse(version)]
    return "v" + ".".join(map(str, max(below))) if below else None


def next_version(tags: list[str], bump: str) -> str:
    major, minor, patch = latest(tags)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"bump must be one of {', '.join(BUMPS)}, not {bump!r}")


def is_fragment(path: str) -> bool:
    """A changelog entry: a Markdown file directly in changelog.d/, other than its README."""
    return bool(re.fullmatch(rf"{FRAGMENTS}/[^/]+\.md", path)) and path != f"{FRAGMENTS}/README.md"


def unreleased(text: str) -> str:
    """The body of a "## Unreleased" section in CHANGELOG.md (empty when there is none). Entries live in changelog.d/
    now, so lines here are a pull request written the old way."""
    m = re.search(r"^## Unreleased[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def notes(entries: list[str], version: str) -> str:
    """Release notes: the entries one after another, their repository links made absolute (at the release's tag)."""
    body = "\n".join(e.strip() for e in entries if e.strip())
    return re.sub(r"\]\((?!https?://|#|mailto:)([^)]+)\)", lambda m: f"]({REPO_URL}/blob/v{version}/{m.group(1)})", body)


def fold(text: str, version: str, day: str, entries: list[str]) -> str:
    """CHANGELOG.md with a "## VERSION (DAY)" section of the entries, above the first lower version's section (so two
    changelog pull requests merged out of order still list the versions newest first)."""
    if re.search(rf"^## {re.escape(version)}\b", text, re.M):
        raise ValueError(f"CHANGELOG.md already has a '## {version}' section")
    section = f"## {version} ({day})\n\n" + "\n".join(e.strip() for e in entries if e.strip()) + "\n\n"
    for m in VERSION_HEADING.finditer(text):
        if tuple(int(n) for n in m.groups()) < parse(version):
            return text[:m.start()] + section + text[m.start():]
    return text.rstrip("\n") + "\n\n" + section.rstrip("\n") + "\n"


def not_ready(text: str, entries: list[str], last: str | None) -> str | None:
    """Why there is nothing to release yet, or None."""
    if unreleased(text):
        return (f"CHANGELOG.md has lines under '## Unreleased': move each into its own file in {FRAGMENTS}/ "
                f"(see {FRAGMENTS}/README.md), which is where release notes come from")
    if not any(e.strip() for e in entries):
        return f"nothing new in {FRAGMENTS}/ since {last or 'the start'} to release"
    return None


def missing_entry(changed: list[str], added: list[str], head: str) -> str | None:
    """Why a pull request needs a changelog entry it doesn't have, or None: it changes what ships (SHIPPED) and adds no
    file to changelog.d/ (added: the files it adds; head: CHANGELOG.md after it)."""
    if unreleased(head):
        return (f"this pull request puts lines under '## Unreleased' in CHANGELOG.md: move them into a new file in "
                f"{FRAGMENTS}/, e.g. {FRAGMENTS}/<topic>.md (see {FRAGMENTS}/README.md), and leave CHANGELOG.md as it is")
    shipped = [f for f in changed if f.startswith(SHIPPED)]
    if not shipped or any(is_fragment(f) for f in added):
        return None
    more = f" and {len(shipped) - 3} more" if len(shipped) > 3 else ""
    return (f"this pull request changes {', '.join(shipped[:3])}{more} but adds no file to {FRAGMENTS}/: add "
            f"{FRAGMENTS}/<topic>.md with a line saying what users will notice (see {FRAGMENTS}/README.md), or "
            "label the pull request no-changelog if they won't notice anything")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True, cwd=ROOT).stdout


def released(prev: str | None, ref: str) -> list[str]:
    """The changelog.d/ files at ref that prev did not have, in the order they were added."""
    def at(r: str | None) -> set[str]:
        return {p for p in git("ls-tree", "-r", "--name-only", r, "--", FRAGMENTS).splitlines() if is_fragment(p)} if r else set()

    new = at(ref) - at(prev)
    order = git("log", "--reverse", "--diff-filter=A", "--format=", "--name-only", f"{prev}..{ref}" if prev else ref,
                "--", FRAGMENTS).split()
    rank = {p: i for i, p in reversed(list(enumerate(order)))}  # the first time each was added
    return sorted(new, key=lambda p: (rank.get(p, len(order)), p))


def show(ref: str, path: str) -> str:
    return git("show", f"{ref}:{path}")


def main(argv: list[str]) -> int:
    cmd, *args = argv or ["help"]
    text = CHANGELOG.read_text()
    if cmd in ("next", "notes", "fold"):
        tags = git("tag", "--list", "v*").splitlines()
    if cmd == "next" and len(args) == 1:
        last = "v" + ".".join(map(str, latest(tags))) if latest(tags) != (0, 0, 0) else None
        if why := not_ready(text, [show("HEAD", p) for p in released(last, "HEAD")], last):
            print(f"::error::{why}", file=sys.stderr)
            return 1
        print(next_version(tags, args[0]))
    elif cmd == "notes" and len(args) == 1:
        ref = f"v{args[0]}" if f"v{args[0]}" in tags else "HEAD"  # before the tag exists, what it will tag
        print(notes([show(ref, p) for p in released(previous(tags, args[0]), ref)], args[0]))
    elif cmd == "fold" and len(args) == 2:
        ref = f"v{args[0]}"
        paths = released(previous(tags, args[0]), ref)
        CHANGELOG.write_text(fold(text, *args, [show(ref, p) for p in paths]))
        here = set(git("ls-tree", "-r", "--name-only", "HEAD", "--", FRAGMENTS).splitlines())
        print("\n".join(p for p in paths if p in here))
    elif cmd == "entry" and len(args) == 1:
        base = git("merge-base", args[0], "HEAD").strip()
        changed = git("diff", "--name-only", base, "HEAD").splitlines()
        added = git("diff", "--name-only", "--diff-filter=A", base, "HEAD").splitlines()
        if why := missing_entry(changed, added, text):
            print(f"::error file=CHANGELOG.md::{why}", file=sys.stderr)
            return 1
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
