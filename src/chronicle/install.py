"""Install/uninstall Chronicle into Claude Code (hooks, MCP server) and the background agents: launchd on macOS,
systemd user units on Linux (for a hub that runs on a Linux box)."""

from __future__ import annotations

import json
import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from .config import Config
from .util import utcnow_iso

LAUNCHD_LABEL = "com.claude-chronicle.sync"
UI_LABEL = "com.claude-chronicle.ui"
HOOK_MARKER = " hook "
MCP_NAME = "chronicle"
APP_BUNDLE_ID = "io.github.kayeungadrian-tam.chronicle"


def shim_path() -> Path:
    from .config import chronicle_home

    return chronicle_home() / "bin" / "chronicle"


def write_shim(target: str) -> Path:
    """A stable `chronicle` command that runs the app's bundled executable.

    Hooks and MCP registrations store a command path, and the app's own path changes when it is moved or
    updated, so they point here instead. The app rewrites this on every launch; if the app has moved since,
    the shim looks it up by bundle id with Spotlight.
    """
    path = shim_path()
    text = (
        "#!/bin/sh\n"
        "# Written by Chronicle.app on every launch. Claude Code hooks and MCP servers run this.\n"
        f"exe={shlex.quote(target)}\n"
        '[ -x "$exe" ] || exe="$(mdfind "kMDItemCFBundleIdentifier == \'' + APP_BUNDLE_ID + '\'" | head -n 1)'
        '/Contents/MacOS/Chronicle"\n'
        'exec "$exe" "$@"\n'
    )
    if not path.exists() or path.read_text() != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)
    return path


def executable() -> str:
    """Absolute path of the installed `chronicle` command (falls back to python -m chronicle)."""
    if getattr(sys, "frozen", False):  # inside Chronicle.app
        return str(write_shim(sys.executable))
    found = shutil.which("chronicle")
    if found:  # keep the PATH entry (e.g. ~/.local/bin/chronicle): it survives `uv tool install --force`
        return str(Path(found).absolute())
    argv0 = Path(sys.argv[0])
    if argv0.name == "chronicle" and argv0.exists():
        return str(argv0.resolve())
    return f"{shlex.quote(sys.executable)} -m chronicle"


def _exe_cmd(exe: str, *args: str) -> str:
    base = exe if " -m " in exe else shlex.quote(exe)
    return " ".join([base, *args])


def _is_ours(hook: dict) -> bool:
    cmd = hook.get("command") or ""
    return "chronicle" in cmd and HOOK_MARKER in f" {cmd} "


def settings_path(cfg: Config) -> Path:
    return (cfg.claude_dirs[0] if cfg.claude_dirs else Path("~/.claude").expanduser()) / "settings.json"


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text()
    return json.loads(text) if text.strip() else {}


def _backup(cfg: Config, path: Path) -> Path | None:
    if not path.exists():
        return None
    dest = cfg.home / "backups" / f"{path.name}.{utcnow_iso().replace(':', '')}.bak"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest


def hooks_installed(cfg: Config) -> dict[str, bool]:
    try:
        settings = _load_settings(settings_path(cfg))
    except (OSError, ValueError):
        return {}
    found = {}
    for event, groups in (settings.get("hooks") or {}).items():
        for group in groups or []:
            if any(_is_ours(h) for h in group.get("hooks") or []):
                found[event] = True
    return found


