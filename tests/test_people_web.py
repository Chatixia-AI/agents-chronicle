"""People on a hub, from the dashboard's side: who is viewing (at the hub, a company sign-in, a session cookie), what
each role may do, signing in with an invite or sign-in link, the People API, and the hub API's person tokens."""

import json
import urllib.error
import urllib.request

import pytest

from chronicle import hub, people
from chronicle.config import load_config, set_config_value

from test_hub import _serve

MACHINE = "11111111-2222-4333-8444-555555555555"
OTHER = "99999999-2222-4333-8444-555555555555"
REMOTE = {"X-Forwarded-For": "203.0.113.5"}  # not this computer: test requests all come from 127.0.0.1
TAILNET = {**REMOTE, "Tailscale-User-Login": "me@github"}  # a phone through Tailscale Serve, which names its login


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def _raw(url, path, body=None, headers=None):
    req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", "X-Chronicle": "1", **(headers or {})})
    try:
        with OPENER.open(req, timeout=10) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def _call(url, path, body=None, headers=None):
    status, _, data = _raw(url, path, body, headers)
    return status, json.loads(data)


def _as(session, **extra):
    return {**REMOTE, "Cookie": f"chronicle_session={session}", **extra}


@pytest.fixture()
def hubweb(synced, monkeypatch):
    """The `synced` computer as a hub serving its dashboard on a free port; no people yet."""
    monkeypatch.setattr(hub.IngestTrigger, "request", lambda self: None)
    cfg = synced["cfg"]
    token = hub.new_token(cfg)
    app, httpd, url = _serve(cfg)
    synced.update(app=app, url=url, token=token)
    yield synced
    httpd.shutdown()


@pytest.fixture()
def team(hubweb):
    """Ada (admin), Bob (member) and Vic (read-only), each with a browser session."""
    conn = hubweb["conn"]
    ada = people.add(conn, "Ada", "ada@example.com", "admin")
    bob = people.add(conn, "Bob", "bob@example.com", "member", by=ada)
    vic = people.add(conn, "Vic", "vic@example.com", "readonly", by=ada)
    sessions = {p["name"]: people.open_browser(conn, people.invite(conn, p["id"]), "test")[1] for p in (ada, bob, vic)}
    hubweb.update(ada=ada, bob=bob, vic=vic, sessions=sessions)
    return hubweb


def test_a_hub_without_people_answers_as_before(hubweb):
    url = hubweb["url"]
    code, dv = _call(url, "/api/devices")
    assert code == 200 and dv["here"] and dv["can_admin"] and not dv["people_mode"] and dv["viewer"]["role"] == "admin"
    code, dv = _call(url, "/api/devices", headers=TAILNET)  # a Tailscale login: lets in, but hub settings stay here
    assert code == 200 and not dv["here"] and not dv["can_admin"] and not dv["viewer"]["here"]
    assert _call(url, "/api/suggestions/seen", {}, TAILNET) == (200, {"ok": True})
    assert _call(url, "/api/people", headers=TAILNET)[0] == 403
    assert _call(url, "/api/team-store/save", {"enabled": False}, TAILNET)[0] == 403
    code, me = _call(url, "/api/me")
    assert code == 200 and me["viewer"]["here"] and not me["people_mode"]
    status, headers, page = _raw(url, "/signin?code=AAAA-BBBB-CCCC")
    assert status == 400 and b"known on this hub" in page and headers["Content-Type"].startswith("text/html")


