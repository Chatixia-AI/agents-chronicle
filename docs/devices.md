# Phone and other computers

[← Chronicle](../README.md) · [Docs index](README.md)

Chronicle keeps its archive on one computer. You can also open its dashboard on your phone, and keep the sessions
of your other computers in the same archive. Both go through [Tailscale](https://tailscale.com), a private network
between your own devices: nothing is opened to the internet.

One computer is the **hub**: the only one that records sessions, analyzes them and serves the dashboard. Pick the
one that is switched on most of the time, such as a desktop Mac, a Mac mini or a Linux box. Your other computers
**send** it their sessions, and your phone opens its dashboard. Because only the hub writes, each session is
analyzed (and paid for) once, and there is never anything to merge.

## Your phone

1. Install Tailscale on the hub and on your phone, and sign both in to the same account.
2. On the hub, run:

   ```bash
   chronicle tailnet on
   ```

   The first time, Tailscale may print a link to turn on Serve and HTTPS certificates for your tailnet: open it,
   and run the command again if it stopped.
3. On your phone (with the Tailscale app on), open the address it prints, `https://<computer>.<tailnet>.ts.net/`.
   On an iPhone, **Share › Add to Home Screen** gives it an icon and opens it like an app; on Android, **⋮ › Add to
   Home screen**.

On a phone the dashboard puts its sections in a tab bar at the bottom and uses the whole width; Sessions opens as
cards. Everything works as on the computer: search, knowledge, reviews, pinning and dismissing.

How it works: Tailscale Serve forwards that HTTPS address to the dashboard, which still listens on 127.0.0.1 only.
The dashboard answers to that name (`[server] allowed_hosts`) and lets in only your Tailscale login
(`[server] allowed_users`), which Serve passes along. `chronicle tailnet on --anyone` lets in everyone in your
tailnet; `chronicle tailnet status` shows the setup; `chronicle tailnet off` takes the dashboard off the tailnet.
The dashboard has to be running on the hub: `chronicle install` keeps it running in the background.

## Your other computers

On the hub, after `chronicle tailnet on`:

```bash
chronicle hub enable
```

It prints a command with the hub's address and a token. [Install Chronicle](install.md) on each other computer,
then run that command there:

```bash
chronicle hub join https://pc.tail1234.ts.net --token …
```

It sends every Claude Code and Codex session on that computer to the hub, which records and analyzes them. From
then on:

- **New sessions go to the hub** as each one ends (the SessionEnd hook) and every 15 minutes (the background sync),
  once `chronicle install` has set those up on that computer. `chronicle push` sends them right away.
- **The hub knows where each session ran.** A session's page says which computer it came from, and **Settings ›
  Devices** lists the computers, their sessions and when each last sent something (`chronicle hub status` in a
  terminal).
- **Analysis runs only on the hub.** If the computer already analyzed sessions with its own Chronicle, it hands
  those analyses over when it joins, so the hub does not pay to analyze them again.
- **That computer's own dashboard and MCP tools stop updating.** They keep what they had; open the hub's dashboard
  instead (**Settings › Devices** has a link).

### Same project, different folders

The same repository often lives in different folders on different computers. The hub files each session under the
matching project of its own:

1. **By git remote.** The other computer reports each project folder's git remote (Codex sessions record theirs
   too); a session goes to the hub's folder with the same remote.
2. **By `[hub] path_map`**, for projects without a remote, in the hub's [configuration](configuration.md#hub):

   ```toml
   [hub]
   path_map = { "/home/me/code" = "/Users/me/Projects" }
   ```

Otherwise the session keeps the folder it ran in. A session page shows the original folder when you hover over the
computer's name.

### What is sent

- From each `claude_dirs` folder: `projects/` (transcripts, subagent threads, memory notes) and `history.jsonl`.
  From each `codex_dirs` folder: `sessions/`, `memories/` and Codex's session index.
- Projects in `sources.exclude_projects` are never sent.
- GitHub Copilot, IBM Bob, Google Antigravity, Codex Cloud and chat exports are not sent: connect or import those on the hub.
- Files travel over HTTPS inside your tailnet, compressed, and are checked against a SHA-256 on arrival. Only files
  the hub lacks, or has an older copy of, are sent. Each computer proves itself with the hub's token, kept in
  `~/.claude-chronicle/hub-token`, readable by your user only. `chronicle hub enable --rotate` replaces it; the
  other computers then have to join again.
- The hub keeps what it receives under `~/.claude-chronicle/machines/<computer>/` and archives it like its own.

### Leaving

`chronicle hub leave` on a computer makes it record and analyze its own sessions again; the hub keeps what it was
sent. `chronicle hub disable` on the hub stops it accepting sessions.

## A Linux hub

On Linux, `chronicle install` sets up systemd user units instead of launchd agents: `chronicle-sync.timer` (the
15-minute sync) and `chronicle-ui.service` (the dashboard). Two one-time commands help a hub that runs unattended:

```bash
loginctl enable-linger $USER             # keep them running while nobody is logged in
sudo tailscale set --operator=$USER      # let `chronicle tailnet on` configure Tailscale Serve
```

The desktop app is macOS only; the command line and the dashboard work the same.

## Without a hub: Syncthing

If you would rather not run a hub, [Syncthing](https://syncthing.net) (or rsync) can copy another computer's
sessions to the main one: sync its `~/.claude/projects` into a folder such as `~/sessions/laptop/claude/projects`
and its `~/.codex/sessions` into `~/sessions/laptop/codex/sessions`, then add `~/sessions/laptop/claude` to
`claude_dirs` and `~/sessions/laptop/codex` to `codex_dirs`. Chronicle records them as its own: without the
computer's name, project matching or the handover of earlier analyses.

Never sync `~/.claude-chronicle` itself between computers: a SQLite database copied while it is in use can be
corrupted.

## Not covered yet

- **The Claude app on your phone.** Claude's custom connectors reach MCP servers from Anthropic's cloud, not from
  your phone, so the hub's tailnet address is out of their reach. Claude Code's Remote Control, from the phone into
  a session on the hub, does have Chronicle's tools.
- **A copy to read offline** on the other computers.
- **Windows.**