def install_hooks(cfg: Config, exe: str, *, inject: bool, dry_run: bool = False) -> list[str]:
    path = settings_path(cfg)
    settings = _load_settings(path)
    hooks = settings.setdefault("hooks", {})
    wanted = {"SessionEnd": _exe_cmd(exe, "hook", "session-end")}
    if inject:
        wanted["SessionStart"] = _exe_cmd(exe, "hook", "session-start")
    actions = []
    # drop any previous chronicle hooks first so paths stay current
    for event in list(hooks):
        groups = []
        for group in hooks[event] or []:
            kept = [h for h in group.get("hooks") or [] if not _is_ours(h)]
            if kept:
                groups.append({**group, "hooks": kept})
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    for event, command in wanted.items():
        hooks.setdefault(event, []).append({"hooks": [{"type": "command", "command": command, "timeout": 15}]})
        actions.append(f"hook {event}: {command}")
    if not hooks:
        settings.pop("hooks", None)
    new_text = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    if not dry_run and (not path.exists() or path.read_text() != new_text):
        backup = _backup(cfg, path)
        if backup:
            actions.append(f"backed up {path} -> {backup}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text)
    return actions


def uninstall_hooks(cfg: Config) -> list[str]:
    path = settings_path(cfg)
    if not path.exists():
        return []
    settings = _load_settings(path)
    hooks = settings.get("hooks") or {}
    removed = 0
    for event in list(hooks):
        groups = []
        for group in hooks[event] or []:
            kept = [h for h in group.get("hooks") or [] if not _is_ours(h)]
            removed += len(group.get("hooks") or []) - len(kept)
            if kept:
                groups.append({**group, "hooks": kept})
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    if removed:
        _backup(cfg, path)
        path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    return [f"removed {removed} hook(s) from {path}"] if removed else []


# ------------------------------------------------------------------ systemd (Linux)
SYSTEMD_UNITS = {LAUNCHD_LABEL: ("chronicle-sync.timer", "chronicle-sync.service"), UI_LABEL: ("chronicle-ui.service",)}


def uses_systemd() -> bool:
    return platform.system() == "Linux" and shutil.which("systemctl") is not None


def background_supported() -> bool:
    """Whether `chronicle install` can keep the sync and dashboard running from login here."""
    return platform.system() == "Darwin" or uses_systemd()


def systemd_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser() / "systemd" / "user"


def _sd_quote(arg: str) -> str:
    arg = arg.replace("%", "%%")
    if not arg or any(c in arg for c in ' \t"\'\\;$'):
        return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return arg


def systemd_units(cfg: Config, exe: str, *, interval: int = 900) -> dict[str, str]:
    """The unit files for the background sync (a timer) and the always-on dashboard."""
    cmd = shlex.split(exe)
    env = "\n".join(f"Environment={_sd_quote(f'{k}={v}')}" for k, v in _agent_env(cfg).items())
    run = lambda *args: " ".join(_sd_quote(a) for a in [*cmd, *args])  # noqa: E731
    return {
        "chronicle-sync.service": (
            "[Unit]\nDescription=Chronicle: archive, ingest and analyze coding-agent sessions\n\n"
            f"[Service]\nType=oneshot\nExecStart={run('sync', '--work', '--quiet')}\n{env}\nNice=10\n"
            "IOSchedulingClass=idle\n"),
        "chronicle-sync.timer": (
            "[Unit]\nDescription=Chronicle: sync every few minutes\n\n"
            f"[Timer]\nOnBootSec=2min\nOnUnitActiveSec={interval}s\n\n[Install]\nWantedBy=timers.target\n"),
        "chronicle-ui.service": (
            "[Unit]\nDescription=Chronicle dashboard\n\n"
            f"[Service]\nExecStart={run('ui')}\n{env}\nRestart=always\nRestartSec=30\n\n"
            "[Install]\nWantedBy=default.target\n"),
    }


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def _systemd_install(cfg: Config, exe: str, names: tuple[str, ...], enable: str, interval: int) -> str | None:
    units = systemd_units(cfg, exe, interval=interval)
    d = systemd_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name in names:
        (d / name).write_text(units[name])
    _systemctl("daemon-reload")
    proc = _systemctl("enable", "--now", enable)
    if proc.returncode != 0:
        return proc.stderr.strip() or f"exit {proc.returncode}"
    if enable.endswith(".service"):
        _systemctl("restart", enable)  # pick up a changed ExecStart
    return None


def _systemd_status(label: str) -> dict:
    units = SYSTEMD_UNITS[label]
    info = {"installed": (systemd_dir() / units[0]).exists(),
            "loaded": _systemctl("is-active", units[0]).stdout.strip() == "active"}
    show = _systemctl("show", units[-1], "-p", "ExecMainStatus", "-p", "NRestarts").stdout
    for line in show.splitlines():
        key, _, value = line.partition("=")
        if key == "ExecMainStatus" and info["installed"]:
            info["last_exit"] = value
    return info


# ------------------------------------------------------------------ launchd
def plist_path(label: str = LAUNCHD_LABEL) -> Path:
    return Path("~/Library/LaunchAgents").expanduser() / f"{label}.plist"


def _agent_env(cfg: Config) -> dict:
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    claude = cfg.claude_bin()
    for extra in ([str(Path(claude).parent)] if claude else []) + [str(Path(sys.executable).parent), "/usr/bin", "/bin"]:
        if extra not in path_dirs:
            path_dirs.append(extra)
    return {"PATH": os.pathsep.join(p for p in path_dirs if p), "HOME": str(Path.home()), "CHRONICLE_HOME": str(cfg.home)}


def _bootstrap(label: str, plist: dict) -> str | None:
    path = plist_path(label)
    path.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], capture_output=True)
    with open(path, "wb") as fh:
        plistlib.dump(plist, fh)
    proc = subprocess.run(["launchctl", "bootstrap", domain, str(path)], capture_output=True, text=True)
    return None if proc.returncode == 0 else proc.stderr.strip() or f"exit {proc.returncode}"


