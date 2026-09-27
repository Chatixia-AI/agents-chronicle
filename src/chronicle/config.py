"""Configuration: paths, defaults, and the user-editable config.toml."""

from __future__ import annotations

import fnmatch
import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_TOML = """\
# Claude Chronicle configuration.
# Edit freely; changes apply on the next sync / worker run.

[sources]
# Claude Code config directories to scan (each one contains projects/).
claude_dirs = ["~/.claude"]
# OpenAI Codex homes to scan (sessions, memories, and the Claude sessions Codex Desktop imported).
# Empty = not connected; `chronicle connect codex` (or the dashboard's Sources page) fills it in.
codex_dirs = []
# GitHub Copilot: Copilot agent homes (~/.copilot) and VS Code User directories (Copilot Chat). `chronicle connect copilot`.
copilot_dirs = []
# IBM Bob homes (~/.bob). `chronicle connect bob`.
bob_dirs = []
# Recover prompts of sessions whose transcripts Claude Code already deleted (from history.jsonl).
import_history = true
# Import Claude's auto-memory files (projects/*/memory/*.md) as knowledge.
import_memory = true
# Project paths (glob patterns) to ignore entirely, e.g. ["/Users/me/secret/*"].
exclude_projects = []

[analysis]
# Analyze sessions automatically with headless Claude Code (`claude -p`) once they go idle.
auto = true
model = "sonnet"
effort = "medium"
# Spend cap per `claude -p` call, in API-equivalent USD.
max_budget_usd = 3.0
# A session must be idle this long (or have ended) before it is analyzed.
idle_minutes = 20
# Sessions with fewer human prompts than this are skipped.
min_prompts = 1
# Max session analyses per worker run (the background job runs every 15 minutes).
max_per_run = 6
# Parallel `claude -p` processes.
concurrency = 2
# Also analyze sessions recorded before Chronicle was installed (newest first, within max_per_run).
backfill = true
# Characters of condensed transcript per Claude call; longer sessions are map-reduced.
chunk_chars = 150000
timeout_seconds = 900
# Path to the claude executable (auto-detected when empty).
claude_bin = ""

[synthesis]
# Consolidate per-project knowledge bases once enough new knowledge accumulates.
auto = true
model = "sonnet"
min_new_items = 3

[export]
# Mirror everything into an Obsidian-compatible Markdown vault.
markdown = true
# Where the vault lives (empty = <chronicle home>/notes).
notes_dir = ""

[server]
host = "127.0.0.1"
port = 8765

[inject]
# Inject a short digest of the project's knowledge base into new sessions (SessionStart hook).
session_start = false
max_chars = 3000
"""


def chronicle_home() -> Path:
    return Path(os.environ.get("CHRONICLE_HOME", "~/.claude-chronicle")).expanduser()


@dataclass
class AnalysisConfig:
    auto: bool = True
    model: str = "sonnet"
    effort: str = "medium"
    max_budget_usd: float = 3.0
    idle_minutes: int = 20
    min_prompts: int = 1
    max_per_run: int = 6
    concurrency: int = 2
    backfill: bool = True
    chunk_chars: int = 150_000
    timeout_seconds: int = 900
    claude_bin: str = ""


@dataclass
class SynthesisConfig:
    auto: bool = True
    model: str = "sonnet"
    min_new_items: int = 3


