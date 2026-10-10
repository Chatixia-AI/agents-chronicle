"""The menu-bar item on macOS: Chronicle's mark, which says at a glance whether it is working or needs a look, and a
menu with the status, the recent sessions and the way into the dashboard.

`chronicle ui` shows it when launchd runs it as the login item (or with --menu-bar), and Chronicle.app (desktop.py)
shows the same menu with its own items added. What the menu says is worked out without AppKit (snapshot(),
summarize()); StatusMenu draws it.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

from .config import Config
from .util import parse_ts, to_iso, utcnow

log = logging.getLogger("chronicle.menubar")

OK, WORKING, ATTENTION, PAUSED = "ok", "working", "attention", "paused"
RECENT_N = 5
POLL_S = 30  # how often the icon catches up with what other processes did
POLL_BUSY_S = 4  # while something runs, so the icon settles soon after it ends
TITLE_MAX = 48
# imported chats are not work done on this computer; the hub's copies of other computers' sessions are ("remote")
RECENT_SKIP = ("history", "chatgpt-export", "claude-ai-export")
JOB_LABELS = {"sync": "Syncing", "push": "Sending to the hub", "import": "Importing chats",
              "screen": "Screening imported chats", "update": "Updating Chronicle", "themes": "Grouping glossary themes",
              "analyze": "Analyzing", "glossary": "Updating the glossary", "review": "Writing the weekly review",
              "synthesize": "Updating knowledge"}


@dataclass
class Snapshot:
    state: str
    headline: str
    detail: str = ""
    hub: str = ""  # a computer that shares knowledge with a hub: what it last sent
    recent: list[dict] = field(default_factory=list)
    update: str | None = None  # the version on offer, "build" for a changed checkout
    syncing: bool = False


def when(iso: str | None, now: datetime | None = None) -> str:
    """'at 14:05' today, 'Oct 8 at 14:05' before."""
    dt = parse_ts(iso)
    if dt is None:
        return ""
    dt, today = dt.astimezone(), (now or utcnow()).astimezone().date()
    return f"at {dt:%H:%M}" if dt.date() == today else f"{dt:%b} {dt.day} at {dt:%H:%M}"


def _short(text: str, n: int = 60) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def summarize(st: dict, *, now: datetime | None = None, analyzing: int = 0, sync_running: bool = False,
              sync_error: str | None = None, push: dict | None = None, hub_name: str | None = None,
              sends_files: bool = False) -> Snapshot:
    """The icon's state and the menu's first two lines, from the dashboard's status (App.status_small()).

    `analyzing`: sessions being analyzed by any process; `sync_running`/`sync_error`: the sync that runs outside the
    dashboard (the app's own loop, or the launchd agent); `push`: a spoke's last push (hub.last_push()),
    `hub_name` what the hub calls itself, `sends_files` whether the hub analyzes this computer's sessions
    (Config.sends_files) or only gets the knowledge learned here."""
    now = now or utcnow()
    jobs = {name: j for name, j in (st.get("jobs") or {}).items() if j.get("state") == "running"}
    failed = (st.get("jobs") or {}).get("sync") or {}
    syncing = sync_running or "sync" in jobs or "push" in jobs
    queued = 0 if sends_files else int((st.get("pending") or {}).get("queued") or 0)  # else the hub analyzes them
    detail = f"{queued} session{'' if queued == 1 else 's'} waiting for analysis" if queued else ""
    hub = (hub_name or urlparse(st["hub_url"]).hostname or st["hub_url"]) if st.get("hub_url") else ""
    sent = when((push or {}).get("at"), now)
    shared = (f"Sharing knowledge with {hub}" + (f" · last sent {sent}" if sent else " · nothing sent yet")
              if hub and not sends_files else "")

    def snap(state: str, headline: str) -> Snapshot:
        return Snapshot(state, headline, detail, shared, update=(st.get("update") or {}).get("to"), syncing=syncing)

    if sync_error:
        return snap(ATTENTION, f"Sync failed: {_short(sync_error)}")
    if failed.get("state") == "error":
        return snap(ATTENTION, f"Sync failed: {_short(failed.get('result') or 'see the logs')}")
    if push and push.get("errors"):
        return snap(ATTENTION, f"Sending to the hub failed: {_short(push['errors'][0])}")
    if jobs or syncing or analyzing:
        name, job = next(iter(jobs.items()), ("sync" if syncing else "analyze", {}))
        label = JOB_LABELS.get(name.split(":", 1)[0], "Working")
        if job.get("total"):
            return snap(WORKING, f"{label} {job.get('done') or 0} of {job['total']}…")
        if label == "Analyzing" and analyzing:
            return snap(WORKING, f"Analyzing {analyzing} session{'' if analyzing == 1 else 's'}…")
        return snap(WORKING, f"{label}…")
    paused = st.get("paused_until")
    if paused and paused > to_iso(now):
        return snap(PAUSED, f"Analysis paused until {when(paused, now).removeprefix('at ')}")
    if hub and sends_files:
        return snap(OK, f"Sending to {hub}" + (f" · last sent {sent}" if sent else " · nothing sent yet"))
    at = when(st.get("last_sync"), now)
    return snap(OK, f"Synced {at}" if at else "Not synced yet")


def recent_sessions(conn, n: int = RECENT_N) -> list[dict]:
    marks = ",".join("?" * len(RECENT_SKIP))
    return [dict(r) for r in conn.execute(
        f"SELECT id, title, project_name, COALESCE(ended_at, started_at) at FROM sessions "
        f"WHERE source NOT IN ({marks}) AND COALESCE(ended_at, started_at) IS NOT NULL "
        f"ORDER BY COALESCE(ended_at, started_at) DESC LIMIT ?", [*RECENT_SKIP, n])]


def snapshot(app, *, sync_running: bool = False, sync_error: str | None = None) -> Snapshot:
    """What the menu shows now. `app`: the dashboard's server.App, read on the caller's thread."""
    from .hub import last_folders, last_push

    try:
        app.refresh_config()
        st = app.status_small()
        conn = app.conn
        analyzing = conn.execute("SELECT COUNT(*) FROM sessions WHERE analysis_status = 'running'").fetchone()[0]
        spoke = app.cfg.is_spoke
        snap = summarize(st, analyzing=analyzing, sync_running=sync_running, sync_error=sync_error,
                         push=last_push(app.cfg) if spoke else None, sends_files=app.cfg.sends_files,
                         hub_name=(last_folders(app.cfg) or {}).get("hub") if spoke else None)
        snap.recent = recent_sessions(conn)
        return snap
    finally:
        app.release()  # no read transaction held between polls


def agent_sync_error() -> str | None:
    """The launchd sync agent's last run, when it failed (the login item's own sync runs there, not in the menu)."""
    from .install import background_status

    info = background_status()
    code = str(info.get("last_exit") or "0")
    if not info.get("loaded") or code in ("0", "(never exited)"):
        return None
    return f"the background sync exited with code {code} (see sync.err.log)"


def wants_menu_bar(cfg: Config) -> bool:
    """`chronicle ui` shows the icon by itself only as the login item, so a second dashboard run from a terminal
    (or a checkout's dev server) adds no second icon."""
    from .install import UI_LABEL

    return (sys.platform == "darwin" and cfg.server_menu_bar
            and os.environ.get("XPC_SERVICE_NAME") == UI_LABEL)


# ---------------------------------------------------------------------------------------------- AppKit from here on
def alert(title: str, text: str, buttons: list[str]) -> int:
    """Modal alert from a background thread; returns the index of the button pressed."""
    import AppKit
    from PyObjCTools import AppHelper

    done, result = threading.Event(), [0]

    def run():
        try:
            a = AppKit.NSAlert.alloc().init()
            a.setMessageText_(title)
            a.setInformativeText_(text)
            for b in buttons:
                a.addButtonWithTitle_(b)
            AppKit.NSApp.activateIgnoringOtherApps_(True)
            result[0] = int(a.runModal()) - AppKit.NSAlertFirstButtonReturn
        finally:
            done.set()

    AppHelper.callAfter(run)
    done.wait()
    return result[0]


def mark(state: str = OK, size: float = 18.0):
    """Chronicle's mark as a template image (macOS tints it for the menu bar): the stack of pages from the app icon,
    with a dot while it works, a "!" when it needs a look, and dimmed while analysis is paused."""
    import AppKit

    def draw(rect) -> bool:
        s = size / 18.0
        AppKit.NSColor.blackColor().set()

        def page(x, y, w, h, fold=0.0):
            p = AppKit.NSBezierPath.bezierPath()
            p.moveToPoint_((x * s, y * s))
            p.lineToPoint_(((x + w - fold) * s, y * s))
            p.lineToPoint_(((x + w) * s, (y + fold) * s))
            p.lineToPoint_(((x + w) * s, (y + h) * s))
            p.lineToPoint_((x * s, (y + h) * s))
            p.closePath()
            p.setLineWidth_(1.3 * s)
            p.setLineJoinStyle_(AppKit.NSLineJoinStyleRound)
            return p

        def clear(path) -> None:
            ctx = AppKit.NSGraphicsContext.currentContext()
            ctx.saveGraphicsState()
            ctx.setCompositingOperation_(AppKit.NSCompositingOperationClear)
            path.fill()
            ctx.restoreGraphicsState()

        badge = state in (WORKING, ATTENTION)
        for x, y in ((8.2, 1.2), (5.4, 2.6)):  # the pages behind, each covering the one before
            back = page(x, y, 8.4, 11.6)
            clear(back)
            back.stroke()
        front = page(1.6, 4.4, 9.8, 12.8, fold=3.0)
        clear(front)
        front.stroke()
        for y in (10.2, 13.0):  # the two lines on the front page
            line = AppKit.NSBezierPath.bezierPath()
            line.moveToPoint_((4.2 * s, y * s))
            line.lineToPoint_((8.8 * s, y * s))
            line.setLineWidth_(1.3 * s)
            line.setLineCapStyle_(AppKit.NSLineCapStyleRound)
            line.stroke()
        if badge:
            r = 3.0 if state == WORKING else 4.0
            cx, cy = 18.0 - r, 18.0 - r
            ring = AppKit.NSBezierPath.bezierPathWithOvalInRect_((((cx - r - 1.4) * s, (cy - r - 1.4) * s),
                                                                  ((2 * r + 2.8) * s, (2 * r + 2.8) * s)))
            clear(ring)
            AppKit.NSBezierPath.bezierPathWithOvalInRect_((((cx - r) * s, (cy - r) * s), (2 * r * s, 2 * r * s))).fill()
            if state == ATTENTION:  # a "!" cut out of the dot
                clear(AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                    (((cx - 0.6) * s, (cy - 2.6) * s), (1.2 * s, 3.2 * s)), 0.6 * s, 0.6 * s))
                clear(AppKit.NSBezierPath.bezierPathWithOvalInRect_((((cx - 0.65) * s, (cy + 1.2) * s),
                                                                     (1.3 * s, 1.3 * s))))
        return True

    image = AppKit.NSImage.imageWithSize_flipped_drawingHandler_((size, size), True, draw)
    if state == PAUSED:  # a template image keeps its alpha: dimmed, as macOS shows an inactive item
        full = image

        def dimmed(rect) -> bool:
            full.drawInRect_fromRect_operation_fraction_(rect, AppKit.NSZeroRect,
                                                         AppKit.NSCompositingOperationSourceOver, 0.45)
            return True

        image = AppKit.NSImage.imageWithSize_flipped_drawingHandler_((size, size), False, dimmed)
    image.setTemplate_(True)
    return image


