"""Chronicle.app (macOS): the dashboard in a native window, a menu-bar item, and the background sync.

The app does what `chronicle install` sets up launchd for: it serves the dashboard and runs `sync --work`
every 15 minutes while it is running (it opens at login). Claude Code's hooks and MCP registration point at
a shim (~/.claude-chronicle/bin/chronicle) that the app rewrites on every launch, so they survive the app
being moved or updated. Needs the `app` extra (pywebview + PyObjC).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .config import Config, load_config

log = logging.getLogger("chronicle.desktop")

SYNC_INTERVAL_S = 15 * 60
FIRST_SYNC_DELAY_S = 20
ONBOARDED_KEY = "app_onboarded"
EXTRA_PATH = ("/opt/homebrew/bin", "/usr/local/bin", "~/.local/bin")
CLI_LINK = "~/.local/bin/chronicle"


def adopt_login_path() -> None:
    """Apps opened from Finder get PATH=/usr/bin:/bin:/usr/sbin:/sbin, but `claude` (and the node an npm
    install of it needs) live elsewhere. Take PATH from the user's login shell, as a terminal would have it."""
    dirs = os.environ.get("PATH", "").split(os.pathsep)
    shell = os.environ.get("SHELL") or "/bin/zsh"
    try:
        out = subprocess.run([shell, "-ilc", 'printf "__PATH__%s__PATH__" "$PATH"'], capture_output=True,
                             text=True, timeout=10, stdin=subprocess.DEVNULL).stdout
        if out.count("__PATH__") >= 2:
            dirs = out.split("__PATH__")[1].split(os.pathsep) + dirs
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("could not read PATH from %s: %s", shell, exc)
    dirs += [str(Path(d).expanduser()) for d in EXTRA_PATH]
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(d for d in dirs if d))


def in_temporary_location(exe: str | None = None) -> bool:
    """Running from a mounted disk image or a quarantined (translocated) copy, not from where it will stay."""
    exe = exe or sys.executable
    return "/AppTranslocation/" in exe or exe.startswith("/Volumes/")


class Background:
    """`chronicle sync --work` every 15 minutes, on a thread; the file locks keep it from overlapping with a
    hook-spawned run or a launchd agent left over from a CLI install."""

    def __init__(self, on_change):
        self.on_change = on_change
        self.wake = threading.Event()
        self.running = False
        self.last: float | None = None
        self.error: str | None = None

    def start(self) -> None:
        threading.Thread(target=self._loop, name="chronicle-sync", daemon=True).start()

    def sync_now(self) -> None:
        self.wake.set()

    def _loop(self) -> None:
        self.wake.wait(FIRST_SYNC_DELAY_S)
        while True:
            self.wake.clear()
            self.run_once()
            self.wake.wait(SYNC_INTERVAL_S)

    def run_once(self) -> None:
        from .db import connect
        from .ingest import sync
        from .worker import run_worker

        self.running = True
        self.on_change()
        try:
            cfg = load_config()
            cfg.ensure_dirs()
            conn = connect(cfg.db_path)
            try:
                report = sync(cfg, conn)
            finally:
                conn.close()
            work = run_worker(cfg)
            log.info("app sync: %s · work: %s", report.summary(), work.summary())
            self.error = None
        except Exception as exc:
            log.exception("app sync failed")
            self.error = str(exc)
        finally:
            self.running = False
            self.last = time.time()
            self.on_change()

    def describe(self) -> str:
        if self.running:
            return "Syncing…"
        if self.error:
            return f"Last sync failed: {self.error[:60]}"
        if self.last:
            return "Last sync " + time.strftime("%H:%M", time.localtime(self.last))
        return "First sync starts shortly"


_TARGET_CLASS = None


def _menu_target_class():
    """NSObject subclass receiving the menu-bar actions (ObjC classes can only be defined once per process)."""
    global _TARGET_CLASS
    if _TARGET_CLASS is None:
        import AppKit

        class ChronicleMenuTarget(AppKit.NSObject):
            def openWindow_(self, sender):
                self.app.show_window()

            def openInBrowser_(self, sender):
                webbrowser.open(self.app.url)

            def syncNow_(self, sender):
                self.app.bg.sync_now()

            def connectClaude_(self, sender):
                self.app.in_background(self.app.connect_claude)

            def toggleLoginItem_(self, sender):
                self.app.in_background(self.app.toggle_login_item)

            def installCLI_(self, sender):
                self.app.in_background(self.app.install_cli)

            def openDataFolder_(self, sender):
                subprocess.Popen(["open", str(self.app.cfg.home)])

            def quit_(self, sender):
                AppKit.NSApp.terminate_(None)

            def menuWillOpen_(self, menu):
                self.app.update_menu()

        _TARGET_CLASS = ChronicleMenuTarget
    return _TARGET_CLASS


class DesktopApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.frozen = bool(getattr(sys, "frozen", False))
        self.quitting = False
        self.window = None
        self.url = ""
        self.items: dict = {}
        self.bg = Background(self._menu_changed)

    # ------------------------------------------------------------------ lifecycle
    def run(self) -> int:
        import webview

        from .install import write_shim
        from .server import make_server

        adopt_login_path()
        if self.frozen:
            write_shim(sys.executable)
        httpd = make_server(self.cfg, any_port=True)
        self.url = f"http://127.0.0.1:{httpd.server_address[1]}/"
        threading.Thread(target=httpd.serve_forever, name="chronicle-ui", daemon=True).start()
        log.info("app started (%s), dashboard at %s", sys.executable, self.url)

        self._install_app_delegate()
        self.window = webview.create_window("Chronicle", self.url, width=1440, height=920, min_size=(900, 600),
                                            text_select=True, zoomable=True)
        self.window.events.closing += self._on_closing
        self.bg.start()
        webview.start(self._started, private_mode=False, storage_path=str(self.cfg.home / "webview"))
        httpd.shutdown()
        return 0

    def _install_app_delegate(self) -> None:
        """Extend pywebview's NSApplication delegate: Quit really quits (closing the window only hides it),
        and clicking the Dock icon brings the window back."""
        import objc
        from webview.platforms.cocoa import BrowserView

        app = self
        base = BrowserView.AppDelegate

        class ChronicleAppDelegate(base):
            def applicationShouldTerminate_(self, nsapp):
                app.quitting = True
                return objc.super(ChronicleAppDelegate, self).applicationShouldTerminate_(nsapp)

            def applicationShouldHandleReopen_hasVisibleWindows_(self, nsapp, flag):
                app.show_window()
                return True

        BrowserView.AppDelegate = ChronicleAppDelegate

    def _started(self) -> None:
        from PyObjCTools import AppHelper

        AppHelper.callAfter(self._build_status_item)
        try:
            self.onboard()
        except Exception:
            log.exception("onboarding failed")

    def _on_closing(self):
        if self.quitting:
            return True
        import AppKit
        from PyObjCTools import AppHelper

        self.window.hide()  # keep running in the menu bar, without a Dock icon
        AppHelper.callAfter(AppKit.NSApp.setActivationPolicy_, AppKit.NSApplicationActivationPolicyAccessory)
        return False

    def show_window(self) -> None:
        import AppKit
        from PyObjCTools import AppHelper

        def show():
            AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            self.window.show()

        AppHelper.callAfter(show)

    def in_background(self, fn) -> None:
        """Menu actions run on the main thread; anything that may show an alert or wait goes to a thread."""
        threading.Thread(target=fn, daemon=True).start()

    # ------------------------------------------------------------------ menu bar
    def _build_status_item(self) -> None:
        import AppKit

        target = _menu_target_class().alloc().init()
        target.app = self
        menu = AppKit.NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        menu.setDelegate_(target)

        def add(key, title, action=None, key_equiv=""):
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key_equiv)
            if action:
                item.setTarget_(target)
            else:
                item.setEnabled_(False)
            menu.addItem_(item)
            self.items[key] = item

        add("open", "Open Chronicle", "openWindow:")
        add("browser", "Open in Browser", "openInBrowser:")
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        add("status", self.bg.describe())
        add("sync", "Sync Now", "syncNow:")
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        add("connect", "Connect Claude Code…", "connectClaude:")
        add("login", "Open at Login", "toggleLoginItem:")
        add("cli", "Install Command-Line Tool", "installCLI:")
        add("data", "Open Data Folder", "openDataFolder:")
        menu.addItem_(AppKit.NSMenuItem.separatorItem())
        add("quit", "Quit Chronicle", "quit:", "q")

        item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_("books.vertical", "Chronicle")
        if image is not None:
            image.setTemplate_(True)
            item.button().setImage_(image)
        else:
            item.button().setTitle_("Chronicle")
        item.setMenu_(menu)
        self._status_item, self._menu_target = item, target  # keep references alive
        self.update_menu()

    def _menu_changed(self) -> None:
        if self.items:
            from PyObjCTools import AppHelper

            AppHelper.callAfter(self.update_menu)

    def update_menu(self) -> None:
        """Main thread only (menuWillOpen: and callAfter)."""
        import AppKit

        from .install import hooks_installed

        self.items["status"].setTitle_(self.bg.describe())
        self.items["sync"].setEnabled_(not self.bg.running)
        self.items["connect"].setHidden_(bool(hooks_installed(self.cfg).get("SessionEnd")))
        self.items["login"].setHidden_(not self.frozen)
        self.items["cli"].setHidden_(not self.frozen)
        if self.frozen:
            on = self.login_item_status() == "enabled"
            self.items["login"].setState_(AppKit.NSControlStateValueOn if on else AppKit.NSControlStateValueOff)

    # ------------------------------------------------------------------ dialogs
    def alert(self, title: str, text: str, buttons: list[str]) -> int:
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

    # ------------------------------------------------------------------ setup
    def onboard(self) -> None:
        """First launch: offer to connect Claude Code (hooks + MCP). Asked once; the menu keeps the option."""
        from .db import connect, kv_get, kv_set
        from .install import hooks_installed

        if self.frozen and in_temporary_location():
            self.alert("Move Chronicle to Applications",
                       "Chronicle is running from a disk image or a temporary location. Drag it into your "
                       "Applications folder and open it from there, so it stays available to Claude Code.", ["OK"])
            return
        if hooks_installed(self.cfg).get("SessionEnd"):
            return
        conn = connect(self.cfg.db_path)
        try:
            if kv_get(conn, ONBOARDED_KEY):
                return
            kv_set(conn, ONBOARDED_KEY, "1")
            conn.commit()
        finally:
            conn.close()
        self.connect_claude(first_run=True)

    def connect_claude(self, first_run: bool = False) -> None:
        from .connectors import connect
        from .install import executable

        if not self.cfg.claude_bin():
            self.alert("Claude Code not found",
                       "Chronicle records your Claude Code sessions and uses your Claude Code login (claude -p) to "
                       "analyze them. Install Claude Code from claude.com/claude-code and sign in, then choose "
                       "“Connect Claude Code…” from Chronicle's menu-bar icon.", ["OK"])
            return
        steps = ["• add a SessionEnd hook to ~/.claude/settings.json (a backup is kept), so each session is "
                 "recorded when it ends",
                 "• register the chronicle MCP server, so Claude can search your past sessions"]
        if self.frozen:
            steps.append("• open Chronicle at login, so sessions are analyzed in the background")
        text = ("Chronicle will:\n" + "\n".join(steps) + "\n\nAnalysis runs through your own Claude Code login "
                "and counts toward your plan's usage. Everything else stays on this Mac.")
        if self.alert("Connect Claude Code?", text, ["Connect", "Not Now"]) != 0:
            return
        for action in connect(self.cfg, "claude", executable()):
            log.info("connect: %s", action)
        if self.frozen and self.login_item_status() != "enabled":
            self.set_login_item(True)
        self.bg.sync_now()
        self._menu_changed()
        if first_run:
            self.alert("Claude Code connected",
                       "Chronicle is importing your past sessions now; analysis follows in the background. "
                       "Chronicle stays in the menu bar when you close its window.", ["OK"])

    # ------------------------------------------------------------------ login item (macOS 13+)
    def login_item_status(self) -> str:
        try:
            from ServiceManagement import SMAppService

            status = SMAppService.mainAppService().status()
        except Exception:
            return "unavailable"
        return {0: "not registered", 1: "enabled", 2: "requires approval", 3: "not found"}.get(status, str(status))

    def set_login_item(self, on: bool) -> None:
        from ServiceManagement import SMAppService

        service = SMAppService.mainAppService()
        ok, err = service.registerAndReturnError_(None) if on else service.unregisterAndReturnError_(None)
        if not ok:
            log.warning("login item %s failed: %s", "register" if on else "unregister", err)
            self.alert("Open at Login", f"macOS refused: {err.localizedDescription() if err else 'unknown error'}",
                       ["OK"])
        elif on and self.login_item_status() == "requires approval":
            SMAppService.openSystemSettingsLoginItems()
        self._menu_changed()

    def toggle_login_item(self) -> None:
        self.set_login_item(self.login_item_status() != "enabled")

    # ------------------------------------------------------------------ command-line tool
    def install_cli(self) -> None:
        from .install import shim_path, write_shim

        shim = write_shim(sys.executable)
        link = Path(CLI_LINK).expanduser()
        if link.is_symlink() and link.resolve() == shim.resolve():
            self.alert("Command-line tool", f"`chronicle` is already installed at {CLI_LINK}.", ["OK"])
            return
        if link.exists() or link.is_symlink():
            self.alert("Command-line tool",
                       f"{CLI_LINK} already exists (for example from `uv tool install`), so it was left alone. "
                       f"The app's own command is {shim_path()}.", ["OK"])
            return
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(shim)
        on_path = str(link.parent) in os.environ.get("PATH", "").split(os.pathsep)
        self.alert("Command-line tool", f"Installed `chronicle` at {CLI_LINK}."
                   + ("" if on_path else " Add ~/.local/bin to your PATH to use it."), ["OK"])


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "darwin":
        print("The Chronicle desktop app is macOS-only for now; run `chronicle ui` for the dashboard.", file=sys.stderr)
        return 1
    try:
        import webview  # noqa: F401
    except ImportError:
        print("The desktop app needs the `app` extra: uv tool install 'agents-chronicle[app]'", file=sys.stderr)
        return 1
    from .util import file_lock, setup_logging

    cfg = load_config()
    cfg.ensure_dirs()
    setup_logging(cfg.logs_dir)
    with file_lock(cfg.locks_dir / "app.lock", blocking=False) as got:
        if not got:
            print("Chronicle is already running (see its menu-bar icon).", file=sys.stderr)
            return 0
        return DesktopApp(cfg).run()
