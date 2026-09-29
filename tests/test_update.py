"""The dashboard's Update button: install detection, update checks and the update command."""

import io
import json
import os
import time

import pytest

from chronicle import __version__, update


@pytest.fixture
def method(monkeypatch):
    """Pretend Chronicle was installed a given way; returns a setter."""
    monkeypatch.setattr(update, "_method", {})
    monkeypatch.setattr(update, "_remote", {})

    def set_method(**m):
        update._method.clear()
        monkeypatch.setattr(update, "_install_method", lambda: {"label": m.get("kind"), "command": None, **m})

    return set_method


def test_version_order():
    assert update._vkey("0.1.10") > update._vkey("0.1.9") > update._vkey("0.1") > update._vkey(None)
    assert update._vkey("0.2.0rc1") == (0, 2, 0)


def test_pypi_install_checks_only_when_asked(method, monkeypatch):
    method(kind="uv", command=["uv", "tool", "upgrade", "agents-chronicle"])
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return io.BytesIO(json.dumps({"info": {"version": "99.0.0"}}).encode())

    monkeypatch.setattr(update, "urlopen", fake_urlopen)
    info = update.check()
    assert not calls and not info["available"] and info["checked_at"] is None
    assert update.available_version() is None  # the status bar poll never goes online

    info = update.check(remote=True)
    assert calls == [update.PYPI_JSON]
    assert info["available"] and info["latest"] == "99.0.0" and info["can_update"]
    assert info["command"] == "uv tool upgrade agents-chronicle"
    assert update.available_version() == "99.0.0"  # remembered from the check
    assert update.available() == {"to": "99.0.0", "key": "99.0.0"}
    assert info["notes_url"].endswith("/releases/tag/v99.0.0")
    assert len(calls) == 1


def test_pypi_unreachable_is_reported(method, monkeypatch):
    method(kind="pipx", command=["pipx", "upgrade", "agents-chronicle"])

    def offline(req, timeout):
        raise OSError("no network")

    monkeypatch.setattr(update, "urlopen", offline)
    info = update.check(remote=True)
    assert not info["available"] and "Could not reach PyPI" in info["error"]


def test_checkout_install_compares_file_times(method, tmp_path):
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "agents-chronicle"\nversion = "{__version__}"\n')
    (tmp_path / "src" / "chronicle").mkdir(parents=True)
    (tmp_path / "src" / "chronicle" / "server.py").write_text("")
    installed = time.time() + 60
    method(kind="uv", source=str(tmp_path), local=True, installed_at=installed, command=["uv", "tool", "upgrade", "--reinstall", "x"])
    info = update.check()
    assert not info["available"] and info["latest"] == __version__

    os.utime(tmp_path / "src" / "chronicle" / "server.py", (installed + 5, installed + 5))
    info = update.check()
    assert info["available"] and info["can_update"]
    assert update.available_version() == "build"  # same version number, newer files
    assert "changes" not in info  # the status bar's poll does not list them
    info = update.check(detail=True)
    assert info["changes"]["files"] == ["src/chronicle/server.py"] and info["changes"]["commits"] == []


def test_checkout_notification_key_follows_commits(method, tmp_path):
    """Editing files keeps one notification; a new commit brings it back."""
    import subprocess

    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "agents-chronicle"\nversion = "{__version__}"\n')
    git = ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*git, "init", "-q"], check=True)
    installed = time.time() - 60
    method(kind="uv", source=str(tmp_path), local=True, installed_at=installed, command=["uv"])
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "First change"], check=True)
    first = update.available()
    assert first["to"] == "build" and first["key"].startswith("build:")
    info = update.check(detail=True)
    assert [c["subject"] for c in info["changes"]["commits"]] == ["First change"]

    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "agents-chronicle"\nversion = "{__version__}"\n# edit\n')
    assert update.available()["key"] == first["key"]
    subprocess.run([*git, "commit", "-qam", "Second change"], check=True)
    assert update.available()["key"] != first["key"]


def test_app_and_source_installs_do_not_run_commands(method, monkeypatch):
    method(kind="app")
    monkeypatch.setattr(update, "urlopen", lambda req, timeout: io.BytesIO(b'{"info": {"version": "99.0.0"}}'))
    info = update.check(remote=True)
    assert info["available"] and not info["can_update"] and info["releases_url"].endswith("/releases/latest")
    with pytest.raises(RuntimeError, match="cannot update itself"):
        update.run_update(lambda m: None)

    method(kind="source")
    assert update.check(remote=True)["note"].startswith("Running from a source checkout")


def test_pypi_check_is_kept_in_the_database(method, env, monkeypatch):
    """The last answer outlives a restart (the in-memory copy is gone; the database still has it)."""
    from chronicle.db import connect

    method(kind="uv", command=["uv", "tool", "upgrade", "agents-chronicle"])
    monkeypatch.setattr(update, "urlopen", lambda req, timeout: io.BytesIO(b'{"info": {"version": "99.0.0"}}'))
    conn = connect(env["cfg"].db_path)
    update.check(remote=True)
    update.remember(conn)
    update._remote.clear()  # a restart
    assert update.available_version() is None
    update.recall(conn)
    assert update.available_version() == "99.0.0"


def test_daily_check_is_opt_in_and_runs_once_a_day(method, env, monkeypatch):
    from chronicle.server import App

    method(kind="uv", command=["uv", "tool", "upgrade", "agents-chronicle"])
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return io.BytesIO(b'{"info": {"version": "99.0.0"}}')

    monkeypatch.setattr(update, "urlopen", fake_urlopen)
    app = App(env["cfg"])
    assert app.status_small()["update"] is None and not calls  # off by default: never online on its own

    info = app.action_check_daily(True)
    assert info["check_daily"] and "check_daily = true" in env["cfg"].config_path.read_text()
    for _ in range(50):  # the first check runs in the background
        if not app._update_check.locked() and calls:
            break
        time.sleep(0.05)
    assert calls == [update.PYPI_JSON]
    assert app.status_small()["update"]["to"] == "99.0.0"
    assert len(calls) == 1  # the next one is due a day later
    assert update.check_due(now=time.time() + update.DAY + 1)

    assert not app.action_check_daily(False)["check_daily"]


def test_checkouts_never_check_pypi_daily(method, tmp_path):
    method(kind="uv", source=str(tmp_path), local=True, installed_at=time.time(), command=["uv"])
    assert not update.check_due()
