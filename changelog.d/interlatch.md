- **Chronicle is now Interlatch:** the same program under a new name. Install it with `uv tool install interlatch`
  (the app is `Interlatch-<version>-arm64.dmg`) and run it as `interlatch`; `chronicle` still works. An existing
  install moves over by itself: the data folder becomes `~/.interlatch`, the MCP server `interlatch` in every agent,
  and hooks, login items and permissions follow; `CHRONICLE_*` variables are still read. The docs are at
  [interlatch.com/docs](https://interlatch.com/docs/) ([Moving from Chronicle](docs/moving-from-chronicle.md)).
