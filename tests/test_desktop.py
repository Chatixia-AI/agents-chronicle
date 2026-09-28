"""The pieces Chronicle.app relies on that run without a GUI: the shim, frozen self-invocation, the server port."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import urllib.request

import pytest


@pytest.fixture()
def frozen(env, monkeypatch):
    """Pretend to run inside Chronicle.app: sys.executable is the bundled binary (here a script echoing its args)."""
    exe = env["tmp"] / "Chronicle.app" / "Contents" / "MacOS" / "Chronicle"
    exe.parent.mkdir(parents=True)
    exe.write_text('#!/bin/sh\necho "ran:$*"\n')
    exe.chmod(0o755)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe


def test_frozen_executable_is_a_shim_that_runs_the_app(env, frozen):
    from chronicle.install import executable, shim_path

    exe = executable()
    assert exe == str(shim_path()) == str(env["home"] / "bin" / "chronicle")
    out = subprocess.run([exe, "hook", "session-end"], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "ran:hook session-end"


def test_shim_is_rewritten_only_when_the_app_moves(env, frozen, monkeypatch):
    from chronicle.install import write_shim

    shim = write_shim(str(frozen))
    mtime = shim.stat().st_mtime_ns
    assert write_shim(str(frozen)).stat().st_mtime_ns == mtime
    moved = env["tmp"] / "Applications" / "Chronicle"
    write_shim(str(moved))
    assert str(moved) in shim.read_text()


def test_frozen_hooks_point_at_the_shim(env, frozen):
    from chronicle.install import executable, install_hooks, settings_path

    install_hooks(env["cfg"], executable(), inject=False)
    settings = json.loads(settings_path(env["cfg"]).read_text())
    command = settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"]
    assert command == f"{env['home'] / 'bin' / 'chronicle'} hook session-end"


def test_self_command(monkeypatch):
    from chronicle.hooks import self_command

    assert self_command() == [sys.executable, "-m", "chronicle"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert self_command() == [sys.executable]


def test_make_server_falls_back_to_a_free_port(env):
    from chronicle.server import make_server

    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        with pytest.raises(OSError):
            make_server(env["cfg"], port=port)
        httpd = make_server(env["cfg"], port=port, any_port=True)
    bound = httpd.server_address[1]
    assert bound != port
    import threading

    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{bound}/api/status", timeout=5) as resp:
            assert "version" in json.loads(resp.read())  # the Host check accepts the fallback port
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_in_temporary_location():
    from chronicle.desktop import in_temporary_location

    assert in_temporary_location("/Volumes/Chronicle/Chronicle.app/Contents/MacOS/Chronicle")
    assert in_temporary_location("/private/var/folders/x/AppTranslocation/ABC/d/Chronicle.app/Contents/MacOS/Chronicle")
    assert not in_temporary_location("/Applications/Chronicle.app/Contents/MacOS/Chronicle")


def test_version_comes_from_the_package_metadata():
    from importlib.metadata import version

    import chronicle

    assert chronicle.__version__ == version("agents-chronicle")
