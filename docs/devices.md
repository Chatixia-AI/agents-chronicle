# Phone and other computers

[← Chronicle](../README.md) · [Docs index](README.md)

Chronicle keeps its archive on one computer. You can also open its dashboard on your phone, and keep the sessions
of your other computers in the same archive. Both go through [Tailscale](https://tailscale.com), a private network
between your own devices: nothing is opened to the internet.

One computer is the **hub**: the only one that records sessions, analyzes them and serves the dashboard. Pick the
one that is switched on most of the time, such as a desktop Mac, a Mac mini or a Linux box. Your other computers
**send** it their sessions, and your phone opens its dashboard. Because only the hub writes, each session is
analyzed (and paid for) once, and there is never anything to merge.

A hub can also serve a team. Each person joins with an invite and a role ([People and roles](#people-and-roles)),
and the company network can take the place of Tailscale ([Reaching the hub without
Tailscale](#reaching-the-hub-without-tailscale)).

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

That token is the hub's shared token, which suits your own computers. For other people's computers, invite each
person instead ([People and roles](#people-and-roles)).

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
2. **By a folder added on that computer**, for a folder whose sessions belong to one of the hub's projects: a notes
   folder, a scratch folder, or a repository the hub doesn't know. On that computer, run:

   ```bash
   chronicle hub add-folder ~/work/client-notes --project demo-app
   ```

   `--project` takes a project's name or its path on the hub; `chronicle hub folders --list` lists them. The folder
   and everything below it go to that project, including sessions already on the hub: they move with their knowledge,
   and both projects' knowledge bases are rebuilt. The more specific match wins, so a repository inside the folder
   whose git remote the hub knows still follows its remote. A folder inside a repository the hub files under another
   project is refused, because a repository belongs to one project. `chronicle hub folders` shows what goes where,
   and `chronicle hub remove-folder <folder>` takes one back out. The hub's **Settings › Devices** lists the folders
   each computer added.
3. **By `[hub] path_map`**, for projects without a remote, in the hub's [configuration](configuration.md#hub):

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
- Files travel over HTTPS (inside your tailnet, or through the HTTPS proxy in front of the hub), compressed, and are
  checked against a SHA-256 on arrival. Only files the hub lacks, or has an older copy of, are sent. Each computer
  proves itself with a token kept in `~/.claude-chronicle/hub-token`, readable by your user only: the hub's shared
  token, or a token of its own when it joined with an invite. `chronicle hub enable --rotate` replaces the shared
  token; the computers that use it then have to join again.
- The hub keeps what it receives under `~/.claude-chronicle/machines/<computer>/` and archives it like its own.

### Sharing knowledge only

A computer can keep its transcripts and still add to the hub's knowledge. Join with `--share knowledge`:

```bash
chronicle hub join https://pc.tail1234.ts.net --token … --share knowledge
```

(or, on a computer that already joined, `chronicle config set hub.share knowledge`, or **Settings › Devices › What this
computer sends** in its dashboard). That computer then works like a
standalone Chronicle: it records its own sessions, analyzes them with its own Claude Code or Codex login, and keeps
its dashboard and MCP tools up to date. After each analysis it sends the hub only:

- each analyzed session's details: when it ran, agent, model, branch, tokens and cost, which tools it used;
- its analysis: title, summary, outcome, highlights and what went wrong;
- the lessons it produced about the project.

Prompts, shell commands, file paths, transcripts and lessons about you (global ones and preferences) never leave
the computer. Sessions from GitHub Copilot, IBM Bob and Google Antigravity are shared too; imported chats are not.

On the hub these sessions are filed like any other from that computer (by git remote, an added folder or
`path_map`) and their lessons join the project's knowledge base. A session page shows **transcript on
<computer>** instead of the transcript, and the hub never analyzes these sessions again, so it needs no Claude login
for them. It still builds each project's knowledge base and glossary with its own. **Settings › Devices** marks the
computer **knowledge only**. A session the hub already has the transcript of keeps the hub's record.

### Teammates' lessons, and a team store in Postgres

A hub that several people share can keep the team's record in Postgres, and send each computer that shares
knowledge what its teammates learned. On the hub:

```bash
uv tool install 'agents-chronicle[team]'    # the Postgres driver, needed on the hub only
# PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD (and PGSSLMODE, require by default), one per line:
$EDITOR ~/.claude-chronicle/team-store.env && chmod 600 ~/.claude-chronicle/team-store.env
chronicle config set hub.store postgres
chronicle hub store                          # connects, sets up its tables, and shows what it holds
```

Then restart the dashboard, which is what receives the sessions. Or, once the driver is installed, open **Settings ›
Devices › Team store** on the hub itself: fill in the connection, **Test connection**, then **Save**. Nothing is saved
unless the connection works, the password is never shown again, and only an admin can change these settings
([People and roles](#people-and-roles)).

- **What it keeps.** Every session a computer shares, its details, summary and project lessons, is written to
  Postgres first and then to the hub's own database, which the dashboard still reads. If Postgres can't be reached,
  neither keeps it, and the computer sends it again at its next push.
- **Lessons belong to a repository.** A lesson learned in a git repository belongs to that repository (its remote),
  wherever each person cloned it; one learned in a folder without a remote belongs to that folder's project on the
  hub. The same lesson from two people (same kind and title) becomes one item that remembers whose sessions stated
  it.
- **Teammates' lessons come back.** After each push, a computer that shares knowledge gets its teammates' lessons
  for the repositories it has clones of, the projects it shared sessions in, and those it added folders to. They are
  kept read-only in its own database, under its own folder for that repository, where its MCP tools answer with them
  (marked as teammates') and the start-of-session notes list them under **From teammates' sessions**. Lessons it
  stated itself are not sent back. One it dismisses stays dismissed; one the team no longer has disappears.
  `chronicle hub status` and its **Settings › Devices** show how many it holds; **Share and get team lessons now**
  there pushes at once.
- **Only the hub connects to the database.** Computers never get its address or password, so it can sit on a
  network only the hub reaches. Its tables live in the schema `team`, with an audit log of every push and pull
  (counts only), and each upgrade step runs once, recorded by name.

Not yet: lessons from sessions the hub analyzes itself (`share = "everything"`) don't go to Postgres, and when the
same lesson arrives in two languages, the latest wording wins.

### Leaving

`chronicle hub leave` on a computer makes it record and analyze its own sessions again; the hub keeps what it was
sent. `chronicle hub disable` on the hub stops it accepting sessions.

## People and roles

A hub that several people share knows who each of them is. An admin invites each person with a role, each
person's computers get a token of their own, and the hub's dashboard opens without a password. None of it needs
Tailscale.

| Role | What they can do |
| --- | --- |
| `admin` | everything a member can, and on the hub's dashboard: invite people, change roles, remove people, and change the hub's settings (the team store, people, the shared token) |
| `member` | their computers send to the hub and get teammates' lessons back; they see the hub's dashboard |
| `readonly` | they see the hub's dashboard; they send nothing and change nothing |

Members and read-only people can look through everything on the hub's dashboard, but only admins change anything
there: settings, Sync, analyses, pinning and dismissing. A member's own Chronicle works as before.

Until you add the first person, a hub works as it always did: computers send with the shared token, and the
dashboard lets in whoever reaches it (through Tailscale, whoever `[server] allowed_users` allows). Once it has
people, everyone who opens its dashboard from another device signs in, through Tailscale too.

### Whoever is at the hub is an admin

Someone at the hub computer itself is always an admin: the `chronicle hub` commands run there, and so does the
dashboard opened on that computer. That is how the first people are added. It is also how you recover a hub whose
admins are gone: at the hub, run `chronicle hub role ana@example.com admin`. A person with the admin role can't
demote or remove the hub's last admin; at the hub itself you can.

### Inviting someone

On the hub, run:

```bash
chronicle hub invite "Ana Lima" --email ana@example.com --role member
```

or use **Settings › Devices › People › Invite someone** in the hub's dashboard. `--role` is `member` when you leave
it out. The email is optional, but company sign-in finds people by it. You get:

- a code, such as `K7PQ-M2XD-9HNA`;
- the command for Ana's computer: `chronicle hub join https://chronicle.example.internal --code K7PQ-M2XD-9HNA --share knowledge`;
- a link for a browser: `https://chronicle.example.internal/signin?code=K7PQ-M2XD-9HNA`;
- when the code expires.

A code works once, for 7 days. The hub sends no email: pass the code on by chat. It is shown once, because the hub
keeps only a hash of it. If it is lost or has expired, make a new one: run `chronicle hub invite` again with the same
email, or use **New invite** next to the person. One code joins one computer or signs in one browser, so someone
with a laptop and a phone needs two. Case and dashes don't matter when a code is typed.

The command and the link use the hub's address, `[hub] address`, which `chronicle hub enable --url <address>` sets.
`chronicle hub people` lists everyone with their role and computers.

### Joining a computer

On the person's computer, after [installing Chronicle](install.md):

```bash
chronicle hub join https://chronicle.example.internal --code K7PQ-M2XD-9HNA --share knowledge
```

The hub trades the code for a token for that person and that computer, kept in `~/.claude-chronicle/hub-token`. The
token only works from that computer. From then on the computer sends like any other
([Your other computers](#your-other-computers)). `--share knowledge` keeps its transcripts on the computer
([Sharing knowledge only](#sharing-knowledge-only)); leave it out to send everything. Joining again with a new code
replaces the computer's old token.

### Opening the hub's dashboard

- **From your own Chronicle.** On a computer that joined, **Settings › Devices › Open the hub's dashboard** asks the
  hub for a sign-in link, valid for 5 minutes, and opens it in your browser. There is no password.
- **With the invite link.** Opening `…/signin?code=…` signs that browser in. You can also paste the code on the
  hub's sign-in screen. Use this for a phone, or for someone with no computer joined to the hub.
- **With company sign-in**, when the hub sits behind it ([below](#company-sign-in)).

A browser stays signed in until 30 days after it was last used. **Sign out** in the header ends it.

### Read-only people

A read-only person only looks. Send them the browser link rather than the join command: the hub refuses what a
computer joined with their code sends ("read-only people can't send to the hub"). Make them a member to let their
computer send.

### The shared token

Computers that joined with `--token` keep sending with the hub's shared token after people are added, so nobody is
cut off. Once everyone has joined with an invite, turn it off on the hub:

```bash
chronicle hub shared-token off
```

or with the switch in **Settings › Devices › People**. From then on the hub refuses the shared token, and a computer
that still uses it has to join again with a code. `chronicle hub shared-token on` turns it back on. The shared token
never opens the dashboard.

### Removing someone

`chronicle hub remove ana@example.com`, or **Remove** next to the person in **Settings › Devices › People**, takes a
person off the hub. Their unused codes, their computers' tokens and their browser sessions stop working at the next
request. What their computers sent stays on the hub.

To cut off one computer or one browser and keep the person, a lost laptop say, use **Revoke** next to it in the
same list. That computer can join again with a new code. `chronicle hub role ana@example.com readonly` changes a
role. These commands take an email or the id that `chronicle hub people` shows.

### The audit log

The hub records who added, invited, changed the role of, removed or revoked whom, and each time a computer joins or
a browser signs in, with the time. What is done at the hub itself is recorded as **this computer**. **Settings ›
Devices › People** shows the latest entries. Codes, tokens and browser sessions are stored only as hashes.

## Reaching the hub without Tailscale

Tailscale is one way to reach a hub. Many companies don't allow it, and a hub works just as well on the company
network or over the company VPN. Say the hub should be reached at `https://chronicle.example.internal`:

1. **Set the address and add people first.** At the hub, `chronicle hub enable --url
   https://chronicle.example.internal` sets `[hub] address`, which the join commands and sign-in links use. Then
   invite yourself and your team ([above](#inviting-someone)). Until a hub has people, anyone who reaches its
   dashboard gets in as an admin, so do this before you open it to the network.
2. **Put HTTPS in front.** The dashboard speaks plain HTTP, and codes, tokens and sign-in cookies must not cross the
   network in clear text. Put a reverse proxy in front of it with a certificate your computers trust: Caddy, nginx,
   or the company's load balancer. The proxy passes on the original `Host` and sets `X-Forwarded-For` and
   `X-Forwarded-Proto`. Caddy does this by default; with nginx:

   ```nginx
   location / {
       proxy_pass http://127.0.0.1:8765;
       proxy_set_header Host $host;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       client_max_body_size 0;    # transcripts can be large
   }
   ```

3. **Let the dashboard answer to that name**, in the hub's [configuration](configuration.md#synthesis-export-server-inject-updates):

   ```toml
   [server]
   host = "0.0.0.0"                                # only when the proxy runs on another computer
   allowed_hosts = ["chronicle.example.internal"]
   trusted_proxies = ["10.0.4.12"]                 # that computer, so its X-Forwarded-Proto is believed
   ```

   When the proxy runs on the hub itself, keep `host = "127.0.0.1"` and the default `trusted_proxies`, and add
   `behind_proxy = true`: a proxied request can look exactly like one made at the hub, which is always an admin, so
   with it set no request through the dashboard counts as made at the hub. Admins then sign in like everyone, or use
   the `chronicle hub` commands at the hub. With `0.0.0.0`, let only the proxy reach port 8765 through the firewall.
   Restart the dashboard afterwards.

With Tailscale instead, `chronicle tailnet on --anyone` lets everyone in your tailnet reach the hub over HTTPS
([Your phone](#your-phone)). Once the hub has people, they still sign in.

### Company sign-in

If your company signs people in through an auth proxy (oauth2-proxy, Azure App Service authentication and the like)
that passes the signed-in person's email in a header, the hub can use it:

```toml
[server]
auth_header = "X-Forwarded-Email"
trusted_proxies = ["127.0.0.1", "::1"]     # where the auth proxy connects from
```

The hub believes the header only on requests from `trusted_proxies`, and only for people added on the hub with that
email; anyone else sees "you're not on this hub; ask an admin to add you". Roles still come from the hub. The proxy
must set the header itself and drop any copy a browser sends: anything else in `trusted_proxies` that passes a
visitor's headers through unchanged (Tailscale Serve on the hub, for one) would let a visitor name any email. Use
`auth_header` only when the auth proxy is the only way in. Computers don't use company sign-in: they keep joining
with a code, so let requests to `/api/hub/` through the auth proxy without sign-in (oauth2-proxy:
`--skip-auth-route`). The hub checks their tokens itself.

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