def install_ui_agent(cfg: Config, exe: str, *, dry_run: bool = False) -> list[str]:
    """Keep the dashboard running at http://127.0.0.1:<port> (restarted by launchd or systemd if it exits)."""
    url = f"http://127.0.0.1:{cfg.server_port}/"
    if uses_systemd():
        if dry_run:
            return [f"systemd user unit {systemd_dir() / 'chronicle-ui.service'} serving {url}"]
        err = _systemd_install(cfg, exe, ("chronicle-ui.service",), "chronicle-ui.service", 900)
        return [f"dashboard agent failed: {err}"] if err else [f"dashboard always available at {url}"]
    if platform.system() != "Darwin":
        return ["dashboard agent skipped (no launchd or systemd); run `chronicle ui` yourself"]
    program = shlex.split(exe) + ["ui"]
    if dry_run:
        return [f"dashboard agent {plist_path(UI_LABEL)} serving {url}"]
    err = _bootstrap(UI_LABEL, {
        "Label": UI_LABEL,
        "ProgramArguments": program,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 30,
        "ProcessType": "Background",
        "EnvironmentVariables": _agent_env(cfg),
        "StandardOutPath": str(cfg.logs_dir / "ui.out.log"),
        "StandardErrorPath": str(cfg.logs_dir / "ui.err.log"),
    })
    return [f"dashboard agent failed: {err}"] if err else [f"dashboard always available at {url}"]


def install_launchd(cfg: Config, exe: str, *, interval: int = 900, dry_run: bool = False) -> list[str]:
    """The background sync every `interval` seconds: a launchd agent on macOS, a systemd user timer on Linux."""
    if uses_systemd():
        if dry_run:
            return [f"systemd user timer {systemd_dir() / 'chronicle-sync.timer'} running sync every {interval}s"]
        err = _systemd_install(cfg, exe, ("chronicle-sync.service", "chronicle-sync.timer"), "chronicle-sync.timer", interval)
        return [f"systemd timer failed: {err}"] if err else [f"systemd timer chronicle-sync.timer runs `chronicle sync --work` every {interval // 60} min"]
    if platform.system() != "Darwin":
        return ["background sync skipped (no launchd or systemd); schedule `chronicle sync --work` with cron instead"]
    program = shlex.split(exe) + ["sync", "--work", "--quiet"]
    plist = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": program,
        "StartInterval": interval,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "EnvironmentVariables": _agent_env(cfg),
        "StandardOutPath": str(cfg.logs_dir / "launchd.out.log"),
        "StandardErrorPath": str(cfg.logs_dir / "launchd.err.log"),
    }
    if dry_run:
        return [f"launchd agent {plist_path()} running {' '.join(program)} every {interval}s"]
    err = _bootstrap(LAUNCHD_LABEL, plist)
    if err:
        return [f"launchd bootstrap failed: {err}"]
    return [f"launchd agent {LAUNCHD_LABEL} runs `{' '.join(program)}` every {interval // 60} min"]


