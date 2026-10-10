"""The menu-bar item's state and text (menubar.py), worked out without AppKit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from chronicle.menubar import ATTENTION, OK, PAUSED, WORKING, ago, day_label, summarize, when
from chronicle.util import to_iso

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def status(**kw) -> dict:
    base = {"pending": {"ready": 0, "queued": 0}, "paused_until": None, "last_sync": "2026-10-10T11:30:00Z",
            "jobs": {}, "update": None, "hub_url": None}
    return {**base, **kw}


def test_quiet_when_nothing_needs_a_look():
    snap = summarize(status(), now=NOW)
    assert (snap.state, snap.title, snap.sub) == (OK, "All caught up", "Synced 30 min ago")
    assert snap.headline == "All caught up · Synced 30 min ago"
    assert snap.detail == "" and snap.update is None and not snap.syncing and snap.note == ""


def test_never_synced():
    assert summarize(status(last_sync=None), now=NOW).sub == "Not synced yet"


def test_a_queue_is_the_title_and_does_not_change_the_icon():
    snap = summarize(status(pending={"ready": 3, "queued": 12}), now=NOW)
    assert (snap.state, snap.title, snap.sub) == (OK, "12 sessions to analyze", "Synced 30 min ago")
    assert snap.detail == "12 sessions waiting for analysis" and snap.stats == {"waiting": 12}
    assert summarize(status(pending={"queued": 1}), now=NOW).title == "1 session to analyze"


def test_what_stops_the_queue_is_noted():
    st = status(pending={"queued": 3, "block": "automatic analysis is off (analysis.auto)"})
    assert summarize(st, now=NOW).note == "automatic analysis is off (analysis.auto)"
    assert summarize(status(pending={"queued": 0, "block": "off"}), now=NOW).note == ""


def test_a_running_job_with_progress():
    jobs = {"sync": {"state": "running", "done": 2, "total": 5}}
    snap = summarize(status(jobs=jobs), now=NOW)
    assert (snap.state, snap.title, snap.sub, snap.progress, snap.syncing) == (WORKING, "Syncing", "2 of 5", (2, 5), True)


def test_a_running_job_says_what_it_is_doing():
    snap = summarize(status(jobs={"themes": {"state": "running", "message": "grouping 40 terms…"}}), now=NOW)
    assert (snap.title, snap.sub, snap.progress) == ("Grouping glossary themes", "grouping 40 terms…", None)


def test_analysis_by_another_process_counts_as_working():
    snap = summarize(status(), now=NOW, analyzing=2)
    assert (snap.state, snap.title, snap.syncing) == (WORKING, "Analyzing 2 sessions", False)


def test_the_apps_own_sync_loop_counts_as_syncing():
    snap = summarize(status(), now=NOW, sync_running=True)
    assert (snap.state, snap.title, snap.syncing) == (WORKING, "Syncing", True)


def test_finished_jobs_are_not_work():
    snap = summarize(status(jobs={"themes": {"state": "done"}}), now=NOW)
    assert snap.state == OK


@pytest.mark.parametrize("kw, title, sub", [
    ({"sync_error": "database is locked"}, "Sync failed", "database is locked"),
    ({"push": {"at": "2026-10-10T11:00:00Z", "errors": ["hub unreachable"]}}, "Sending to the hub failed", "hub unreachable"),
])
def test_failures_need_a_look_even_while_something_runs(kw, title, sub):
    snap = summarize(status(jobs={"analyze:abc": {"state": "running"}}), now=NOW, **kw)
    assert (snap.state, snap.title, snap.sub) == (ATTENTION, title, sub)


def test_a_failed_sync_job_needs_a_look_until_the_next_one():
    st = status(jobs={"sync": {"state": "error", "result": "no space left on device"}})
    assert summarize(st, now=NOW).state == ATTENTION
    st["jobs"]["sync"] = {"state": "running"}
    assert summarize(st, now=NOW).state == WORKING


def test_long_errors_are_cut_to_fit():
    snap = summarize(status(), now=NOW, sync_error="x " * 200)
    assert len(snap.sub) <= 90 and snap.sub.endswith("…")


def test_paused_until_later_but_not_once_it_has_passed():
    snap = summarize(status(paused_until="2026-10-10T13:00:00Z"), now=NOW)
    assert (snap.state, snap.title) == (PAUSED, "Analysis paused")
    assert snap.sub == f"Resumes {when('2026-10-10T13:00:00Z', NOW)} (usage limit)"
    assert summarize(status(paused_until="2026-10-10T11:00:00Z"), now=NOW).state == OK


def test_a_spoke_that_sends_its_sessions_says_where():
    st = status(hub_url="https://hub.example.com:8443", pending={"queued": 4})
    snap = summarize(st, now=NOW, sends_files=True)
    assert (snap.title, snap.sub) == ("Sending to hub.example.com", "Nothing sent yet")
    assert snap.detail == "" and snap.hub == "" and snap.stats == {"waiting": None}  # the hub analyzes them
    snap = summarize(st, now=NOW, sends_files=True, hub_name="Team hub", push={"at": "2026-10-10T11:45:00Z", "errors": []})
    assert (snap.state, snap.title, snap.sub) == (OK, "Sending to Team hub", "Last sent 15 min ago")


def test_a_spoke_that_shares_knowledge_syncs_and_analyzes_here():
    st = status(hub_url="https://hub.example.com", pending={"queued": 4})
    snap = summarize(st, now=NOW, hub_name="Team hub")
    assert snap.title == "4 sessions to analyze"
    assert snap.hub == "Sharing knowledge with Team hub · nothing sent yet"
    snap = summarize(st, now=NOW, push={"at": "2026-10-10T11:45:00Z", "errors": []})
    assert snap.hub == "Sharing knowledge with hub.example.com · last sent 15 min ago"


def test_no_hub_no_hub_line():
    assert summarize(status(), now=NOW).hub == ""


def test_an_update_shows_in_the_menu_only():
    snap = summarize(status(update={"to": "0.19.0", "key": "0.19.0"}), now=NOW)
    assert (snap.state, snap.update) == (OK, "0.19.0")


def test_when_says_the_day_only_before_today():
    assert when("2026-10-10T11:30:00Z", NOW).startswith("at ")
    assert not when("2026-10-01T11:30:00Z", NOW).startswith("at ")
    assert when(None, NOW) == ""


@pytest.mark.parametrize("iso, expected", [
    ("2026-10-10T11:59:30Z", "just now"),
    ("2026-10-10T11:05:00Z", "55 min ago"),
    (None, ""),
])
def test_ago(iso, expected):
    assert ago(iso, NOW) == expected


def test_ago_counts_calendar_days():
    local_noon = NOW.astimezone().replace(hour=12, minute=0)
    assert ago(to_iso(local_noon - timedelta(hours=3)), local_noon) == "3 h ago"
    assert ago(to_iso(local_noon - timedelta(days=1)), local_noon) == "yesterday"
    assert ago(to_iso(local_noon - timedelta(days=3)), local_noon) == "3 days ago"
    assert ago(to_iso(local_noon - timedelta(days=30)), local_noon) == f"{(local_noon - timedelta(days=30)):%b} {(local_noon - timedelta(days=30)).day}"


def test_day_label():
    local_noon = NOW.astimezone().replace(hour=12, minute=0)
    assert day_label(to_iso(local_noon), local_noon) == "Today"
    assert day_label(to_iso(local_noon - timedelta(days=1)), local_noon) == "Yesterday"
    assert day_label(to_iso(local_noon - timedelta(days=4)), local_noon).count(",") == 1


def test_the_page_gets_the_state_and_its_picture():
    page = summarize(status(), now=NOW, sync_error="boom").to_page()
    assert page["state"] == ATTENTION and page["art"] == "art-glitch.webp"
    assert {"title", "sub", "hub", "recent", "update", "syncing", "stats", "note", "progress"} <= set(page)


def test_snapshot_from_the_dashboards_own_app(synced):
    from chronicle.menubar import snapshot
    from chronicle.server import make_server

    httpd = make_server(synced["cfg"], port=0)
    try:
        snap = snapshot(httpd.app)
    finally:
        httpd.server_close()
    assert snap.state in (OK, WORKING)
    assert snap.recent and snap.recent[0]["id"]
    assert all(set(r) == {"id", "title", "project_name", "agent", "outcome", "analysis_status", "at", "day", "time"}
               for r in snap.recent)
    assert set(snap.stats) == {"waiting", "today", "lessons"}


def test_stats_count_today_and_the_last_week(synced):
    from chronicle.menubar import stats

    conn = synced["conn"]
    n = conn.execute("SELECT COUNT(*) FROM sessions WHERE source NOT IN ('history')").fetchone()[0]
    conn.execute("UPDATE sessions SET ended_at = ?", (to_iso(NOW),))
    conn.execute("INSERT INTO knowledge (kind, title, source, status, created_at) VALUES ('fix', 'a', 'analysis', 'active', ?)",
                 (to_iso(NOW - timedelta(days=2)),))
    conn.execute("INSERT INTO knowledge (kind, title, source, status, created_at) VALUES ('fix', 'b', 'analysis', 'active', ?)",
                 (to_iso(NOW - timedelta(days=9)),))
    conn.execute("INSERT INTO knowledge (kind, title, source, status, created_at) VALUES ('fix', 'c', 'manual', 'active', ?)",
                 (to_iso(NOW),))
    got = stats(conn, NOW)
    assert got["today"] == n and got["lessons"] >= 1
    before = got["lessons"]
    conn.execute("UPDATE knowledge SET status = 'dismissed' WHERE title = 'a'")
    assert stats(conn, NOW)["lessons"] == before - 1


def test_recent_sessions_leave_out_imported_chats(synced):
    from chronicle.menubar import recent_sessions

    conn = synced["conn"]
    sid = recent_sessions(conn)[0]["id"]
    conn.execute("UPDATE sessions SET source = 'chatgpt-export'")
    assert recent_sessions(conn) == []
    conn.execute("UPDATE sessions SET source = 'transcript' WHERE id = ?", (sid,))
    assert [r["id"] for r in recent_sessions(conn)] == [sid]


def test_only_the_login_item_shows_the_icon_by_itself(env, monkeypatch):
    from chronicle.install import UI_LABEL
    from chronicle.menubar import wants_menu_bar

    cfg = env["cfg"]
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.delenv("XPC_SERVICE_NAME", raising=False)
    assert not wants_menu_bar(cfg)  # a dashboard started in a terminal
    monkeypatch.setenv("XPC_SERVICE_NAME", UI_LABEL)
    assert wants_menu_bar(cfg)
    cfg.server_menu_bar = False
    assert not wants_menu_bar(cfg)
    cfg.server_menu_bar = True
    monkeypatch.setattr("sys.platform", "linux")
    assert not wants_menu_bar(cfg)


def test_menu_bar_can_be_turned_off_in_config(env):
    from chronicle.config import load_config

    cfg = env["cfg"]
    assert load_config(cfg.home).server_menu_bar is True
    cfg.config_path.write_text("[server]\nmenu_bar = false\n")
    assert load_config(cfg.home).server_menu_bar is False


def test_agent_sync_error_reads_the_launchd_exit_code(monkeypatch):
    from chronicle import menubar

    for info, expected in [({"loaded": True, "last_exit": "0"}, None),
                           ({"loaded": True, "last_exit": "(never exited)"}, None),
                           ({"loaded": False, "last_exit": "1"}, None),
                           ({"installed": False}, None)]:
        monkeypatch.setattr("chronicle.install.background_status", lambda info=info: info)
        assert menubar.agent_sync_error() is expected
    monkeypatch.setattr("chronicle.install.background_status", lambda: {"loaded": True, "last_exit": "78"})
    assert "78" in menubar.agent_sync_error()


def test_without_pyobjc_the_dashboard_serves_as_before(env, monkeypatch):
    import builtins

    from chronicle import menubar

    real = builtins.__import__

    def no_appkit(name, *a, **kw):
        if name in ("AppKit", "PyObjCTools"):
            raise ImportError(name)
        return real(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_appkit)
    assert menubar.run_with_server(env["cfg"], object(), "http://127.0.0.1:1/") is False
