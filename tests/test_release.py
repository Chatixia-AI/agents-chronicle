"""packaging/release.py: the next version from the tags, release notes and dating the changelog."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("release", Path(__file__).parents[1] / "packaging" / "release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

CHANGELOG = """# Changelog

## Unreleased

- **New:** see [the docs](docs/devices.md#people) and [PyPI](https://pypi.org/) or [below](#x).

## 0.6.1 (2026-10-02)

- Older.
"""


def test_next_version_follows_the_highest_tag():
    tags = ["v0.6.1", "v0.10.0", "v0.9.3", "v1.0.0rc1", "nightly"]
    assert release.next_version(tags, "patch") == "0.10.1"
    assert release.next_version(tags, "minor") == "0.11.0"
    assert release.next_version(tags, "major") == "1.0.0"
    assert release.next_version([], "minor") == "0.1.0"
    with pytest.raises(ValueError):
        release.next_version(tags, "dry run")


def test_notes_are_the_unreleased_section_with_absolute_links():
    out = release.notes(CHANGELOG, "0.7.0")
    assert out == ("- **New:** see [the docs](https://github.com/Chatixia-AI/agents-chronicle/blob/v0.7.0/docs/devices.md#people)"
                   " and [PyPI](https://pypi.org/) or [below](#x).")
    assert release.unreleased("# Changelog\n\n## 0.6.1 (2026-10-02)\n\n- Older.\n") == ""
    assert release.unreleased("## Unreleased\n\n## 0.6.1\n- Older.\n") == ""


def test_date_renames_the_unreleased_heading():
    out = release.date(CHANGELOG, "0.7.0", "2026-10-05")
    assert "## 0.7.0 (2026-10-05)\n\n- **New:**" in out and "Unreleased" not in out
    with pytest.raises(ValueError):
        release.date(out, "0.7.1", "2026-10-06")


def test_not_ready_until_the_last_changelog_pull_request_is_merged():
    assert release.not_ready(CHANGELOG, ["v0.6.1"]) is None
    # v0.7.0 is out but its changelog pull request is not merged: its lines are still under Unreleased
    assert "merge the changelog pull request for 0.7.0" in release.not_ready(CHANGELOG, ["v0.6.1", "v0.7.0"])
    dated = release.date(CHANGELOG, "0.7.0", "2026-10-05")
    assert "nothing under '## Unreleased'" in release.not_ready(dated, ["v0.7.0"])
    assert release.not_ready(dated.replace("## 0.7.0", "## Unreleased\n\n- Next.\n\n## 0.7.0"), ["v0.7.0"]) is None
    assert release.not_ready(CHANGELOG, []) is None  # the first release


def test_a_change_to_what_ships_needs_a_new_unreleased_line():
    dated = release.date(CHANGELOG, "0.7.0", "2026-10-05")  # just released: no Unreleased section
    added = dated.replace("## 0.7.0", "## Unreleased\n\n- **Newer:** a dot.\n\n## 0.7.0")
    code = ["src/chronicle/web/app.js", "tests/test_web.py"]
    assert release.missing_entry(dated, added, code) is None
    assert release.missing_entry(CHANGELOG, CHANGELOG.replace("- **New:**", "- **Newer:** a dot.\n- **New:**"), code) is None
    why = release.missing_entry(dated, dated, code)
    assert "src/chronicle/web/app.js" in why and "tests/" not in why and "no-changelog" in why
    assert release.missing_entry(CHANGELOG, CHANGELOG, ["docker/Dockerfile"])  # lines already there don't count
    assert release.missing_entry(dated, dated, ["README.md", "docs/hub.md", ".github/workflows/ci.yml", "uv.lock"]) is None
    many = [f"src/chronicle/m{i}.py" for i in range(5)]
    assert "and 2 more" in release.missing_entry(dated, dated, many)
