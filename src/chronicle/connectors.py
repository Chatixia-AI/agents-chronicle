"""Sources ("connectors"): which coding agents Chronicle records, and how each one is wired up."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import time
import tomllib
from pathlib import Path

from .config import Config, set_config_value

_VERSION_CACHE: dict[str, tuple[float, str | None]] = {}


def _version(binary: str | None) -> str | None:
    if not binary:
        return None
    hit = _VERSION_CACHE.get(binary)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=10,
                             env={**os.environ, "CHRONICLE_INTERNAL": "1"}).stdout.strip().splitlines()
        version = out[0] if out else None
    except (OSError, subprocess.SubprocessError):
        version = None
    _VERSION_CACHE[binary] = (time.time(), version)
    return version


def _tilde(p: Path | str) -> str:
    s = str(p)
    home = str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


def _recorded(conn: sqlite3.Connection, where: str, params=()) -> dict:
    r = conn.execute(f"SELECT COUNT(*), MAX(started_at), SUM(analysis_status = 'done') FROM sessions WHERE {where}", params).fetchone()
    return {"sessions": r[0] or 0, "last_session": r[1], "analyzed": r[2] or 0}


# ------------------------------------------------------------------ Claude Code
def claude_status(cfg: Config, conn: sqlite3.Connection) -> dict:
    from .install import LAUNCHD_LABEL, hooks_installed, launchd_status, mcp_registered

    binary = cfg.claude_bin()
    dirs = cfg.claude_dirs
    default_dir = Path("~/.claude").expanduser()
    scan_dirs = dirs or [default_dir]
    on_disk = sum(len(list(d.glob("projects/*/*.jsonl"))) for d in scan_dirs if (d / "projects").is_dir())
    hooks = hooks_installed(cfg)
    rec = _recorded(conn, "agent = 'claude' AND source = 'transcript'")
    recovered = _recorded(conn, "agent = 'claude' AND source IN ('history', 'codex-import')")
    connected = bool(dirs)
    sync = launchd_status(LAUNCHD_LABEL)
    return {
        "name": "claude",
        "label": "Claude Code",
        "vendor": "Anthropic",
        "detected": bool(binary) or default_dir.is_dir(),
        "connected": connected,
        "version": _version(binary),
        "binary": binary,
        "dirs": [_tilde(d) for d in scan_dirs],
        "on_disk": on_disk,
        "recorded": rec,
        "recovered": recovered["sessions"],
        "recording": ("SessionEnd hook + background sync every 15 min" if hooks.get("SessionEnd") else "background sync every 15 min")
        if connected else "not recording",
        "checks": [
            {"label": "Transcripts", "ok": on_disk > 0, "detail": f"{', '.join(_tilde(d) + '/projects' for d in scan_dirs)} · {on_disk} on disk"},
            {"label": "Recording", "ok": connected, "detail": "scanned every sync" if connected else "not scanned (disconnected)"},
            {"label": "SessionEnd hook", "ok": bool(hooks.get("SessionEnd")), "detail": "archives and analyzes each session as it ends"},
            {"label": "MCP server in Claude Code", "ok": mcp_registered(), "detail": "Claude can search your sessions and knowledge"},
            {"label": "Knowledge injection", "ok": bool(hooks.get("SessionStart")), "optional": True,
             "detail": "SessionStart hook adds the project's knowledge base to new sessions"},
            {"label": "Background sync", "ok": bool(sync.get("loaded")), "detail": "launchd, every 15 minutes"},
        ],
        "notes": [f"{recovered['sessions']} older sessions recovered (prompt history / Codex imports)"] if recovered["sessions"] else [],
    }


def connect_claude(cfg: Config, exe: str) -> list[str]:
    from .install import install_hooks, install_mcp

    actions = []
    if not cfg.claude_dirs:
        set_config_value(cfg, "sources", "claude_dirs", '["~/.claude"]')
        actions.append("recording ~/.claude")
    actions += install_hooks(cfg, exe, inject=cfg.inject_session_start)
    actions += install_mcp(cfg, exe)
    return actions


def disconnect_claude(cfg: Config) -> list[str]:
    from .install import uninstall_hooks, uninstall_mcp

    set_config_value(cfg, "sources", "claude_dirs", "[]")
    return ["stopped recording Claude Code (recorded sessions are kept)"] + uninstall_hooks(cfg) + uninstall_mcp(cfg)


# ------------------------------------------------------------------ Codex
def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def codex_mcp_registered(home: Path | None = None) -> bool:
    try:
        data = tomllib.loads(((home or codex_home()) / "config.toml").read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return "chronicle" in (data.get("mcp_servers") or {})


def _codex_notify(home: Path) -> list | None:
    try:
        return tomllib.loads((home / "config.toml").read_text()).get("notify")
    except (OSError, tomllib.TOMLDecodeError):
        return None


def codex_status(cfg: Config, conn: sqlite3.Connection) -> dict:
    from .codex_parser import load_imports, rollout_files

    binary = cfg.codex_bin()
    home = cfg.codex_dirs[0] if cfg.codex_dirs else codex_home()
    files = rollout_files(home)
    imports = load_imports(home)
    connected = bool(cfg.codex_dirs)
    rec = _recorded(conn, "agent = 'codex' AND source != 'codex-cloud'")
    recovered = _recorded(conn, "source = 'codex-import'")
    notify = _codex_notify(home)
    notify_owner = Path(notify[0]).name if isinstance(notify, list) and notify else None
    mcp = codex_mcp_registered(home)
    return {
        "name": "codex",
        "label": "Codex",
        "vendor": "OpenAI",
        "detected": bool(binary) or (home / "sessions").is_dir(),
        "connected": connected,
        "version": _version(binary),
        "binary": binary,
        "dirs": [_tilde(home)],
        "on_disk": len(files),
        "recorded": rec,
        "recovered": recovered["sessions"],
        "imports": len(imports),
        "recording": "background sync every 15 min" if connected else "not recording",
        "checks": [
            {"label": "Rollouts", "ok": bool(files), "detail": f"{_tilde(home)}/sessions · {len(files)} on disk"},
            {"label": "Recording", "ok": connected, "detail": "scanned every sync" if connected else "not scanned (connect to start)"},
            {"label": "Session-end hook", "ok": None, "optional": True,
             "detail": (f"not available: Codex allows one notify program and it is used by {notify_owner}; sessions are picked up by the 15-minute sync"
                        if notify_owner else "Codex has no session-end hook; sessions are picked up by the 15-minute sync")},
            {"label": "MCP server in Codex", "ok": mcp, "detail": "Codex can search your sessions and knowledge (Claude's too)"},
            {"label": "Claude sessions imported by Codex", "ok": None, "optional": True,
             "detail": f"{len(imports)} in Codex's import registry; {recovered['sessions']} recovered into the vault"
                       + (" (the rest are duplicates of transcripts already recorded)" if imports else "")},
        ],
        "notes": [],
    }


def connect_codex(cfg: Config, exe: str) -> list[str]:
    home = codex_home()
    actions = []
    if not cfg.codex_dirs:
        set_config_value(cfg, "sources", "codex_dirs", f'["{_tilde(home)}"]')
        actions.append(f"recording {_tilde(home)}")
    binary = cfg.codex_bin()
    if not binary:
        return actions + ["MCP registration skipped: codex CLI not found"]
    if not codex_mcp_registered(home):
        cmd = [binary, "mcp", "add", "chronicle", "--", *shlex.split(exe), "mcp"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        actions.append("registered MCP server 'chronicle' in Codex" if proc.returncode == 0
                       else f"Codex MCP registration failed: {(proc.stderr or proc.stdout).strip()[:300]}")
    return actions


def disconnect_codex(cfg: Config) -> list[str]:
    set_config_value(cfg, "sources", "codex_dirs", "[]")
    actions = ["stopped recording Codex (recorded sessions are kept)"]
    binary = cfg.codex_bin()
    if binary and codex_mcp_registered():
        proc = subprocess.run([binary, "mcp", "remove", "chronicle"], capture_output=True, text=True, timeout=60)
        actions.append("removed MCP server 'chronicle' from Codex" if proc.returncode == 0
                       else f"Codex MCP removal failed: {(proc.stderr or proc.stdout).strip()[:200]}")
    return actions


# ------------------------------------------------------------------ Codex Cloud
def codex_cloud_status(cfg: Config, conn: sqlite3.Connection) -> dict:
    from .codex_cloud import load_status

    binary = cfg.codex_bin()
    connected = cfg.codex_cloud
    last = load_status(conn)
    rec = _recorded(conn, "source = 'codex-cloud'")
    checked = time.strftime("%b %d %H:%M", time.localtime(last["checked_at"])) if last.get("checked_at") else None
    listing = (f"{last.get('tasks', 0)} tasks at the last sync ({checked})" if last.get("ok")
               else f"failed at the last sync ({checked}): {last.get('error')}" if checked else "not listed yet")
    return {
        "name": "codex-cloud",
        "agent": "codex",
        "label": "Codex Cloud",
        "vendor": "OpenAI",
        "detected": bool(binary),
        "connected": connected,
        "version": _version(binary),
        "binary": binary,
        "dirs": [],
        "on_disk": last.get("tasks", 0) if last.get("ok") else 0,
        "on_disk_label": "in the cloud",
        "recorded": rec,
        "recovered": 0,
        "recording": "task list and diffs every sync, through the codex CLI" if connected else "not recording",
        "checks": [
            {"label": "Codex CLI", "ok": bool(binary), "detail": "lists tasks with your Codex login (`codex login`)" if binary
             else "not found: install Codex and run `codex login`"},
            {"label": "Recording", "ok": connected, "detail": "checked every sync" if connected else "not checked (connect to start)"},
            {"label": "Task list", "ok": bool(last.get("ok")) if checked else None, "optional": not connected, "detail": listing},
            {"label": "Conversation", "ok": None, "optional": True,
             "detail": "not available from the CLI: each task is recorded with its title, repository, changed files and diff"},
        ],
        "notes": [],
    }


def connect_codex_cloud(cfg: Config, exe: str) -> list[str]:
    set_config_value(cfg, "sources", "codex_cloud", "true")
    actions = ["recording Codex Cloud tasks"]
    if not cfg.codex_bin():
        actions.append("codex CLI not found: install Codex and run `codex login`")
    return actions


def disconnect_codex_cloud(cfg: Config) -> list[str]:
    set_config_value(cfg, "sources", "codex_cloud", "false")
    return ["stopped recording Codex Cloud (recorded tasks are kept)"]


# ------------------------------------------------------------------ MCP entries in other tools' JSON configs
def _mcp_json_has(path: Path, key: str) -> bool:
    try:
        return "chronicle" in (json.loads(path.read_text()).get(key) or {})
    except (OSError, ValueError, AttributeError):
        return False


def _mcp_json_set(cfg: Config, path: Path, key: str, entry: dict | None, label: str) -> str:
    """Add (entry) or remove (None) the 'chronicle' server in a JSON MCP config, keeping everything else.
    The file is backed up first; a file that is not plain JSON (comments) is left alone."""
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except (OSError, ValueError):
        return f"{label}: {_tilde(path)} is not plain JSON; add the 'chronicle' MCP server by hand"
    if not isinstance(data, dict):
        return f"{label}: unexpected {_tilde(path)} format; left unchanged"
    servers = data.setdefault(key, {})
    if entry is None:
        if "chronicle" not in servers:
            return f"{label}: no chronicle MCP server to remove"
        servers.pop("chronicle")
    else:
        if servers.get("chronicle") == entry:
            return f"{label}: chronicle MCP server already registered"
        servers["chronicle"] = entry
    if path.exists():
        backup = cfg.home / "backups" / f"{path.name}.{int(time.time())}.{re.sub(r'[^a-z]+', '-', label.lower())}.bak"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return f"{label}: {'removed' if entry is None else 'registered'} MCP server 'chronicle' ({_tilde(path)})"


def _split_exe(exe: str) -> tuple[str, list[str]]:
    parts = shlex.split(exe)
    return parts[0], [*parts[1:], "mcp"]


# ------------------------------------------------------------------ GitHub Copilot
def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME", "~/.copilot")).expanduser()


def vscode_user_dirs() -> list[Path]:
    base = Path("~/Library/Application Support").expanduser()
    return [d for d in (base / "Code" / "User", base / "Code - Insiders" / "User") if d.is_dir()]


def _copilot_extension_version() -> str | None:
    exts = sorted(Path("~/.vscode/extensions").expanduser().glob("github.copilot-chat-*"))
    return exts[-1].name.removeprefix("github.copilot-chat-") if exts else None


def copilot_status(cfg: Config, conn: sqlite3.Connection) -> dict:
    from .copilot_parser import agent_session_dirs, chat_files

    home = next((d for d in cfg.copilot_dirs if (d / "session-state").is_dir()), copilot_home())
    users = [d for d in cfg.copilot_dirs if (d / "workspaceStorage").is_dir()] or vscode_user_dirs()
    agent_sessions = agent_session_dirs(home)
    chats = [f for u in users for f in chat_files(u)]
    connected = bool(cfg.copilot_dirs)
    binary = shutil.which("copilot")
    ext = _copilot_extension_version()
    rec = _recorded(conn, "agent = 'copilot'")
    mcp_vscode = any(_mcp_json_has(u / "mcp.json", "servers") for u in users)
    mcp_cli = _mcp_json_has(home / "mcp-config.json", "mcpServers")
    return {
        "name": "copilot",
        "label": "GitHub Copilot",
        "vendor": "GitHub",
        "detected": home.is_dir() or bool(ext) or bool(binary),
        "connected": connected,
        "version": ext and f"Copilot Chat {ext}",
        "binary": binary,
        "dirs": [_tilde(home), *(_tilde(u) for u in users)],
        "on_disk": len(agent_sessions) + len(chats),
        "recorded": rec,
        "recovered": 0,
        "recording": "background sync every 15 min" if connected else "not recording",
        "checks": [
            {"label": "Copilot agent sessions", "ok": bool(agent_sessions),
             "detail": f"{_tilde(home)}/session-state · {len(agent_sessions)} (Copilot CLI and VS Code agent host)"},
            {"label": "Copilot Chat in VS Code", "ok": bool(chats),
             "detail": f"{len(chats)} chat logs in VS Code workspace storage (empty chat panels are skipped)"},
            {"label": "Recording", "ok": connected, "detail": "scanned every sync" if connected else "not scanned (connect to start)"},
            {"label": "MCP server in VS Code", "ok": mcp_vscode, "detail": "Copilot Chat can search your sessions and knowledge"},
            {"label": "MCP server in Copilot CLI", "ok": mcp_cli, "optional": True, "detail": f"{_tilde(home)}/mcp-config.json"},
            {"label": "Session-end hook", "ok": None, "optional": True,
             "detail": "not used: sessions are picked up by the 15-minute sync"},
        ],
        "notes": ["Copilot is billed per seat; costs shown are API list-price estimates where token splits are known"],
    }


def connect_copilot(cfg: Config, exe: str) -> list[str]:
    actions = []
    home = copilot_home()
    dirs = [d for d in (home, *vscode_user_dirs()) if d.is_dir()]
    if not cfg.copilot_dirs and dirs:
        set_config_value(cfg, "sources", "copilot_dirs", json.dumps([_tilde(d) for d in dirs], ensure_ascii=False))
        actions.append("recording " + ", ".join(_tilde(d) for d in dirs))
    command, args = _split_exe(exe)
    for u in vscode_user_dirs():
        actions.append(_mcp_json_set(cfg, u / "mcp.json", "servers", {"type": "stdio", "command": command, "args": args}, "VS Code"))
    if home.is_dir():
        actions.append(_mcp_json_set(cfg, home / "mcp-config.json", "mcpServers",
                                     {"type": "local", "command": command, "args": args, "tools": ["*"]}, "Copilot CLI"))
    return actions


def disconnect_copilot(cfg: Config) -> list[str]:
    set_config_value(cfg, "sources", "copilot_dirs", "[]")
    actions = ["stopped recording GitHub Copilot (recorded sessions are kept)"]
    for u in vscode_user_dirs():
        if _mcp_json_has(u / "mcp.json", "servers"):
            actions.append(_mcp_json_set(cfg, u / "mcp.json", "servers", None, "VS Code"))
    if _mcp_json_has(copilot_home() / "mcp-config.json", "mcpServers"):
        actions.append(_mcp_json_set(cfg, copilot_home() / "mcp-config.json", "mcpServers", None, "Copilot CLI"))
    return actions


# ------------------------------------------------------------------ IBM Bob
def bob_home() -> Path:
    return Path(os.environ.get("BOB_HOME", "~/.bob")).expanduser()


def bob_status(cfg: Config, conn: sqlite3.Connection) -> dict:
    from .bob_parser import bob_db, load_tasks

    home = cfg.bob_dirs[0] if cfg.bob_dirs else bob_home()
    tasks = load_tasks(home)
    with_prompt = sum(1 for t in tasks if t["messages"])
    connected = bool(cfg.bob_dirs)
    app = next((a for a in ("/Applications/IBM Bob.app", "/Applications/IBM Bob - Insiders.app") if Path(a).exists()), None)
    mcp = _mcp_json_has(home / "settings" / "mcp_settings.json", "mcpServers")
    return {
        "name": "bob",
        "label": "IBM Bob",
        "vendor": "IBM",
        "detected": home.is_dir() or bool(app),
        "connected": connected,
        "version": None,
        "binary": app,
        "dirs": [_tilde(home)],
        "on_disk": with_prompt,
        "recorded": _recorded(conn, "agent = 'bob'"),
        "recovered": 0,
        "recording": "background sync every 15 min" if connected else "not recording",
        "checks": [
            {"label": "Task database", "ok": bob_db(home).exists(),
             "detail": f"{_tilde(bob_db(home))} · {len(tasks)} tasks, {with_prompt} with messages"},
            {"label": "Recording", "ok": connected, "detail": "scanned every sync" if connected else "not scanned (connect to start)"},
            {"label": "MCP server in Bob", "ok": mcp, "detail": f"{_tilde(home)}/settings/mcp_settings.json"},
            {"label": "IDE chat history", "ok": None, "optional": True,
             "detail": "Bob IDE keeps no conversation files on this Mac; only tasks in its task database are recorded"},
        ],
        "notes": [],
    }


def connect_bob(cfg: Config, exe: str) -> list[str]:
    actions = []
    home = bob_home()
    if not cfg.bob_dirs:
        set_config_value(cfg, "sources", "bob_dirs", f'["{_tilde(home)}"]')
        actions.append(f"recording {_tilde(home)}")
    if home.is_dir():
        command, args = _split_exe(exe)
        actions.append(_mcp_json_set(cfg, home / "settings" / "mcp_settings.json", "mcpServers",
                                     {"command": command, "args": args, "disabled": False, "alwaysAllow": []}, "IBM Bob"))
    return actions


def disconnect_bob(cfg: Config) -> list[str]:
    set_config_value(cfg, "sources", "bob_dirs", "[]")
    actions = ["stopped recording IBM Bob (recorded sessions are kept)"]
    path = bob_home() / "settings" / "mcp_settings.json"
    if _mcp_json_has(path, "mcpServers"):
        actions.append(_mcp_json_set(cfg, path, "mcpServers", None, "IBM Bob"))
    return actions


# ------------------------------------------------------------------ MCP-only clients
# Tools Chronicle does not record but can give its MCP server to. Each keeps a JSON config with a server map.
APPLICATIONS = Path("/Applications")

MCP_CLIENTS = {
    "claude-desktop": {"label": "Claude Desktop", "vendor": "Anthropic", "app": "Claude.app",
                       "config": "Library/Application Support/Claude/claude_desktop_config.json", "home": "Library/Application Support/Claude",
                       "restart": True},
    "cursor": {"label": "Cursor", "vendor": "Anysphere", "app": "Cursor.app", "config": ".cursor/mcp.json", "home": ".cursor"},
    "windsurf": {"label": "Windsurf", "vendor": "Windsurf", "app": "Windsurf.app",
                 "config": ".codeium/windsurf/mcp_config.json", "home": ".codeium/windsurf"},
    "gemini": {"label": "Gemini CLI", "vendor": "Google", "binary": "gemini", "config": ".gemini/settings.json", "home": ".gemini"},
}


def mcp_client_config(name: str) -> Path:
    return Path.home() / MCP_CLIENTS[name]["config"]


def _mcp_client_detected(name: str) -> bool:
    c = MCP_CLIENTS[name]
    return ((Path.home() / c["home"]).is_dir() or ("app" in c and (APPLICATIONS / c["app"]).exists())
            or ("binary" in c and bool(shutil.which(c["binary"]))))


def mcp_clients_status() -> list[dict]:
    return [{"name": name, "label": c["label"], "vendor": c["vendor"], "detected": _mcp_client_detected(name),
             "registered": _mcp_json_has(mcp_client_config(name), "mcpServers"), "config": _tilde(mcp_client_config(name))}
            for name, c in MCP_CLIENTS.items()]


def mcp_server_entry(exe: str) -> dict:
    command, args = _split_exe(exe)
    return {"command": command, "args": args}


def add_mcp_client(cfg: Config, name: str, exe: str) -> list[str]:
    c = MCP_CLIENTS[name]
    if not _mcp_client_detected(name):
        return [f"{c['label']} not found on this Mac; nothing changed"]
    action = _mcp_json_set(cfg, mcp_client_config(name), "mcpServers", mcp_server_entry(exe), c["label"])
    return [action + (f"; restart {c['label']} to load it" if c.get("restart") and "registered MCP" in action else "")]


def remove_mcp_client(cfg: Config, name: str) -> list[str]:
    return [_mcp_json_set(cfg, mcp_client_config(name), "mcpServers", None, MCP_CLIENTS[name]["label"])]


# ------------------------------------------------------------------ registry
CONNECTORS = {
    "claude": (claude_status, connect_claude, disconnect_claude),
    "codex": (codex_status, connect_codex, disconnect_codex),
    "codex-cloud": (codex_cloud_status, connect_codex_cloud, disconnect_codex_cloud),
    "copilot": (copilot_status, connect_copilot, disconnect_copilot),
    "bob": (bob_status, connect_bob, disconnect_bob),
}


def all_status(cfg: Config, conn: sqlite3.Connection) -> list[dict]:
    return [status(cfg, conn) for status, _, _ in CONNECTORS.values()]


def connect(cfg: Config, name: str, exe: str) -> list[str]:
    if name in MCP_CLIENTS:
        return add_mcp_client(cfg, name, exe)
    if name not in CONNECTORS:
        raise KeyError(name)
    return CONNECTORS[name][1](cfg, exe)


def disconnect(cfg: Config, name: str) -> list[str]:
    if name in MCP_CLIENTS:
        return remove_mcp_client(cfg, name)
    if name not in CONNECTORS:
        raise KeyError(name)
    return CONNECTORS[name][2](cfg)