def test_who_may_look_and_who_may_change(team):
    url, s = team["url"], team["sessions"]
    code, r = _call(url, "/api/overview", headers=REMOTE)
    assert code == 401 and r["signin"] is True
    assert _call(url, "/api/overview")[0] == 200  # the hub computer itself is always an admin
    assert _raw(url, "/", headers=REMOTE)[0] == 200  # the page stays public, so it can show how to sign in
    assert _call(url, "/api/overview", headers=_as("not-a-session"))[0] == 401

    for name, role in (("Vic", "readonly"), ("Bob", "member")):
        code, me = _call(url, "/api/me", headers=_as(s[name]))
        assert code == 200 and me["viewer"]["name"] == name and me["viewer"]["role"] == role
        assert me["people_mode"] and not me["can_admin"] and not me["viewer"]["here"]
        assert _call(url, "/api/overview", headers=_as(s[name]))[0] == 200
        code, r = _call(url, "/api/suggestions/seen", {}, _as(s[name]))
        assert code == 403 and "admin" in r["error"]
        assert _call(url, "/api/people", headers=_as(s[name]))[0] == 403
        assert _call(url, "/api/team-store/save", {"enabled": False}, _as(s[name]))[0] == 403
    code, r = _call(url, "/api/suggestions/seen", {}, _as(s["Bob"], **{"X-Chronicle-Lang": "ja"}))
    assert r["error"] == "これができるのはこのハブの管理者だけです"

    code, dv = _call(url, "/api/devices", headers=_as(s["Ada"]))
    assert code == 200 and dv["can_admin"] and dv["viewer"]["name"] == "Ada" and not dv["here"]
    assert _call(url, "/api/suggestions/seen", {}, _as(s["Ada"])) == (200, {"ok": True})
    assert _call(url, "/api/people", headers=_as(s["Ada"]))[0] == 200
    assert _call(url, "/api/devices/share", {"share": "knowledge"}, _as(s["Ada"]))[0] == 403  # this computer's own
    assert _call(url, "/api/devices/hub-signin", {}, _as(s["Ada"]))[0] == 403

    status, headers, _ = _raw(url, "/api/signout", {}, _as(s["Vic"]))
    assert status == 200 and "Max-Age=0" in headers["Set-Cookie"]
    assert _call(url, "/api/overview", headers=_as(s["Vic"]))[0] == 401


def test_team_store_settings_for_an_admin_person(team):
    url, s, home = team["url"], team["sessions"], team["cfg"].home
    set_config_value(team["cfg"], "hub", "store", '"postgres"')
    assert _call(url, "/api/team-store/save", {"enabled": False}, _as(s["Bob"]))[0] == 403
    assert load_config(home).hub_store == "postgres"
    code, r = _call(url, "/api/team-store/save", {"enabled": False}, _as(s["Ada"]))
    assert code == 200 and r["ok"] and load_config(home).hub_store == ""


def test_signing_in_with_a_link(team):
    url, conn, app = team["url"], team["conn"], team["app"]
    code = people.invite(conn, team["vic"]["id"])
    status, headers, _ = _raw(url, f"/signin?code={code.lower()}", headers=REMOTE)
    cookie = headers["Set-Cookie"]
    assert status == 302 and headers["Location"] == "/#/" and "Secure" not in cookie
    assert all(part in cookie for part in ("HttpOnly", "SameSite=Lax", "Path=/", "Max-Age=2592000"))
    session = cookie.split(";")[0].split("=", 1)[1]
    assert _call(url, "/api/me", headers=_as(session))[1]["viewer"]["name"] == "Vic"

    status, headers, page = _raw(url, f"/signin?code={code}", headers=REMOTE)  # a code works once
    assert status == 400 and b"already used" in page and "Set-Cookie" not in headers
    status, _, page = _raw(url, f"/signin?code={code}", headers={**REMOTE, "Accept-Language": "ja,en;q=0.8"})
    assert "使用済み".encode() in page and "サインインできませんでした".encode() in page
    status, _, page = _raw(url, "/signin?code=%3Cscript%3E", headers=REMOTE)
    assert status == 400 and b"<script>" not in page

    signin = people.signin_code(conn, team["bob"])  # https through a trusted proxy: the cookie is Secure
    status, headers, _ = _raw(url, f"/signin?code={signin}", headers={**REMOTE, "X-Forwarded-Proto": "https"})
    assert status == 302 and "Secure" in headers["Set-Cookie"]
    app.cfg.server_trusted_proxies = ["10.0.0.1"]  # from anyone else, X-Forwarded-Proto is not believed
    signin = people.signin_code(conn, team["bob"])
    status, headers, _ = _raw(url, f"/signin?code={signin}", headers={**REMOTE, "X-Forwarded-Proto": "https"})
    assert status == 302 and "Secure" not in headers["Set-Cookie"]


