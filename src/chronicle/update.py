"""Self-update for the dashboard's Update button: find how Chronicle was installed and upgrade it the same way.

Checking PyPI is the only network call, and it runs only when the user asks (Status › Check for updates).
An install from a local checkout is checked without the network: it is out of date when the checkout's
files changed after the install.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tomllib
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from . import __version__

DIST = "agents-chronicle"
PYPI_JSON = f"https://pypi.org/pypi/{DIST}/json"
RELEASES_URL = "https://github.com/kayeungadrian-tam/agents-chronicle/releases/latest"

# server.serve() sets this: a plain `chronicle ui` (by hand or launchd) can re-exec itself after an update;
# the desktop app serves the dashboard from its own process and is restarted by the user instead.
RESTARTABLE = False
_remote: dict = {}  # the last PyPI check: {"latest": ..., "checked_at": ...} or {"error": ...}
_method: dict = {}  # install_method() is polled with the status bar; it only changes when an update runs


def _vkey(v: str | None) -> tuple:
    """Release numbers of a version ("0.1.10" -> (0, 1, 10)); enough to order Chronicle's own releases."""
    m = re.match(r"\d+(?:\.\d+)*", v or "")
    return tuple(int(n) for n in m.group(0).split(".")) if m else ()


def _which(name: str) -> str | None:
    """Like shutil.which, but also looks where installers put tools: launchd's PATH is only /usr/bin:/bin."""
    home = Path.home()
    found = shutil.which(name)
    for p in [found, home / ".local/bin" / name, home / ".cargo/bin" / name, f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}"]:
        if p and Path(p).is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def install_method() -> dict:
    """How this copy was installed: kind, where from, and the command that upgrades it (None when there is none)."""
    if not _method:
        _method.update(_install_method())
    return _method


def _install_method() -> dict:
    if getattr(sys, "frozen", False):
        return {"kind": "app", "label": "Chronicle.app", "command": None}
    receipt = Path(sys.prefix) / "uv-receipt.toml"
    if receipt.is_file():
        reqs = tomllib.loads(receipt.read_text()).get("tool", {}).get("requirements", [])
        req = next((r for r in reqs if r.get("name") == DIST), {})
        source = req.get("directory") or req.get("path") or req.get("git") or req.get("url")
        uv = _which("uv")
        # a checkout's version rarely changes, so a plain upgrade would keep the old build: --reinstall rebuilds it
        cmd = [uv, "tool", "upgrade", *(["--reinstall"] if source else []), DIST] if uv else None
        return {"kind": "uv", "label": f"uv tool from {source}" if source else "uv tool from PyPI", "source": source,
                "local": bool(req.get("directory") or req.get("path")),
                # installed files carry the install time (the receipt is not rewritten by an upgrade)
                "installed_at": (Path(__file__).parent / "__init__.py").stat().st_mtime,
                "command": cmd}
    try:
        direct = json.loads(distribution(DIST).read_text("direct_url.json") or "null")
    except PackageNotFoundError:
        return {"kind": "source", "label": "source tree (not installed)", "command": None}
    if direct and direct.get("dir_info", {}).get("editable"):
        return {"kind": "source", "label": f"editable checkout {unquote(urlparse(direct['url']).path)}", "command": None}
    if "pipx" in Path(sys.prefix).parts or "pipx" in sys.prefix:
        pipx = _which("pipx")
        return {"kind": "pipx", "label": "pipx", "command": [pipx, "upgrade", DIST] if pipx else None}
    has_pip = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode == 0
    return {"kind": "pip", "label": f"pip in {sys.prefix}",
            "command": [sys.executable, "-m", "pip", "install", "--upgrade", DIST] if has_pip else None}


def _checkout_changed(source: str, since: float) -> bool:
    """True when the checkout has files newer than the install, i.e. reinstalling would change something."""
    root = Path(source).expanduser()
    files = [root / "pyproject.toml", *(p for p in (root / "src").rglob("*") if p.is_file() and "__pycache__" not in p.parts)]
    return any(p.stat().st_mtime > since for p in files if p.exists())


def _checkout_version(source: str) -> str | None:
    try:
        return tomllib.loads((Path(source).expanduser() / "pyproject.toml").read_text())["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return None


def check(remote: bool = False) -> dict:
    """What the Status page shows. remote=True asks PyPI for the latest release; otherwise the last answer is reused."""
    m = install_method()
    info = {"current": __version__, "kind": m["kind"], "method": m["label"], "source": m.get("source"),
            "local": m.get("local", False), "latest": None, "available": False,
            "can_update": m["command"] is not None, "command": shlex.join(m["command"]) if m["command"] else None,
            "restartable": RESTARTABLE, "checked_at": None, "error": None, "releases_url": RELEASES_URL}
    if m["kind"] == "source":
        info["note"] = "Running from a source checkout: git pull to update."
        return info
    if m.get("local"):  # checked locally, no network
        info["latest"] = _checkout_version(m["source"])
        info["available"] = _checkout_changed(m["source"], m["installed_at"])
        info["note"] = None if info["available"] else "Matches the checkout."
        return info
    if m.get("source"):  # git or URL: nothing to compare against, reinstalling fetches it again
        info["note"] = f"Installed from {m['source']}; updating reinstalls from there."
        return info
    if remote:
        try:
            req = Request(PYPI_JSON, headers={"User-Agent": f"chronicle/{__version__}", "Accept": "application/json"})
            with urlopen(req, timeout=8) as r:
                _remote.update(latest=json.load(r)["info"]["version"], checked_at=time.time(), error=None)
        except Exception as exc:  # offline, proxy, PyPI down: shown on the page
            _remote.update(checked_at=time.time(), error=f"Could not reach PyPI ({exc.__class__.__name__})")
    info.update(latest=_remote.get("latest"), checked_at=_remote.get("checked_at"), error=_remote.get("error"))
    info["available"] = bool(info["latest"]) and _vkey(info["latest"]) > _vkey(__version__)
    if m["kind"] == "app":
        info["note"] = "Download the new version and drag it into Applications."
    return info


def available_version() -> str | None:
    """For the status bar: the version to update to, from checks already made (never touches the network)."""
    try:
        info = check()
    except Exception:
        return None
    if not info["available"]:
        return None
    return info["latest"] if _vkey(info["latest"]) > _vkey(__version__) else "build"  # a changed checkout, same version


def run_update(progress) -> str:
    """Upgrade with the install's own tool; returns a line for the UI. Restarts the dashboard when it can."""
    m = install_method()
    if not m["command"]:
        raise RuntimeError(f"Chronicle installed as {m['label']} cannot update itself")
    progress("updating Chronicle…")
    r = subprocess.run(m["command"], capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL)
    out = (r.stdout + r.stderr).strip()
    _method.clear()  # a reinstall rewrites the receipt
    if r.returncode:
        raise RuntimeError(out.splitlines()[-1] if out else f"{m['command'][0]} exited with {r.returncode}")
    new = subprocess.run([sys.executable, "-c", f"import importlib.metadata as m; print(m.version({DIST!r}))"],
                         capture_output=True, text=True).stdout.strip() or "?"
    if RESTARTABLE:
        threading.Timer(3.0, restart).start()  # after the next status poll has seen this job finish
        return f"Updated to Chronicle {new}; the dashboard is restarting"
    return f"Updated to Chronicle {new}; quit and reopen Chronicle to use it"


def restart() -> None:
    """Replace this process with a fresh copy of itself. The pid stays, so a launchd KeepAlive agent is undisturbed;
    the listening socket is not inherited, and open tabs reload themselves when they see the new build."""
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(sys.executable, sys.orig_argv)
