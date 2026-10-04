# Roadmap

[← Chronicle](README.md) · [Changelog](CHANGELOG.md) · 日本語: [ROADMAP.ja.md](ROADMAP.ja.md)

What is coming to Chronicle, roughly in the order it will be worked on. Nothing here has a date. Items move between
sections as plans change, and finished work moves to the [changelog](CHANGELOG.md). Last updated 2026-10-02, at
version 0.6.1.

Three rules shape everything below. Chronicle stays local: no server of ours, no telemetry, no account. Analysis
runs through your own Claude Code or Codex login, never a key we hold. And Chronicle should say what it doesn't
know rather than guess.

## Now

### Answers that say what they don't know

These come from reading [OpenRig](https://github.com/mvschwarz/openrig), which handles trust and missing data
carefully.

- **Trust that expires.** An established or canonical item that no session has confirmed for 90 days is shown as
  *seen once* until a new session confirms it. The stored stage doesn't change, so nothing is lost; the window
  will be a setting. Today a lesson about a tool you replaced months ago keeps being offered first.
- **Start-of-session notes that drop whole items.** The notes Chronicle gives Claude Code at the start of a
  session are cut at 3,000 characters, which can end mid-sentence and lose the pointer to the MCP tools. They will
  be filled item by item, most trusted first, and end with how many more there are and how to search for them.
- **Empty search results that say what was searched.** "No sessions matched" can mean it never happened, or that
  Chronicle never saw it: a Claude Code on the web session, a chat newer than your last export, or a session not
  analyzed yet. An empty result will say which sources were searched and which weren't.

### Fixes

- **Desktop app without the command-line install.** When the app is set up on its own, the Status and Sources
  pages report the background sync as off, and `analysis.backfill = false` is ignored on the first sync. Until
  this is fixed, run `~/.claude-chronicle/bin/chronicle install --no-launchd --no-ui` once after connecting your
  agents in the app ([Troubleshooting](docs/troubleshooting.md)).
- **Clicking a new-version notification on macOS** opens Script Editor instead of the dashboard.

### Safer upgrades

- **Named upgrade steps.** The database records one schema version number. When two changes are developed at the
  same time, both can claim the same number and one upgrade step gets skipped (this was caught before 0.6.0). Each
  step will be recorded by name instead, so every step runs exactly once whatever order changes land in.

## Next

- **Phone and other computers, on real hardware.** The hub, Tailscale access and the phone layout are built and
  tested, but so far only with demo data, automated tests and mobile emulation in a desktop browser. They need a
  run on a real tailnet, a real Linux hub and a real iPhone. Fixes from that run will come first.
- **Claude Code on the web.** These sessions aren't in the claude.ai export, and there is no public API for them.
  The only way in today is `claude --teleport <session-id>`, which copies one onto your computer as an ordinary
  transcript. Chronicle will document this path, list it as a missing source in search results, and pick up a
  teleported session as soon as its transcript appears.
- **Knowing when a session has really ended.** Chronicle waits for a session to go quiet before analyzing it.
  Claude Code keeps a small status file for each running session, and reading it would let Chronicle analyze a
  session as soon as it closes and say exactly where it is still running. The file format is undocumented, so the
  quiet-period timer stays as the fallback.
- **Lessons with their reason attached.** Gotchas extracted in a fixed shape: the moment it bites, the reflex that
  goes wrong, what to do instead, and why. Agents get something they can act on, not just a fact. Existing items
  keep their current shape unless you re-analyze them.
- **Refreshing knowledge in long sessions** (optional). The start-of-session notes already come back after
  compaction. After many hours of work in one session, Chronicle could offer the relevant knowledge again, saying
  why it is doing so. It will be off by default, since it runs on every prompt.

## Later

- **Linked discussions.** When a session's agent reads a team-chat thread through an MCP tool, keep the thread's
  link (not its text) with the session, show it on the session page, and let knowledge cite it. That gives you
  "this discussion, this session, this code" without Chronicle ever connecting to Slack. An option will drop such
  tools' message text from the archive and keep only the links. It waits until real sessions use such a tool.
- **Remote access without Tailscale**, over a peer-to-peer connection with QR pairing. A design exists. It needs a
  browser-side peer, and its WebRTC dependency would be an optional install so the core package stays small.
- **More agents recorded.** Claude Desktop, Cursor, Windsurf and Gemini CLI can use Chronicle's MCP server today,
  but their sessions aren't recorded.
- **Windows.** Not supported yet. The command line and dashboard are mostly portable; background running and the
  desktop app are not.
- **Notifications on your phone** for new versions and finished analyses, without adding a server.

## Not planned

- **A hosted service, cloud sync or telemetry.** Chronicle's promise is that nothing leaves your machines except
  the analysis call through your own login. Sharing across computers goes through your own hub.
- **Computers connecting to a shared database.** One computer, the hub, writes; the others send it their sessions
  and never get a database's address or password. A hub may keep the team's record in your own Postgres as well
  ([team store](docs/devices.md#teammates-lessons-and-a-team-store-in-postgres)), but it stays the only writer.
- **Analysis with an API key we hold.** Analysis always uses the Claude Code or Codex login already on your
  computer and counts against your own plan.

## Suggesting something

Open an [issue](https://github.com/Chatixia-AI/agents-chronicle/issues) describing what you were trying to do and
where Chronicle got in the way. That helps more than a feature name, and it is how items get onto this page.