def test_company_sign_in_header(team):
    url, app = team["url"], team["app"]
    app.cfg.server_auth_header = "X-Auth-Email"
    code, me = _call(url, "/api/me", headers={**REMOTE, "X-Auth-Email": "BOB@example.com"})
    assert code == 200 and me["viewer"]["name"] == "Bob"
    code, r = _call(url, "/api/me", headers={**REMOTE, "X-Auth-Email": "eve@example.com"})
    assert code == 403 and "not on this hub" in r["error"]
    app.cfg.server_trusted_proxies = ["10.0.0.1"]  # the header is believed only from a trusted proxy
    assert _call(url, "/api/me", headers={**REMOTE, "X-Auth-Email": "bob@example.com"})[0] == 401


def test_people_api_and_its_audit(team):
    url, s, app = team["url"], team["sessions"], team["app"]
    ada = _as(s["Ada"])
    assert _call(url, "/api/people/add", {"name": "Cy", "email": "cy@example.com"}, _as(s["Bob"]))[0] == 403
    code, r = _call(url, "/api/people/add", {"name": "Cy", "email": "cy@example.com", "role": "member", "projects": "all"}, ada)
    assert code == 200 and r["person"]["role"] == "member" and r["expires_at"] and r["note"]
    assert r["link"].endswith(f"/signin?code={r['code']}") and f"--code {r['code']} --share knowledge" in r["join"]
    cy = r["person"]["id"]
    code, r = _call(url, "/api/people/add", {"name": "Cy", "email": "cy@example.com", "projects": "all"}, ada)
    assert code == 400 and "already on this hub" in r["error"]

    app.cfg.hub_address = "https://hub.example.com"
    code, r = _call(url, "/api/people/invite", {"id": cy}, ada)
    assert r["join"] == f"chronicle hub join https://hub.example.com --code {r['code']} --share knowledge"
    assert r["link"] == f"https://hub.example.com/signin?code={r['code']}" and "note" not in r
    code, r = _call(url, "/api/people/role", {"id": cy, "role": "readonly"}, ada)
    assert code == 200 and {p["name"]: p["role"] for p in r["people"]}["Cy"] == "readonly"
    code, r = _call(url, "/api/people/role", {"id": team["ada"]["id"], "role": "member"},
                    {**ada, "X-Chronicle-Lang": "ja"})
    assert code == 400 and r["error"] == "このハブの最後の管理者です。先にほかの人を管理者にしてください"
    assert _call(url, "/api/people/revoke", {"id": cy, "token": "f" * 16}, ada)[0] == 400
    code, r = _call(url, "/api/people/remove", {"id": cy}, ada)
    assert code == 200 and "Cy" not in [p["name"] for p in r["people"]]
    assert _call(url, "/api/people/remove", {"id": "x"}, ada)[0] == 400

    code, info = _call(url, "/api/people", headers=ada)
    assert code == 200 and info["roles"] == ["admin", "member", "readonly"] and info["shared_token"] is True
    by_ada = [(a["action"], a["actor_name"]) for a in info["audit"] if a["actor_name"] == "Ada"]
    assert ("add", "Ada") in by_ada and ("role", "Ada") in by_ada and ("remove", "Ada") in by_ada
    code, r = _call(url, "/api/people/shared-token", {"on": False}, ada)
    assert code == 200 and r["shared_token"] is False and load_config(team["cfg"].home).hub_shared_token is False
    assert r["audit"][0]["action"] == "shared-token"


