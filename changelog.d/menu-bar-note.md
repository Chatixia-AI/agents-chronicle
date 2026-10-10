- **The menu-bar switch shows the icon after it restarts the dashboard:** turning the icon on from **Settings ›
  Status › Recording** (or updating from **Status › Updates**) restarted the dashboard in place, and macOS then kept
  the new icon hidden. On a Mac the dashboard that runs at login is now restarted by launchd, and the icon shows.
  With the icon on, the Status note no longer says it is in the menu bar: it says to check **System Settings › Menu
  Bar**, where the dashboard is listed by its Python (`python3.14`, say), and on a MacBook whether the notch hides
  it ([Troubleshooting](docs/troubleshooting.md#install-and-the-app)).
