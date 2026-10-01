"""Background worker: analyze idle sessions, synthesize knowledge bases, export Markdown."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import timedelta

from .config import Config
from .db import connect, kv_get, kv_set
from .llm import BudgetExceededError, LLMError, Runner, UsageLimitError, make_runner
from .util import file_lock, to_iso, utcnow

log = logging.getLogger("chronicle.worker")

PAUSE_KEY = "analysis_paused_until"


@dataclass
class WorkReport:
    analyzed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    synthesized: list[str] = field(default_factory=list)
    reviews: list[str] = field(default_factory=list)
    exported: int = 0
    cost_usd: float = 0.0
    paused_until: str | None = None
    note: str | None = None

    def summary(self) -> str:
        parts = [f"{len(self.analyzed)} analyzed", f"{len(self.skipped)} skipped", f"{len(self.failed)} failed",
                 f"{len(self.synthesized)} knowledge bases", f"{len(self.reviews)} reviews", f"{self.exported} notes exported"]
        if self.paused_until:
            parts.append(f"paused until {self.paused_until}")
        if self.note:
            parts.append(self.note)
        return ", ".join(parts)


def pending_sessions(conn, cfg: Config, limit: int) -> list[str]:
    now = utcnow()
    params = {
        "now": to_iso(now),
        "idle": to_iso(now - timedelta(minutes=cfg.analysis.idle_minutes)),
        "min_prompts": cfg.analysis.min_prompts,
        "installed": kv_get(conn, "installed_at") or "0000",
    }
    sql = (
        "SELECT id, project_path FROM sessions WHERE source != 'history' "
        "AND analysis_status IN ('pending', 'stale', 'error') AND analysis_attempts < 4 "
        "AND (analysis_not_before IS NULL OR analysis_not_before <= :now) "
        "AND n_prompts >= :min_prompts AND (ended_flag = 1 OR ended_at <= :idle)"
    )
    if not cfg.analysis.backfill:
        sql += " AND started_at >= :installed"
    sql += " ORDER BY ended_flag DESC, ended_at DESC"
    ids = []
    for sid, project_path in conn.execute(sql, params):
        if cfg.is_excluded(project_path):  # excluded after it was queued: never send it to Claude
            continue
        ids.append(sid)
        if len(ids) >= limit:
            break
    return ids


def count_pending(conn, cfg: Config) -> dict:
    ready = len(pending_sessions(conn, cfg, 100_000))
    waiting = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE source != 'history' AND analysis_status IN ('pending','stale')"
    ).fetchone()[0]
    return {"ready": ready, "queued": waiting}


def run_worker(cfg: Config, *, session_ids: list[str] | None = None, max_analyses: int | None = None,
               analyze: bool = True, synthesize: bool = True, export: bool = True, force: bool = False,
               model: str | None = None, progress=None, wait: bool = False) -> WorkReport:
    report = WorkReport()
    if cfg.is_spoke:  # its sessions go to the hub, which analyzes them; analyzing here would pay twice
        report.note = f"analysis runs on the hub ({cfg.hub_url})"
        return report
    if wait and progress:
        with file_lock(cfg.locks_dir / "worker.lock", blocking=False) as free:
            pass
        if not free:
            progress("waiting for the background worker to finish its current batch…")
    with file_lock(cfg.locks_dir / "worker.lock", blocking=wait, timeout=3600 if wait else None) as got:
        if not got:
            report.note = "another worker is running"
            return report
        conn = connect(cfg.db_path)
        try:
            _run_locked(cfg, conn, report, session_ids=session_ids, max_analyses=max_analyses, analyze=analyze,
                        synthesize=synthesize, export=export, force=force, model=model, progress=progress)
        finally:
            conn.rollback()  # never leave a write transaction (and its lock) behind on any exit path
            conn.close()
    log.info("worker: %s", report.summary())
    return report


def _run_locked(cfg: Config, conn, report: WorkReport, *, session_ids, max_analyses, analyze, synthesize, export,
                force, model, progress) -> None:
    # a crashed worker can leave sessions marked running
    conn.execute("UPDATE sessions SET analysis_status = 'pending' WHERE analysis_status = 'running'")
    conn.commit()
    runner = make_runner(cfg)
    paused = kv_get(conn, PAUSE_KEY)
    if analyze and (cfg.analysis.auto or session_ids or force):
        if paused and paused > to_iso(utcnow()) and not session_ids:
            report.paused_until = paused
        elif not runner.available():
            report.note = f"{runner.label} ({runner.cli.split()[0]}) not found; analysis skipped"
        else:
            ids = session_ids or pending_sessions(conn, cfg, max_analyses or cfg.analysis.max_per_run)
            _analyze_many(cfg, ids, runner, report, model=model, progress=progress)
    if synthesize and (cfg.synthesis.auto or force) and runner.available() and not report.paused_until:
        _synthesize(cfg, conn, runner, report, force=force, progress=progress)
        _glossaries(cfg, conn, runner, report, progress=progress)
        _themes(cfg, report, progress=progress)
        _weekly_review(cfg, conn, runner, report, progress=progress)
    if export and cfg.export_markdown:
        from .export_md import export_markdown

        try:
            report.exported = export_markdown(conn, cfg)
        except Exception:  # export problems must never block analysis
            conn.rollback()
            log.exception("markdown export failed")


def _analyze_many(cfg: Config, ids: list[str], runner: Runner, report: WorkReport, *, model=None, progress=None):
    from .analyze import AnalysisSkipped, analyze_session

    stop = threading.Event()
    lock = threading.Lock()
    finished = 0

    def task(sid: str):
        if stop.is_set():
            return sid, "cancelled", None
        conn = connect(cfg.db_path)
        try:
            if progress:
                progress(f"analyzing {sid[:8]}…" if len(ids) == 1 else f"analyzing sessions: {finished} of {len(ids)} done")
            analyze_session(conn, cfg, sid, runner, model=model)
            cost = conn.execute(
                "SELECT cost_usd FROM analyses WHERE target = ? AND kind = 'session' ORDER BY id DESC LIMIT 1", (sid,)
            ).fetchone()
            return sid, "done", cost[0] if cost else 0.0
        except AnalysisSkipped as exc:
            return sid, "skipped", str(exc)
        except UsageLimitError as exc:
            stop.set()
            until = to_iso(utcnow() + timedelta(hours=1))
            kv_set(conn, PAUSE_KEY, until)
            conn.commit()
            return sid, "paused", f"{exc} (paused until {until})"
        except (LLMError, BudgetExceededError) as exc:
            return sid, "failed", str(exc)
        except Exception as exc:  # keep the batch going
            log.exception("analysis crashed for %s", sid)
            conn.execute("UPDATE sessions SET analysis_status='error', analysis_reason=?, "
                         "analysis_attempts = analysis_attempts + 1 WHERE id=?", (str(exc)[:500], sid))
            conn.commit()
            return sid, "failed", str(exc)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=max(1, cfg.analysis.concurrency)) as pool:
        futures = [pool.submit(task, sid) for sid in ids]
        try:
            for fut in as_completed(futures):
                sid, status, info = fut.result()
                with lock:
                    finished += 1
                    if status == "done":
                        report.analyzed.append(sid)
                        report.cost_usd += info or 0.0
                    elif status == "skipped":
                        report.skipped.append(sid)
                    elif status == "paused":
                        report.failed.append((sid, info))
                        report.paused_until = to_iso(utcnow() + timedelta(hours=1))
                    elif status == "failed":
                        report.failed.append((sid, info))
                if progress:
                    progress(f"{sid[:8]}: {status}" if len(ids) == 1 else f"analyzing sessions: {finished} of {len(ids)} done")
        except KeyboardInterrupt:  # Ctrl-C: drop the queue; the calls already running finish and are saved
            stop.set()
            for fut in futures:
                fut.cancel()
            if progress:
                progress("stopping: finishing the sessions already in progress…")
            raise


def _synthesize(cfg: Config, conn, runner: Runner, report: WorkReport, *, force=False, progress=None):
    from .synthesize import GLOBAL, global_needs_synthesis, projects_needing_synthesis, synthesize_project

    targets = projects_needing_synthesis(conn, cfg, force=force)
    if global_needs_synthesis(conn, cfg) or (force and targets):
        targets.append(GLOBAL)
    for path in targets:
        try:
            if progress:
                progress(f"synthesizing {path.rsplit('/', 1)[-1]}…")
            synthesize_project(conn, cfg, path, runner)
            report.synthesized.append(path)
        except UsageLimitError as exc:
            until = to_iso(utcnow() + timedelta(hours=1))
            kv_set(conn, PAUSE_KEY, until)
            conn.commit()
            report.paused_until = until
            report.failed.append((path, str(exc)))
            break
        except (LLMError, ValueError) as exc:
            report.failed.append((path, str(exc)))
        except Exception as exc:  # a malformed reply must not stop the other projects, the review or the export
            conn.rollback()
            log.exception("synthesis failed for %s", path)
            report.failed.append((path, f"{type(exc).__name__}: {exc}"))


def _weekly_review(cfg: Config, conn, runner: Runner, report: WorkReport, *, progress=None):
    """Write the review of the last completed week once all its sessions are analyzed."""
    from .reviews import generate_review, review_ready

    ready, key = review_ready(conn)
    if not ready:
        return
    try:
        if progress:
            progress(f"writing weekly review {key}…")
        generate_review(conn, cfg, key, runner)
        report.reviews.append(key)
    except UsageLimitError as exc:
        kv_set(conn, PAUSE_KEY, to_iso(utcnow() + timedelta(hours=1)))
        conn.commit()
        report.failed.append((key, str(exc)))
    except (LLMError, ValueError) as exc:
        report.failed.append((key, str(exc)))
    except Exception as exc:
        conn.rollback()
        log.exception("weekly review %s failed", key)
        report.failed.append((key, f"{type(exc).__name__}: {exc}"))


def _themes(cfg: Config, report: WorkReport, *, progress=None):
    """Re-group the glossary categories whose terms changed in this run's glossary rebuilds (the Map's Theme level)."""
    from .glossary import build_themes

    if not report.synthesized or report.paused_until:
        return
    for cat, result in build_themes(cfg, concurrency=cfg.analysis.concurrency, progress=progress).items():
        if isinstance(result, str) and result.startswith("failed"):
            report.failed.append((f"themes:{cat}", result))


def _glossaries(cfg: Config, conn, runner: Runner, report: WorkReport, *, progress=None):
    """Refresh the glossary of every project whose knowledge base was just re-synthesized."""
    from .glossary import build_glossaries

    if not report.synthesized or report.paused_until:
        return
    results = build_glossaries(cfg, list(report.synthesized), concurrency=cfg.analysis.concurrency, progress=progress)
    for path, result in results.items():
        if isinstance(result, str) and result.startswith("failed"):
            report.failed.append((f"glossary:{path}", result))
            if any(m in result.lower() for m in ("usage limit", "rate limit", "429")):
                kv_set(conn, PAUSE_KEY, to_iso(utcnow() + timedelta(hours=1)))
                conn.commit()
                report.paused_until = kv_get(conn, PAUSE_KEY)
