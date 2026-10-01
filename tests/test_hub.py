"""Several computers, one archive: Tailscale access, the hub API, pushing from a spoke, and ingesting what it sent."""

import gzip
import hashlib
import json
import os
import stat
import sys
import textwrap
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from chronicle import hub
from chronicle.config import load_config
from chronicle.db import connect, kv_set

from conftest import CWD, FAKE_CLAUDE, PROJECT_DIR, SID, fake_log, write_fake_claude_tree

SPOKE_SID = "99999999-8888-7777-6666-555555555555"
SPOKE_CWD = "/home/test/code/demo-app"


def _serve(cfg):
    from chronicle.server import App, make_handler

    app = App(cfg)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = httpd.server_address[1]
    httpd.RequestHandlerClass = make_handler(app, port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return app, httpd, f"http://127.0.0.1:{port}"


def _make_spoke(tmp: Path, url: str, token: str, *, cwd: str = SPOKE_CWD, extra: str = "") -> tuple:
    """A second computer: its own Chronicle home and a Claude Code folder with one session of its own."""
    home, claude = tmp / "spoke-home", tmp / "spoke-claude"
    write_fake_claude_tree(claude)
    proj = claude / "projects" / PROJECT_DIR
    new_proj = claude / "projects" / cwd.replace("/", "-")
    proj.rename(new_proj)
    for path in sorted(new_proj.rglob("*"), reverse=True):  # its own session id and folder
        if path.is_file() and path.suffix in (".jsonl", ".json"):
            path.write_text(path.read_text().replace(SID, SPOKE_SID).replace(CWD, cwd))
        if SID in path.name:
            path.rename(path.with_name(path.name.replace(SID, SPOKE_SID)))
    (claude / "history.jsonl").unlink()
    home.mkdir()
    (home / "config.toml").write_text(textwrap.dedent(f"""\
        [sources]
        claude_dirs = ["{claude}"]
        codex_dirs = []
        [hub]
        url = "{url}"
        """) + extra)
    cfg = load_config(home)
    cfg.ensure_dirs()
    hub.write_token(cfg, token)
    return cfg, claude, new_proj / f"{SPOKE_SID}.jsonl"


@pytest.fixture()
def hubenv(synced, monkeypatch):
    """The `synced` computer as a hub, serving on a free port, with a spoke that joined it."""
    requests = []
    monkeypatch.setattr(hub.IngestTrigger, "request", lambda self: requests.append(1))
    token = hub.new_token(synced["cfg"])
    app, httpd, url = _serve(synced["cfg"])
    spoke_cfg, spoke_claude, spoke_main = _make_spoke(synced["tmp"], url, token)
    synced.update(app=app, url=url, token=token, spoke=spoke_cfg, spoke_claude=spoke_claude, spoke_main=spoke_main,
                  ingest_requests=requests)
    yield synced
    httpd.shutdown()


def test_push_then_ingest_tags_the_computer(hubenv):
    from chronicle.ingest import sync

    cfg, spoke = hubenv["cfg"], hubenv["spoke"]
    spoke_id = hub.local_machine(spoke)["id"]
    report = hub.push(spoke)
    assert report.sent >= 3 and not report.errors  # transcript, subagent files, memory notes
    assert hubenv["ingest_requests"], "the hub was not asked to ingest what arrived"
    received = cfg.machines_dir / spoke_id / "claude" / "projects" / SPOKE_CWD.replace("/", "-") / f"{SPOKE_SID}.jsonl"
    assert received.read_bytes() == hubenv["spoke_main"].read_bytes()
    assert abs(received.stat().st_mtime - hubenv["spoke_main"].stat().st_mtime) < 0.01

    sync(cfg, hubenv["conn"])
    conn = hubenv["conn"]
    row = conn.execute("SELECT machine_id, project_path, archive_path, n_prompts FROM sessions WHERE id = ?", (SPOKE_SID,)).fetchone()
    assert row["machine_id"] == spoke_id and row["project_path"] == SPOKE_CWD and row["n_prompts"] == 2
    assert f"/archive/machines/{spoke_id}/claude/" in row["archive_path"]
    own = conn.execute("SELECT machine_id FROM sessions WHERE id = ?", (SID,)).fetchone()[0]
    assert own == hub.local_machine(cfg)["id"] != spoke_id
    seen = {m["id"]: m for m in hub.machines(conn, cfg)}
    assert set(seen) == {own, spoke_id} and seen[own]["this"] and seen[spoke_id]["sessions"] == 1
    assert seen[spoke_id]["last_push"] and seen[spoke_id]["files"] >= 3

    again = hub.push(spoke)  # the hub already has everything
    assert again.sent == 0 and again.unchanged == report.sent
    with open(hubenv["spoke_main"], "a") as fh:  # the session goes on
        fh.write(json.dumps({"type": "user", "sessionId": SPOKE_SID, "cwd": SPOKE_CWD, "timestamp": "2026-09-20T11:00:00.000Z",
                             "message": {"role": "user", "content": "one more thing"}}) + "\n")
    assert hub.push(spoke).sent == 1


def test_hub_api_refuses_bad_tokens_and_paths(hubenv):
    spoke = hubenv["spoke"]
    hub.write_token(spoke, "not-the-token")
    with pytest.raises(hub.HubError, match="token"):
        hub.push(spoke)
    body = gzip.compress(b"x")
    params = f"machine={hub.local_machine(spoke)['id']}&root=claude&path=projects/../../evil&size=1&mtime=1&sha256={hashlib.sha256(b'x').hexdigest()}"
    req = urllib.request.Request(f"{hubenv['url']}/api/hub/file?{params}", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {hubenv['token']}"})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 400
    assert not any(hubenv["cfg"].home.parent.glob("evil*"))
    bad = urllib.request.Request(f"{hubenv['url']}/api/hub/hello", data=b"{}", method="POST")  # no token at all
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(bad, timeout=10)
    assert exc.value.code == 401
    hub.write_token(spoke, hubenv["token"])
    (spoke.home / "machine.json").write_text(json.dumps(hub.local_machine(hubenv["cfg"])))  # a copied Chronicle folder
    with pytest.raises(hub.HubError, match="own id"):
        hub.push(spoke)


def test_damaged_upload_is_rejected(hubenv):
    data = b'{"a": 1}\n'
    params = (f"machine={hub.local_machine(hubenv['spoke'])['id']}&root=claude&path=history.jsonl&size={len(data)}"
              f"&mtime=1&sha256={hashlib.sha256(b'other').hexdigest()}")
    req = urllib.request.Request(f"{hubenv['url']}/api/hub/file?{params}", data=gzip.compress(data), method="POST",
                                 headers={"Authorization": f"Bearer {hubenv['token']}"})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=10)
    assert exc.value.code == 400 and b"damaged" in exc.value.read()
    assert not list(hubenv["cfg"].machines_dir.rglob("history.jsonl*"))


def test_forgotten_session_is_not_taken_back(hubenv):
    from chronicle.ingest import forget_session, sync

    hub.push(hubenv["spoke"])
    sync(hubenv["cfg"], hubenv["conn"])
    forget_session(hubenv["conn"], hubenv["cfg"], SPOKE_SID, delete_transcript=True)
    hub.push(hubenv["spoke"])  # the spoke still has it and offers it again
    sync(hubenv["cfg"], hubenv["conn"])
    assert hubenv["conn"].execute("SELECT COUNT(*) FROM sessions WHERE id = ?", (SPOKE_SID,)).fetchone()[0] == 0
    assert not list(hubenv["cfg"].machines_dir.rglob(f"{SPOKE_SID}.jsonl"))


def test_excluded_projects_never_leave_the_spoke(hubenv):
    spoke = hubenv["spoke"]
    spoke.exclude_projects = ["/home/test/code/*"]
    report = hub.push(spoke)
    assert report.skipped >= 3 and report.sent == 0
    assert not list(hubenv["cfg"].machines_dir.rglob("*.jsonl"))


def test_projects_matched_across_computers(hubenv, monkeypatch):
    from chronicle.ingest import sync

    cfg, conn = hubenv["cfg"], hubenv["conn"]
    cfg.hub_path_map = {"/home/test/code": "/Users/test/Projects"}
    hub.push(hubenv["spoke"])
    sync(cfg, conn)
    row = conn.execute("SELECT project_path, machine_path FROM sessions WHERE id = ?", (SPOKE_SID,)).fetchone()
    assert row["project_path"] == CWD and row["machine_path"] == SPOKE_CWD  # same project as the hub's own session

    # by git remote: the spoke reported its repository, the hub knows the same remote for a folder of its own
    spoke_id = hub.local_machine(hubenv["spoke"])["id"]
    conn.execute("UPDATE machines SET repos_json = ? WHERE id = ?",
                 (json.dumps({"/srv/x/app": ["/srv/x/app", "github.com/org/demo-app"]}), spoke_id))
    kv_set(conn, f"git:{CWD}", json.dumps([CWD, "github.com/org/demo-app"]))
    conn.commit()
    cfg.hub_path_map = {}
    r = hub.resolver(cfg, conn, fresh=True)
    assert r.resolve(spoke_id, "/srv/x/app/api") == f"{CWD}/api"
    assert r.resolve(spoke_id, "/srv/x/other") == "/srv/x/other"  # nothing known: kept as recorded
    assert r.resolve(spoke_id, "/work/demo", remote="git@github.com:Org/demo-app.git") == CWD  # Codex's own remote
    assert r.resolve(hub.local_machine(cfg)["id"], "/srv/x/app") == "/srv/x/app"  # the hub's own sessions: untouched


def test_normalize_remote():
    for url in ("git@github.com:Org/Repo.git", "https://github.com/org/repo", "https://tok@github.com/Org/Repo/",
                "ssh://git@github.com/org/repo.git"):
        assert hub.normalize_remote(url) == "github.com/org/repo"
    assert hub.normalize_remote("not a url") is None and hub.normalize_remote(None) is None


def test_spoke_hands_over_its_earlier_analyses(synced, tmp_path, monkeypatch):
    """A spoke that already analyzed its sessions sends the results once; the hub doesn't pay for them again."""
    from chronicle.ingest import sync
    from chronicle.worker import run_worker

    monkeypatch.setattr(hub.IngestTrigger, "request", lambda self: None)
    cfg = synced["cfg"]
    token = hub.new_token(cfg)
    _app, httpd, url = _serve(cfg)
    try:
        spoke, _claude, _main = _make_spoke(tmp_path, "", token, extra=textwrap.dedent(f"""\
            [analysis]
            claude_bin = "{synced['fake']}"
            idle_minutes = 0
            concurrency = 1
            """))
        conn = connect(spoke.db_path)
        sync(spoke, conn)  # the spoke's own Chronicle, before it joins
        conn.close()
        run_worker(spoke, synthesize=False, export=False)
        spoke_conn = connect(spoke.db_path)
        assert spoke_conn.execute("SELECT analysis_status FROM sessions WHERE id = ?", (SPOKE_SID,)).fetchone()[0] == "done"
        spoke_conn.close()
        calls = len(fake_log(synced))

        spoke.hub_url = url  # joins
        report = hub.push(spoke)
        assert report.analyses >= 1
        sync(cfg, synced["conn"])
        row = synced["conn"].execute("SELECT analysis_status, summary, title FROM sessions WHERE id = ?", (SPOKE_SID,)).fetchone()
        assert row["analysis_status"] == "done" and row["summary"] and row["title"] == "Fixed login token expiry bug"
        assert synced["conn"].execute("SELECT COUNT(*) FROM knowledge WHERE session_id = ? AND source = 'analysis'",
                                      (SPOKE_SID,)).fetchone()[0] >= 1
        assert not list(cfg.machines_dir.glob(f"*/{hub.ANALYSES_FILE}"))  # applied, so gone
        run_worker(cfg, synthesize=False, export=False)
        analyzed = [c for c in fake_log(synced)[calls:] if SPOKE_SID in json.dumps(c)]
        assert not analyzed, "the hub analyzed a session the spoke had already analyzed"
        assert hub.push(spoke).analyses == 0  # only once
    finally:
        httpd.shutdown()


def test_spoke_sends_instead_of_recording(env, monkeypatch):
    from chronicle import hooks
    from chronicle.worker import run_worker

    cfg = env["cfg"]
    with open(cfg.config_path, "a") as fh:
        fh.write('\n[hub]\nurl = "https://pc.tail1234.ts.net"\n')
    spawned = []
    monkeypatch.setattr(hooks, "spawn_detached", lambda args, log: spawned.append(args))
    hooks._on_session_end({"transcript_path": str(env["main"])}, ended=True)
    assert spawned and spawned[0][-2:] == ["push", "--quiet"]
    report = run_worker(load_config(cfg.home))
    assert "hub" in (report.note or "") and not report.analyzed
    assert not fake_log(env)


def test_tailnet_names_and_logins(synced):
    cfg = synced["cfg"]
    cfg.server_allowed_hosts = ["pc.tail1234.ts.net"]
    cfg.server_allowed_users = ["me@github"]
    _app, httpd, base = _serve(cfg)

    def status(headers):
        req = urllib.request.Request(base + "/api/jobs", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as exc:
            return exc.code

    try:
        ts = {"Host": "pc.tail1234.ts.net", "X-Forwarded-For": "100.64.0.2"}  # as Tailscale Serve forwards it
        assert status({**ts, "Tailscale-User-Login": "me@github"}) == 200
        assert status({**ts, "Tailscale-User-Login": "someone@else"}) == 403
        assert status(ts) == 403  # no identity: a tagged device
        # Serve passes the client's Host through as sent: claiming to be this computer must not skip the login check
        assert status({"Host": base.removeprefix("http://"), "X-Forwarded-For": "100.64.0.2"}) == 403
        assert status({"Host": base.removeprefix("http://"), "X-Forwarded-For": "100.64.0.2", "Tailscale-User-Login": "me@github"}) == 200
        assert status({"Host": "evil.example"}) == 403
        assert status({}) == 200  # this computer itself, by 127.0.0.1
        cfg.server_allowed_users = []
        assert status(ts) == 200  # anyone on the tailnet
        req = urllib.request.Request(base + "/api/sync", data=b"{}", method="POST",
                                     headers={**ts, "X-Chronicle": "1", "Tailscale-User-Login": "x"})
        cfg.server_allowed_users = ["me@github"]
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 403
    finally:
        httpd.shutdown()


FAKE_TAILSCALE = r'''#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_TS_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\n")
if args[:2] == ["status", "--json"]:
    print(json.dumps({"BackendState": "Running", "Self": {"DNSName": "pc.tail1234.ts.net.", "UserID": 7,
                      "TailscaleIPs": ["100.64.0.1"]}, "User": {"7": {"LoginName": "me@github"}},
                      "CurrentTailnet": {"Name": "me@github"}}))
elif args[:2] == ["serve", "status"]:
    print(json.dumps({"Web": {"pc.tail1234.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8765"}}}}}))
'''


def test_tailnet_on_and_hub_enable(env, monkeypatch, capsys):
    from chronicle.cli import main

    bin_dir = env["tmp"] / "tsbin"
    bin_dir.mkdir()
    fake = bin_dir / "tailscale"
    fake.write_text(FAKE_TAILSCALE.replace("{python}", sys.executable))
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_TS_LOG", str(env["tmp"] / "ts.log"))
    monkeypatch.setattr(sys, "stdin", open(os.devnull))

    assert main(["tailnet", "on"]) == 0
    cfg = load_config(env["home"])
    assert cfg.server_allowed_hosts == ["pc.tail1234.ts.net"] and cfg.server_allowed_users == ["me@github"]
    calls = [json.loads(line) for line in (env["tmp"] / "ts.log").read_text().splitlines()]
    assert ["serve", "--bg", "--https=443", f"http://127.0.0.1:{cfg.server_port}"] in calls
    assert "https://pc.tail1234.ts.net/" in capsys.readouterr().out

    assert main(["hub", "enable"]) == 0
    out = capsys.readouterr().out
    token = hub.read_token(cfg)
    assert token and f"chronicle hub join https://pc.tail1234.ts.net --token {token}" in out.replace("\n", "")
    assert oct(hub.token_path(cfg).stat().st_mode & 0o777) == "0o600"

    assert main(["tailnet", "off"]) == 0
    cfg = load_config(env["home"])
    assert cfg.server_allowed_hosts == [] and cfg.server_allowed_users == []


def test_systemd_units_quote_commands(env):
    from chronicle.install import systemd_units

    units = systemd_units(env["cfg"], "/usr/bin/python3 -m chronicle", interval=600)
    assert "ExecStart=/usr/bin/python3 -m chronicle sync --work --quiet" in units["chronicle-sync.service"]
    assert "OnUnitActiveSec=600s" in units["chronicle-sync.timer"]
    assert "ExecStart=/usr/bin/python3 -m chronicle ui" in units["chronicle-ui.service"]
    assert "Restart=always" in units["chronicle-ui.service"]
    spaced = systemd_units(env["cfg"], "'/opt/my apps/chronicle'")["chronicle-ui.service"]
    assert 'ExecStart="/opt/my apps/chronicle" ui' in spaced