@dataclass
class Extra:
    """An item an embedding app adds above Quit (Chronicle.app: Connect Claude Code, Open at Login, …)."""
    key: str
    title: str
    action: object  # a callable, run on a background thread
    visible: object = None  # a callable returning bool, asked whenever the menu opens
    checked: object = None


_TARGET_CLASS = None


def _target_class():
    """NSObject subclass receiving the menu's actions (ObjC classes can only be defined once per process)."""
    global _TARGET_CLASS
    if _TARGET_CLASS is None:
        import AppKit

        class ChronicleStatusTarget(AppKit.NSObject):
            def act_(self, sender):
                self.owner.act(str(sender.representedObject()))

            def menuWillOpen_(self, menu):
                self.owner.will_open()

        _TARGET_CLASS = ChronicleStatusTarget
    return _TARGET_CLASS


class StatusMenu:
    """The menu-bar item. `open_page(hash)` opens a dashboard page ("#/", "#/session/<id>"), `refresh()` returns a
    Snapshot (run on the poll thread), `sync_now()` and `quit()` run on a background thread. Main thread: install()."""

    def __init__(self, *, refresh, open_page, sync_now, quit, open_title: str = "Open Dashboard",
                 extras: list[Extra] | None = None):
        self.refresh, self.open_page, self.sync_now, self.quit = refresh, open_page, sync_now, quit
        self.open_title = open_title
        self.extras = extras or []
        self.items: dict = {}
        self.recent_items: list = []
        self.snap: Snapshot | None = None
        self.wake = threading.Event()
        self.images: dict = {}

    # -------------------------------------------------------------- building (main thread)
    def install(self) -> None:
        import AppKit

        self.target = _target_class().alloc().init()
        self.target.owner = self
        menu = AppKit.NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.setDelegate_(self.target)
        self.menu = menu

        def add(key, title, enabled=True, quit_key=""):
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "act:" if enabled else None,
                                                                                quit_key)
            item.setTarget_(self.target)
            item.setRepresentedObject_(key)
            item.setEnabled_(enabled)
            menu.addItem_(item)
            self.items[key] = item
            return item

        add("headline", "Starting…").setToolTip_("Open the Activity page")
        add("detail", "", enabled=False).setHidden_(True)
        add("hub", "", enabled=False).setHidden_(True)
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        header = (AppKit.NSMenuItem.sectionHeaderWithTitle_("Recent Sessions")
                  if hasattr(AppKit.NSMenuItem, "sectionHeaderWithTitle_") else None)
        if header is None:
            header = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Recent Sessions", None, "")
            header.setEnabled_(False)
        menu.addItem_(header)
        self.items["recent"] = header
        self.items["recent_sep"] = AppKit.NSMenuItem.separatorItem()
        menu.addItem_(self.items["recent_sep"])
        add("search", "Search Sessions…")
        add("open", self.open_title)
        add("sync", "Sync Now")
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        add("update", "Update Chronicle…").setHidden_(True)
        for extra in self.extras:
            add(f"extra:{extra.key}", extra.title)
        if self.extras:
            menu.addItem_(AppKit.NSMenuItem.separatorItem())
        add("quit", "Quit Chronicle", quit_key="q")

        self.status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
            AppKit.NSVariableStatusItemLength)
        self.status_item.setMenu_(menu)
        self.status_item.button().setImage_(self._image(OK))
        self.status_item.button().setToolTip_("Chronicle")
        self.will_open()
        threading.Thread(target=self._poll, name="chronicle-menubar", daemon=True).start()

    def _image(self, state: str):
        if state not in self.images:
            self.images[state] = mark(state)
        return self.images[state]

    # -------------------------------------------------------------- keeping it current
    def poke(self) -> None:
        """Something changed (a sync started or ended): refresh now instead of at the next poll."""
        self.wake.set()

    def _poll(self) -> None:
        from PyObjCTools import AppHelper

        while True:
            self.wake.clear()
            try:
                snap = self.refresh()
            except Exception:
                log.exception("menu-bar refresh failed")
                snap = None
            if snap is not None:
                AppHelper.callAfter(self.apply, snap)
            self.wake.wait(POLL_BUSY_S if snap is not None and snap.state == WORKING else POLL_S)

    def apply(self, snap: Snapshot) -> None:
        """Main thread: show a snapshot (also while the menu is open: NSMenu redraws the items it changes)."""
        import AppKit

        self.snap = snap
        button = self.status_item.button()
        button.setImage_(self._image(snap.state))
        button.setToolTip_(f"Chronicle: {snap.headline}")
        button.setAccessibilityLabel_(f"Chronicle, {snap.headline}")
        self.items["headline"].setTitle_(snap.headline)
        self.items["detail"].setTitle_(snap.detail)
        self.items["detail"].setHidden_(not snap.detail)
        self.items["hub"].setTitle_(snap.hub)
        self.items["hub"].setHidden_(not snap.hub)
        self.items["sync"].setEnabled_(not snap.syncing)
        self.items["update"].setHidden_(not snap.update)
        if snap.update:
            self.items["update"].setTitle_("Update Available…" if snap.update == "build"
                                           else f"Update to {snap.update}…")

        for item in self.recent_items:
            self.menu.removeItem_(item)
        self.recent_items = []
        at = self.menu.indexOfItem_(self.items["recent"]) + 1
        for i, s in enumerate(snap.recent):
            title = _short(s.get("title") or "(untitled session)", TITLE_MAX)
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "act:", "")
            item.setTarget_(self.target)
            item.setRepresentedObject_(f"session:{s['id']}")
            sub = " · ".join(x for x in (s.get("project_name"), when(s.get("at")).removeprefix("at ")) if x)
            if sub and item.respondsToSelector_("setSubtitle:"):  # macOS 14.4+
                item.setSubtitle_(sub)
            elif sub:
                item.setToolTip_(sub)
            self.menu.insertItem_atIndex_(item, at + i)
            self.recent_items.append(item)
        self.items["recent"].setHidden_(not snap.recent)
        self.items["recent_sep"].setHidden_(not snap.recent)

    def will_open(self) -> None:
        """Main thread, as the menu opens: the embedding app's items, and a fresh snapshot on its way."""
        import AppKit

        for extra in self.extras:
            item = self.items[f"extra:{extra.key}"]
            try:
                item.setHidden_(bool(extra.visible) and not extra.visible())
                if extra.checked:
                    item.setState_(AppKit.NSControlStateValueOn if extra.checked() else AppKit.NSControlStateValueOff)
            except Exception:
                log.exception("menu item %s", extra.key)
        self.poke()

    # -------------------------------------------------------------- actions
    def act(self, key: str) -> None:
        """Main thread: hand the action to a thread, since it may wait (an alert, the browser, a job)."""
        if key.startswith("session:"):
            fn = lambda: self.open_page(f"#/session/{key.split(':', 1)[1]}")  # noqa: E731
        elif key.startswith("extra:"):
            fn = next(e.action for e in self.extras if f"extra:{e.key}" == key)
        else:
            fn = {"headline": lambda: self.open_page("#/"), "search": lambda: self.open_page("#/search"),
                  "open": lambda: self.open_page("#/"), "update": lambda: self.open_page("#/status"),
                  "sync": self._sync, "quit": self.quit}.get(key)
        if fn is not None:
            threading.Thread(target=self._safely, args=(fn,), daemon=True).start()

    def _safely(self, fn) -> None:
        try:
            fn()
        except Exception:
            log.exception("menu-bar action failed")

    def _sync(self) -> None:
        self.sync_now()
        self.poke()