def test_person_tokens_on_the_hub_api(team):
    url, conn, token = team["url"], team["conn"], team["token"]

    def api(path, body, bearer):
        return _call(url, path, body, {"Authorization": f"Bearer {bearer}"})

    code = people.invite(conn, team["bob"]["id"])
    status, r = _call(url, "/api/hub/join", {"code": code, "machine": MACHINE, "name": "Bob laptop"})
    assert status == 200 and r["person"]["name"] == "Bob"
    bob_token = r["token"]
    assert _call(url, "/api/hub/join", {"code": code, "machine": MACHINE})[0] == 400  # used
    assert api("/api/hub/done", {"machine": MACHINE}, bob_token) == (200, {"ok": True})
    assert api("/api/hub/done", {"machine": OTHER}, bob_token)[0] == 401  # issued to another computer
    assert api("/api/hub/done", {"machine": MACHINE}, "nope")[0] == 401

    status, r = api("/api/hub/signin", {"machine": MACHINE}, bob_token)
    assert status == 200 and _raw(url, f"/signin?code={r['code']}", headers=REMOTE)[0] == 302
    status, r = api("/api/hub/signin", {"machine": MACHINE}, token)
    assert status == 400 and "join with an invite" in r["error"]

    people.set_role(conn, team["bob"]["id"], "readonly")
    status, r = api("/api/hub/done", {"machine": MACHINE}, bob_token)
    assert status == 403 and r["error"] == "read-only people can't send to the hub"
    assert api("/api/hub/signin", {"machine": MACHINE}, bob_token)[0] == 200  # still opens the dashboard

    assert api("/api/hub/done", {"machine": MACHINE}, token)[0] == 200  # the shared token, while it's on
    set_config_value(team["cfg"], "hub", "shared_token", "false")
    assert api("/api/hub/done", {"machine": MACHINE}, token)[0] == 401


def test_a_proxy_on_the_hub_itself_is_not_someone_here(hubweb):
    url, app = hubweb["url"], hubweb["app"]
    for header in ("X-Forwarded-Proto", "X-Real-IP", "Forwarded"):  # added by a proxy: not someone at this computer
        code, dv = _call(url, "/api/devices", headers={header: "https" if header == "X-Forwarded-Proto" else "for=1.2.3.4",
                                                       "Tailscale-User-Login": "me@github"})
        assert code == 200 and not dv["here"] and not dv["can_admin"], header
        code, dv = _call(url, "/api/devices", headers={header: "https" if header == "X-Forwarded-Proto" else "for=1.2.3.4"})
        assert code == 403 and dv["nobody"] is True, header  # nginx in front, say: no people, no way in
    app.cfg.server_behind_proxy = True  # nginx's default: the hub's own Host and no forwarding headers at all
    code, dv = _call(url, "/api/devices")
    assert code == 403 and dv["nobody"] is True  # no people, so no sign-in: nobody through the proxy gets in
    assert _call(url, "/api/team-store/save", {"enabled": False})[0] == 403
    assert _call(url, "/api/update", {})[0] == 403
    people.add(hubweb["conn"], "Ada", "ada@example.com", "admin")
    code, r = _call(url, "/api/overview")
    assert code == 401 and r["signin"] is True  # with people, everyone through the proxy signs in


def test_tailscale_logins_and_people(team):
    """[server] allowed_users keeps others out of a hub without people; with people, people.py says who is who."""
    url, s, app = team["url"], team["sessions"], team["app"]
    app.cfg.server_allowed_users = ["me@github"]
    assert _call(url, "/api/me", headers=_as(s["Bob"]))[1]["viewer"]["name"] == "Bob"
    code, r = _call(url, "/api/overview", headers=REMOTE)
    assert code == 401 and r["signin"] is True
    signin = people.signin_code(team["conn"], team["vic"])
    assert _raw(url, f"/signin?code={signin}", headers=REMOTE)[0] == 302
    assert _call(url, "/api/suggestions/seen", {}, _as(s["Ada"])) == (200, {"ok": True})