def uninstall_launchd(labels=(LAUNCHD_LABEL, UI_LABEL)) -> list[str]:
    out = []
    if uses_systemd():
        for label in labels:
            units = SYSTEMD_UNITS.get(label, ())
            if not any((systemd_dir() / u).exists() for u in units):
                continue
            _systemctl("disable", "--now", units[0])
            for u in units:
                (systemd_dir() / u).unlink(missing_ok=True)
            out.append(f"removed systemd unit {units[0]}")
        if out:
            _systemctl("daemon-reload")
        return out
    if platform.system() != "Darwin":
        return out
    for label in labels:
        path = plist_path(label)
        if not path.exists():
            continue
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
        path.unlink(missing_ok=True)
        out.append(f"removed launchd agent {label}")
    return out


def launchd_status(label: str = LAUNCHD_LABEL) -> dict:
    if uses_systemd() and label in SYSTEMD_UNITS:
        return _systemd_status(label)
    if platform.system() != "Darwin":
        return {"installed": False}
    proc = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{label}"], capture_output=True, text=True)
    info = {"installed": plist_path(label).exists(), "loaded": proc.returncode == 0}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("last exit code"):
            info["last_exit"] = line.split("=", 1)[-1].strip()
        elif line.startswith("runs ="):
            info["runs"] = line.split("=", 1)[-1].strip()
    return info


def background_status() -> dict:
    """The background sync agent's state, whichever service manager runs it."""
    return launchd_status(LAUNCHD_LABEL)


def agent_path(label: str) -> Path:
    return systemd_dir() / SYSTEMD_UNITS[label][0] if uses_systemd() else plist_path(label)


# ------------------------------------------------------------------ MCP
def _claude_json() -> Path:
    return Path("~/.claude.json").expanduser()


def mcp_registered() -> bool:
    try:
        data = json.loads(_claude_json().read_text())
    except (OSError, ValueError):
        return False
    return MCP_NAME in (data.get("mcpServers") or {})


def install_mcp(cfg: Config, exe: str, *, dry_run: bool = False) -> list[str]:
    claude = cfg.claude_bin()
    if not claude:
        return ["MCP registration skipped: claude CLI not found"]
    args = shlex.split(exe) + ["mcp"]
    cmd = [claude, "mcp", "add", "--scope", "user", "--transport", "stdio", MCP_NAME, "--", *args]
    if dry_run:
        return ["would run: " + " ".join(shlex.quote(c) for c in cmd)]
    subprocess.run([claude, "mcp", "remove", "--scope", "user", MCP_NAME], capture_output=True, text=True)
    proc = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "CHRONICLE_INTERNAL": "1"})
    if proc.returncode != 0:
        return [f"MCP registration failed: {(proc.stderr or proc.stdout).strip()[:300]}"]
    return [f"registered MCP server '{MCP_NAME}' (user scope)"]


def uninstall_mcp(cfg: Config) -> list[str]:
    claude = cfg.claude_bin()
    if not claude or not mcp_registered():
        return []
    proc = subprocess.run([claude, "mcp", "remove", "--scope", "user", MCP_NAME], capture_output=True, text=True)
    return [f"removed MCP server '{MCP_NAME}'"] if proc.returncode == 0 else [f"MCP removal failed: {proc.stderr.strip()[:200]}"]
