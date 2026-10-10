- **Chronicle in the menu bar:** on macOS the dashboard that runs at login now puts Chronicle's mark in the menu bar
  (with the `app` extra installed). The icon stays plain while all is well, gets a dot while it syncs or analyzes, a
  "!" when a sync or a push to the hub failed, and dims while analysis is paused. Its menu says what is happening,
  how many sessions wait for analysis, when knowledge last went to your hub, and lists your five most recent sessions
  to open, with Search Sessions, Open Dashboard, Sync Now, and Update when one is out. The desktop app's menu is now
  the same, with its own items added. Turn it off with `chronicle config set server.menu_bar false`.
  [The menu-bar icon](docs/install.md#the-menu-bar-icon)
