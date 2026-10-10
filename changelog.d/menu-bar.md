- **Chronicle in the menu bar:** on macOS the dashboard that runs at login can now put Chronicle's mark in the menu
  bar (with the `app` extra installed). It's optional: `chronicle install` asks once, off unless you say yes, and
  `chronicle install --menu-bar` turns it on. The icon stays plain while all is well, gets a dot while it syncs or
  analyzes, a "!" when a sync or a push to the hub failed, and dims while analysis is paused. A click opens a panel in
  the dashboard's blueprint style: what is happening (with a progress bar while it works), sessions today, the
  analysis queue and lessons this week, a search across every session as you type, and your recent sessions with their
  agent, project and outcome, a click or ↵ away. A right-click opens a quick menu with Sync Now and Quit. The desktop
  app has the same panel, opening pages in its window. `chronicle install --no-menu-bar` turns it off.
  [The menu-bar icon](docs/install.md#the-menu-bar-icon)
