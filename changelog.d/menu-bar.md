- **Chronicle in the menu bar:** on macOS the dashboard that runs at login now puts Chronicle's mark in the menu bar
  (with the `app` extra installed). The icon stays plain while all is well, gets a dot while it syncs or analyzes, a
  "!" when a sync or a push to the hub failed, and dims while analysis is paused. A click opens a panel in the
  dashboard's blueprint style: what is happening (with a progress bar while it works), sessions today, the analysis
  queue and lessons this week, a search across every session as you type, and your recent sessions with their agent,
  project and outcome, a click or ↵ away. A right-click opens a quick menu with Sync Now and Quit. The desktop app
  has the same panel, opening pages in its window. Turn it off with `chronicle config set server.menu_bar false`.
  [The menu-bar icon](docs/install.md#the-menu-bar-icon)