@dataclass
class Config:
    home: Path
    claude_dirs: list[Path] = field(default_factory=list)
    codex_dirs: list[Path] = field(default_factory=list)
    copilot_dirs: list[Path] = field(default_factory=list)
    bob_dirs: list[Path] = field(default_factory=list)
    import_history: bool = True
    import_memory: bool = True
    exclude_projects: list[str] = field(default_factory=list)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    synthesis: SynthesisConfig = field(default_factory=SynthesisConfig)
    export_markdown: bool = True
    notes_dir: Path = Path("~/.claude-chronicle/notes")
    server_host: str = "127.0.0.1"
    server_port: int = 8765
    inject_session_start: bool = False
    inject_max_chars: int = 3000

    # ---- derived paths -------------------------------------------------
    @property
    def db_path(self) -> Path:
        return self.home / "chronicle.db"

    @property
    def archive_dir(self) -> Path:
        return self.home / "archive"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def locks_dir(self) -> Path:
        return self.home / "locks"

    @property
    def config_path(self) -> Path:
        return self.home / "config.toml"

    def ensure_dirs(self) -> None:
        for d in (self.home, self.archive_dir, self.logs_dir, self.locks_dir):
            d.mkdir(parents=True, exist_ok=True)

    def is_excluded(self, project_path: str | None) -> bool:
        if not project_path:
            return False
        return any(fnmatch.fnmatch(project_path, pat) for pat in self.exclude_projects)

    def claude_bin(self) -> str | None:
        if self.analysis.claude_bin:
            return str(Path(self.analysis.claude_bin).expanduser())
        found = shutil.which("claude")
        if found:
            return found
        for candidate in ("~/.local/bin/claude", "~/.claude/local/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
            p = Path(candidate).expanduser()
            if p.exists():
                return str(p)
        return None

    def codex_bin(self) -> str | None:
        found = shutil.which("codex")
        if found:
            return found
        for candidate in ("/opt/homebrew/bin/codex", "/usr/local/bin/codex", "~/.local/bin/codex"):
            p = Path(candidate).expanduser()
            if p.exists():
                return str(p)
        return None


def _section(data: dict, name: str) -> dict:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def _pick(cls, values: dict):
    allowed = cls.__dataclass_fields__.keys()
    return cls(**{k: v for k, v in values.items() if k in allowed})


def load_config(home: Path | None = None, *, create: bool = True) -> Config:
    home = (home or chronicle_home()).expanduser()
    path = home / "config.toml"
    if create and not path.exists():
        home.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG_TOML)
    data: dict = {}
    if path.exists():
        try:
            data = tomllib.loads(path.read_text())
        except tomllib.TOMLDecodeError as exc:  # keep running on a broken edit, loudly
            import logging

            logging.getLogger("chronicle").error("config.toml is invalid (%s); using defaults", exc)
    sources = _section(data, "sources")
    export = _section(data, "export")
    server = _section(data, "server")
    inject = _section(data, "inject")

    env_dirs = os.environ.get("CHRONICLE_CLAUDE_DIRS")
    raw_dirs = env_dirs.split(os.pathsep) if env_dirs else sources.get("claude_dirs", ["~/.claude"])

    cfg = Config(
        home=home,
        claude_dirs=[Path(d).expanduser() for d in raw_dirs],
        codex_dirs=[Path(d).expanduser() for d in sources.get("codex_dirs", [])],
        copilot_dirs=[Path(d).expanduser() for d in sources.get("copilot_dirs", [])],
        bob_dirs=[Path(d).expanduser() for d in sources.get("bob_dirs", [])],
        import_history=bool(sources.get("import_history", True)),
        import_memory=bool(sources.get("import_memory", True)),
        exclude_projects=list(sources.get("exclude_projects", [])),
        analysis=_pick(AnalysisConfig, _section(data, "analysis")),
        synthesis=_pick(SynthesisConfig, _section(data, "synthesis")),
        export_markdown=bool(export.get("markdown", True)),
        notes_dir=Path(export.get("notes_dir") or (home / "notes")).expanduser(),
        server_host=str(server.get("host", "127.0.0.1")),
        server_port=int(server.get("port", 8765)),
        inject_session_start=bool(inject.get("session_start", False)),
        inject_max_chars=int(inject.get("max_chars", 3000)),
    )
    return cfg


def set_config_value(cfg: "Config", section: str, key: str, value: str) -> None:
    """Set `key = value` (value is a TOML literal) inside [section] of config.toml, keeping comments and layout.

    Replaces an existing key (including a multi-line array), inserts into an existing section, or appends the
    section. The result is validated before it is written, so a bad edit never corrupts the file.
    """
    import re

    path = cfg.config_path
    lines = (path.read_text() if path.exists() else DEFAULT_CONFIG_TOML).splitlines()
    header = next((i for i, l in enumerate(lines) if l.strip() == f"[{section}]"), None)
    new_line = f"{key} = {value}"
    if header is None:
        lines += ["", f"[{section}]", new_line]
    else:
        end = next((j for j in range(header + 1, len(lines)) if lines[j].lstrip().startswith("[")), len(lines))
        at = next((j for j in range(header + 1, end) if re.match(rf"^\s*{re.escape(key)}\s*=", lines[j])), None)
        if at is None:
            last = max([j for j in range(header, end) if lines[j].strip()], default=header)
            lines.insert(last + 1, new_line)
        else:
            stop = at
            if "[" in lines[at].split("=", 1)[1] and "]" not in lines[at].split("=", 1)[1]:
                stop = next((j for j in range(at + 1, end) if "]" in lines[j]), at)
            lines[at:stop + 1] = [new_line]
    text = "\n".join(lines).rstrip() + "\n"
    tomllib.loads(text)  # raises before anything is written
    path.write_text(text)