# ---------------------------------------------------------------------------------------------- `chronicle ui`
def run_with_server(cfg: Config, httpd, url: str) -> bool:
    """`chronicle ui` with the menu-bar item: the dashboard serves on a thread, AppKit runs on this (main) thread
    until Quit or Ctrl+C. False, with nothing started, when the `app` extra (PyObjC) is not installed."""
    try:
        import AppKit
        from PyObjCTools import AppHelper
    except ImportError:
        log.info("no menu-bar icon: it needs the `app` extra (uv tool install 'agents-chronicle[app]')")
        return False
    from .install import UI_LABEL

    app = httpd.app
    AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    threading.Thread(target=httpd.serve_forever, name="chronicle-ui", daemon=True).start()

    def quit_() -> None:
        if os.environ.get("XPC_SERVICE_NAME") == UI_LABEL:  # launchd would start a KeepAlive agent right back up
            if alert("Quit Chronicle?",
                     "The dashboard and this icon stop until you next log in, or until you run `chronicle ui`. "
                     "Your sessions are still recorded.", ["Quit", "Cancel"]) != 0:
                return
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{UI_LABEL}"], capture_output=True)
        AppHelper.callAfter(AppKit.NSApp.terminate_, None)

    menu = StatusMenu(refresh=lambda: snapshot(app, sync_error=agent_sync_error()),
                      open_page=lambda page: webbrowser.open(url + page), sync_now=app.action_sync, quit=quit_)
    AppHelper.callAfter(menu.install)
    log.info("menu-bar icon on, dashboard at %s", url)
    AppHelper.runEventLoop(installInterrupt=True)
    return True
