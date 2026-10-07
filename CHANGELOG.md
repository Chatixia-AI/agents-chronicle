# Changelog

## Unreleased

- **A hub that takes knowledge only:** `chronicle config set hub.accept knowledge` on the hub, or **Team › Computers ›
  Knowledge only** for an admin, keeps every transcript off the hub. It turns away any computer that sends
  transcripts, whatever token it uses, and tells it to run `chronicle config set hub.share knowledge`. Computers that
  share knowledge go on as before, and one that joins with an invite is set to share knowledge on its own.
  **Team › Computers** and `chronicle hub` mark a computer that is turned away. A typo in the setting counts as
  knowledge only, and the audit log records who changed it.
  [A hub that takes knowledge only](docs/devices.md#a-hub-that-takes-knowledge-only)
- **More vivid charts:** the eight series colours (charts, the Map, the Systems map, agent dots) keep their hues at
  the most saturation a screen can show, within the lightness range that keeps them readable and distinct, checked
  with the palette validator in both themes. Bars, lines and the tiles' sparklines draw in that bright blue rather
  than grey or the link colour, with stronger fills, and the heatmaps run from pale sky to deep blue.
- **Search for projects when inviting someone:** on a hub with more than six projects, **Team › People** has a search
  box above the projects a person sees, both when inviting someone and under **Change**. It filters by name or
  folder, and ticked projects stay ticked while hidden, with a count of how many are chosen. Enter ticks the only
  match left and never sends the invite; Escape clears the search.
- **The hub's container names its own address:** its log said `Chronicle dashboard: http://127.0.0.1:11524/`, and
  VS Code connected to the server over Remote-SSH forwarded that port to your own computer, where it hid your own
  dashboard at `127.0.0.1:11524`. It now says `Chronicle hub is up: https://<the hub's address>`.
- **Step-by-step guides for a team's hub:** [A hub in Docker](docs/docker.md) now walks whoever runs the hub from an
  empty server to a shared project: Azure (a VM, your own SSH key, the ports, a name), the first admin, adding a
  project from the command line, connecting your own computer, inviting the team, everyday commands and
  troubleshooting. [Joining your team's hub](docs/join-a-hub.md) is the page to send teammates.

## 0.13.0 (2026-10-07)

- **The dashboard in the Chronicle blueprint style:** the app now looks like
  [chronicle.chatixia.net](https://chronicle.chatixia.net/). The dark theme is navy blueprint paper with a faint grid,
  the light theme the same drawing as a whiteprint; type is IBM Plex Sans and Plex Mono, with small mono capitals for
  labels. Gold marks what to press (Sync, Approve) and the current section, teal what is done, blue the links and the
  data. Panels are flat with thin rules instead of glass, in the browser and in the macOS app, so *Reduce transparency*
  is gone from **Settings › Appearance**. The fonts ship with Chronicle (Latin subsets, SIL Open Font License), so the
  dashboard never calls a font service; Japanese text uses the system's Hiragino.
- **A hub in Docker:** `docker/compose.yaml` runs a team's hub on any server with Docker: the hub, Caddy for HTTPS,
  and Postgres for the team store. The image (`ghcr.io/chatixia-ai/chronicle-hub`, published with each release)
  sets the hub up from `CHRONICLE_*` variables. It takes knowledge only, so it needs no model. Computers join with
  invites, and the first admin's invite is printed in the container's log. It won't serve a hub without people,
  since anyone who reaches such a hub counts as its admin. Requests through the dashboard never count as made at the
  hub, so everyone signs in. See [A hub in Docker](docs/docker.md).

## 0.12.1 (2026-10-07)

- **IBM Bob analyzes sessions too:** pick **IBM Bob** in **Status › Analysis** (or `analysis.backend = "bob"`) and add a
  Bob API key (`chronicle config set-key bob`, or `BOB_API_KEY`). Chronicle runs Bob Shell headless (`bob run`) with
  every tool group, MCP and subagents off, its instructions in a throwaway custom mode with no tools, and discards
  a reply that follows any tool call. Bob keeps these runs in its own task list; Chronicle doesn't import them.
- **Choose the agent's model:** Claude Code's tab sets the models for sessions, knowledge bases and screening (an
  alias or a full id such as `claude-opus-5-5`) and the effort; Codex's sets its model and effort.
- **Forgetting a session keeps files other sessions share:** `chronicle forget` (and the dashboard's Forget) deleted the
  session's archive even when it was shared: the snapshot of Bob's database every Bob task points to, or the archived
  chat export behind every imported ChatGPT or Claude.ai chat. With `--delete-transcript`, forgetting one Bob task
  deleted Bob's own `~/.bob/db/bob.db`. A file is now removed only once no remaining session uses it.
- **A tidier Status › Analysis:** the card spans the page, with what analyzes on the left and the queue (ready,
  queued, held, spent), why it waits and the knowledge language on the right. A provider's settings sit in two
  columns with a Ready / Not set up badge, endpoint and tuning under **Advanced**, and the buttons on one row.
- **Analysis through your own model provider stays MIT:** [ee/README.md](ee/README.md) no longer lists a company's
  own model endpoint as an enterprise feature. Since 0.12.0 every provider (Bedrock, Azure OpenAI and the rest) is in
  the MIT core, and it stays there.

## 0.12.0 (2026-10-06)

- **Analyze with a model provider's API:** besides Claude Code and Codex, sessions can be analyzed through the
  Anthropic API, Claude in Amazon Bedrock (a Bedrock API key, or your AWS sign-in with SigV4), the OpenAI API, Azure
  OpenAI (an API key, or Microsoft Entra ID through `az login`), OpenRouter, any OpenAI-compatible server (LM Studio,
  vLLM, ...), or Ollama, where nothing leaves your computer. **Status › Analysis › API provider** sets the endpoint,
  models and key, tests the connection and switches to it; in the terminal, `chronicle config set
  providers.<name>.<key>`, `chronicle config set-key <name>` and `analysis.backend = "<name>"`. Keys are kept in
  `provider-keys.json` (mode 600), never in `config.toml`, and never sent back to the browser. Calls carry no tools, so
  the model can only answer, and need nothing beyond the standard library. [Model providers](docs/analysis.md#model-providers)
- **Bob Shell gets the MCP server:** `chronicle connect bob` now also registers the MCP server in
  `~/.bob/settings/mcp.json`, the file Bob 2.x and Bob Shell (`bob`) read. It used to write only
  `mcp_settings.json`, which Bob copies to `mcp.json` once, so if Bob Shell had run before you connected, it never
  saw the server. Disconnecting removes it from both files, and the Sources card checks `mcp.json`. Bob Shell's tasks
  were already recorded: they're in the same `~/.bob/db/bob.db` as the IDE's.
- **The dashboard's default port is 11524**, out of the way of other local servers that like 8765. New installs use
  it; an existing install keeps the `port = 8765` its `config.toml` already has (`chronicle config set server.port
  11524` moves it). The VS Code extension, unless `chronicle.url` is set, finds the dashboard on either port.
- **Bob's tool calls are recorded:** Bob now writes tool calls as `toolCalls` rather than the OpenAI-style
  `tool_calls`, so Chronicle recorded none of them: Bob sessions showed 0 tool calls, no files, and the files Bob
  wrote never appeared as artifacts. Both shapes are read now. Bob's relative paths (`docs/x.html`) resolve against
  the task's folder, lines added and removed come from the diff Bob keeps with each change, a call Bob marks failed
  counts as an error, and a subagent's calls and files are the subagent's. Cost comes from what Bob reports for each
  message, which used to read $0.00 when the task total had no token counts.

## 0.11.0 (2026-10-06)

- **A hub opens on Activity:** on a hub with people, the dashboard now opens on **Activity** (the charts of every
  session), with its own rail icon. The team's page (what needs attention, team projects) moves to its own
  **Team overview** rail icon at `#/overview`, for every member of the hub. A computer that isn't a hub keeps Home.
- **Updating reloads the page:** after **Update to …** finishes, a "Restarting Chronicle…" cover stays over the page
  while the dashboard restarts, and the page reloads itself as soon as the new version answers (it used to wait for
  the next 20-second status check). If the restart takes over a minute, the cover says so and offers a Reload button.

## 0.10.0 (2026-10-06)

- **Chronicle Enterprise lives in `ee/`:** features a company needs to run Chronicle across its teams (single
  sign-on, policies, audit export, admin reports) will be built in `ee/` under the Chronicle Enterprise License and
  ship as a separate package. Everything else, the hub and its team features included, stays MIT, and the
  `agents-chronicle` package stays MIT only. [ee/README.md](ee/README.md)
- **A map of your systems:** **Projects › Systems map** draws every folder your agents worked in as a system, grouped
  by the folders they live in, with lines where one project edited or read another's files or its glossary says how
  it uses the other. Open a system for its parts in five rows (ways in, code, data, delivery, and what it runs on or
  uses): its frontend calling the backend's `/api`, the Postgres it stores in, the Terraform that provisions its App
  Service, the VM it is deployed to over ssh. Nothing is drawn by a model: every part and line comes from the project's
  manifests (package manifests, compose files, Dockerfiles, Terraform, CI workflows, vite proxies, deploy configs, read
  only) and what sessions did (servers they started, hosts and clouds they reached, machines they ssh'd into, files
  they touched), and clicking it shows that evidence, each command linked to its session. `chronicle systems [NAME]`
  prints the same in the terminal; `[systems] read_manifests = false` draws from sessions only.
  [Systems map](docs/dashboard.md#systems-map)
- **Whose work, on a hub:** **Sessions** and **All knowledge** show whose each session and lesson is (the person whose
  computer it came from, else that computer) and filter by person. Names on the team's Home, session rows and lessons
  open that person's sessions or lessons. `GET /api/team/who` lists who to filter by, within what the viewer may see.
  [The hub's dashboard](docs/devices.md#the-hubs-dashboard)
- **The hub's dashboard is the team's:** once a hub has people, its **Home** shows the team projects (set up on the
  hub, or sent to by other computers) with the sessions and new lessons of the last 7, 30 or 90 days, who worked on
  each, and the newest lessons and sessions with the person they came from. Admins also see what needs attention:
  people who haven't joined or have no way in, and computers not heard from for a week. Projects only the hub
  computer works on stay off it; **Home › Activity** keeps the charts of every session. People, shared projects,
  computers and the team store move from **Settings › Devices** to a **Team** section for admins, and **Team ›
  Computers** says whose each computer is. A **Hub** marker in the header and a green tint tell the hub's dashboard
  from your own; `[hub] name` names it. [The hub's dashboard](docs/devices.md#the-hubs-dashboard)
- **Search when sharing a project:** **Team › Shared projects** now has one search box instead of a
  list and a folder field. Typing filters the hub's projects by name or folder (arrow keys and Enter pick one); a
  folder starting with `/` or `~` can be shared as it is.
- **Pages that say they're loading:** a page that takes more than a moment shows a thin bar along the top of the
  content area, and the dashboard's first open shows grey blocks in the shape of Home instead of a blank area. After
  4 seconds a note under the toolbar says the page is still loading and counts the seconds, adding what the dashboard
  is busy with when a sync or import is running. With reduced motion there is no shimmer and the bar stays still.

## 0.9.0 (2026-10-05)

- **Shared projects on the dashboard:** on a hub, **Settings › Devices › Shared projects** shows which projects leave
  the computer: each one's folder, who sees it, which computers send to it and how many sessions it holds. At the hub
  computer itself you can share another project, picked from the hub's projects or typed as a folder, or stop sharing
  one; admins elsewhere see the card but can't change it, since it decides what leaves the hub. Shared projects carry
  a **Shared** badge in **Projects** and on their page, and sharing or stopping goes into the audit log.
  [Projects and who sees them](docs/devices.md#projects-and-who-sees-them)

## 0.8.0 (2026-10-05)

- **Projects on the hub, and who sees them:** `chronicle hub project add <folder>` sets up a project on the hub
  before anyone sent to it: a folder on the hub computer and everything below it, named after the folder. The hub's
  own sessions there are filed under it at once, with their knowledge, and other computers can
  `chronicle hub add-folder` to it right away. An admin now says which projects each member or read-only person
  sees: `chronicle hub invite <name> --project <name>` (repeat it for more) or `--all-projects`, changed later with
  `chronicle hub access`, or in **Settings › Devices › People**. A new member or read-only invite without either is refused. Someone
  limited to projects sees only theirs on the hub's dashboard (Home, Sessions, Knowledge and Projects), each session
  as its summary and project lessons: no prompts, transcripts, files or commands, and the hub enforces this on its
  side. Their computers share knowledge only, and only the sessions the hub files under their projects; the hub
  drops anything else they send, and the teammates' lessons they get back come from those projects only. With a
  team store, the hub's own sessions in a project set up there go to Postgres too, so teammates get the hub owner's
  lessons. On the hub, the start-of-session notes and `project_knowledge` in any folder inside such a project use
  that project's knowledge. Admins always see everything, and people added before this release still see every
  project. [Projects and who sees them](docs/devices.md#projects-and-who-sees-them)

## 0.7.1 (2026-10-05)

- **Moving a checkout install to PyPI, documented:** [Updating](docs/install.md#updating) now says that a checkout run
  with `uv sync` or `uv run` has no Update button, and **From a checkout to a PyPI install** moves the hooks, MCP
  servers and background agents to `uv tool install 'agents-chronicle[app]'` without touching your data. Installing
  with a `==version` pin stops `uv tool upgrade`, and the Update button, from going past that version; the page
  says how to drop it. A checkout's version now reads like `0.7.1.dev3+g1a2b3c4`: the last release plus the commits
  since.

## 0.7.0 (2026-10-05)

- **People and roles on a hub, without Tailscale:** an admin invites each person as an admin, a member or read-only,
  with `chronicle hub invite <name> --email … --role …` or **Settings › Devices › People** on the hub. The invite is a
  one-time code, valid for 7 days and shown once, passed on by chat. A member's computer joins with
  `chronicle hub join <address> --code …` and gets a token of its own; a browser opens the invite link. Members open
  the hub's dashboard from their own Chronicle with a short sign-in link, no password. Read-only people see the
  dashboard and send nothing, and only admins change anything there. Removing a person, or revoking one computer or
  browser, takes effect at once, and every invite, role change, removal, join and sign-in goes into an audit log.
  Computers that joined with the hub's shared token keep working until `chronicle hub shared-token off`. Whoever is
  at the hub computer itself is always an admin. A hub can now sit on the company network or VPN behind an HTTPS
  proxy (`[hub] address`), with company sign-in through an auth proxy's header (`[server] auth_header`,
  `trusted_proxies`) for people added on the hub. [People and roles](docs/devices.md#people-and-roles)
- **Teammates' lessons, and a team store in Postgres:** a hub with `[hub] store = "postgres"` (the connection in
  `team-store.env`, the driver from `agents-chronicle[team]`) also keeps what computers share in Postgres: each
  session's details and summary, its project lessons, and an audit log. Lessons belong to their git repository
  wherever each person cloned it, so the same lesson from two people becomes one item that remembers whose sessions
  stated it. After each push, a computer that shares knowledge gets its teammates' lessons for its own repositories
  back, read-only: its MCP tools answer with them, marked as teammates', and the start-of-session notes list them
  under **From teammates' sessions**. Only the hub connects to the database. `chronicle hub store` sets it up and
  shows what it holds, and so does **Settings › Devices › Team store** on the hub itself (tested before it is saved; the
  password never comes back to the browser). On a member, **Settings › Devices** switches what it sends and shows its
  teammates' lessons. [Teammates' lessons, and a team store in Postgres](docs/devices.md#teammates-lessons-and-a-team-store-in-postgres)
- **Share knowledge, keep transcripts:** `chronicle hub join … --share knowledge` (or `[hub] share = "knowledge"`)
  lets a computer add to the hub's knowledge without sending its transcripts. It keeps recording and analyzing its
  own sessions with its own Claude Code or Codex login, and after each analysis sends the hub only the session's
  details, its summary and its lessons about the project. Prompts, shell commands, file paths, transcripts and
  lessons about the person stay on the computer. The hub files these sessions like any other, adds their lessons to
  the project's knowledge base, never analyzes them again, and shows **transcript on <computer>** on their pages.
  [Sharing knowledge only](docs/devices.md#sharing-knowledge-only)
- **Add a folder to a project on the hub:** on a computer that sends its sessions to a hub,
  `chronicle hub add-folder <folder> --project <name>` files the sessions in that folder, and every folder below it,
  under one of the hub's projects: a notes folder, a scratch folder, or a repository the hub doesn't know. Sessions
  already on the hub move too, with their knowledge, and both projects' knowledge bases are rebuilt. The more
  specific match wins: a repository inside the folder whose git remote the hub knows still follows its remote, and a
  folder inside a repository the hub files under another project is refused. `chronicle hub folders` shows what
  goes where, `chronicle hub remove-folder` undoes one, and the hub's **Settings › Devices** lists the folders each
  computer added. [Same project, different folders](docs/devices.md#same-project-different-folders)
- **The dashboard in Japanese:** every page, menu, chart, toast and the ⌘K palette can be shown in Japanese, with
  dates, times and durations written the Japanese way. **日本語** in the status bar (next to the theme toggle) switches
  over, and **Settings › Appearance › Language** picks System, English or 日本語; System follows the browser. Text the
  server writes, such as why a session is waiting, What goes wrong and suggestion evidence, follows the same choice.
  Each browser keeps its own language, so the dashboard on your phone can differ from the one on your Mac.
- **Knowledge in Japanese:** `[analysis] language = "ja"` (or **Status › Analysis › Knowledge language**) has
  Chronicle write summaries, knowledge, knowledge bases, the playbook, glossary definitions, weekly reviews and
  screening reasons in Japanese, and propose Japanese lines for `CLAUDE.md` and `AGENTS.md`. Identifiers, commands,
  file paths and error messages stay as they were, and so do tags, so sessions still group by topic. It applies to
  sessions analyzed from then on; what is already written stays in its language. A line whose marker is already in
  the file is not proposed again in the other language, and What goes wrong recognizes friction notes written in
  Japanese. [Language](docs/analysis.md#language)
- **Session pages open on Details:** the summary, knowledge, context chart, tools and files come first, and
  **Transcript** is one click away. A search result still opens the transcript at the match, and `?tab=transcript`
  or `?tab=details` in a link picks one.
- **Google Antigravity is a source:** `chronicle connect antigravity` (or the Sources page) records Antigravity
  conversations from the step log Antigravity writes beside each conversation's artifacts
  (`~/.gemini/antigravity/brain/<id>/.system_generated/logs/`): prompts, replies, thinking, tool calls with results
  and durations, and tokens per call, plus the workspace, git branch and model from its conversation database.
  Connecting also gives Antigravity Chronicle's MCP server (`~/.gemini/config/mcp_config.json`).
- **Artifacts: what your agents made, in one place.** A new **Artifacts** section in the rail lists the documents, HTML
  pages, diagrams, decks, spreadsheets, generated images, published links, pull requests and commits from every
  session. Each comes from an explicit signal in the transcript (a file written whole, a page published, `gh pr
  create`, a commit), each links to the tool call that made it, and each says whether the file is still on disk as
  written, changed since, or gone. The same file across sessions is one item with its versions. Project pages list
  their latest artifacts, and a session's Details lists what it made. Images and SVG diagrams still on disk show as
  thumbnails, as a grid under **Images** and **Diagrams**, and open full size; a generated image is named after what
  its prompt asked for. Decks, documents, spreadsheets and PDFs a script saved are found too (the session names the
  file, and it was created during the session), with their first page drawn by Quick Look on a Mac; a file made in a
  claude.ai chat links to the chat, where it lives. **Open** shows any file in a new tab, even one deleted since (rebuilt from the archived
  transcript), with an HTML page's scripts sandboxed; on the Mac itself, **Open on this Mac** and **Show in Finder**
  hand a file to its own app. claude.ai chats contribute their artifacts and
  the files they handed over. Agents can search them with the new `find_artifacts` MCP tool. The next sync re-reads
  every session once to find them, imported claude.ai chats included, from the copy Chronicle archived; no analysis
  runs again. [Artifacts](docs/dashboard.md#artifacts)
- **Fixed:** an unanalyzed session without a screening result showed a stray "null" under "Not analyzed yet".
- **Fixed:** claude.ai's artifacts tool was counted as shell commands (its `command` is create/update), images that
  tools return (screenshots, image files read) are now counted, and PRs opened with `gh pr create` in Codex, Copilot
  or on a GitHub Enterprise host now reach the session's PR list.
- **An architecture sketch for each project:** synthesizing a project's knowledge base now also draws its main parts
  (code it owns, ways in, data it keeps, external services) and how they connect, shown hand-drawn at the top of the
  project page. Every part and connection cites the knowledge items behind it, and anything without a valid source is
  dropped. Click a part to see where it comes from; **Excalidraw** downloads it as an editable `.excalidraw` file
  (`/api/diagram?path=`), laid out the same way. The Markdown knowledge base carries it as a Mermaid flowchart, so the
  notes export and the `project_knowledge` MCP tool include it. Existing knowledge bases show it after their next
  synthesis. [Architecture sketch](docs/dashboard.md#architecture-sketch)
- **The sessions behind your files, in VS Code:** a new extension (`vscode-extension/`) adds two
  sections to the Explorer. **Chronicle: This File** lists the sessions that read or changed the open file,
  newest first, with what each did to it; every window follows its own editor. **Chronicle: Files in Workspace** shows
  the files sessions touched in your open folders as a folder tree, leaving out what git ignores, and each file
  expands to its sessions. Click a session to open it in the dashboard. They read the new `/api/file?path=` and
  `/api/files?root=` endpoints, which also match the relative paths Codex sometimes records. Not on the Marketplace
  yet: build it with `npx @vscode/vsce package`. [VS Code extension](docs/vscode.md)

## 0.6.1 (2026-10-02)

- **Suggestions go to the right file:** a preference about how you work (one the analysis marked *global*) is now
  proposed once for your user-level `CLAUDE.md` or `AGENTS.md`, not once for each project it came up in. Other global
  knowledge, like a gotcha about a tool, stays in its project's file, since the user-level file is read in every
  session. Each waiting card can move: **Move to every project**, or from the user level back to the projects it came
  from (`chronicle suggest move ID --to user|project`). Chronicle remembers the choice for that lesson or cause, its
  other waiting cards move along, and your edited wording comes too. Lines you dismissed or applied no longer use up
  one of a file's 8 places, so the next ones come up. A card whose lesson moved to another file, or that is waiting
  for a place, now leaves the queue quietly instead of showing as stale.
  [Moving a line](docs/suggestions.md#moving-a-line)
- **Easier to read at a glance:** on Suggestions, the status filter is one joined switch and **What goes wrong** is a
  link, so **Check again** is the only button in the header. The rail icons show their name and what the section
  holds as soon as you point at them or tab to them, in the app window too.

## 0.6.0 (2026-10-02)

- **Screen imported chats before analyzing them:** years of claude.ai and ChatGPT chats are mostly lookups, rewrites
  and everyday questions, and analyzing all of them would take your plan's limits for days. **Screen N chats** on the
  export's card (Sources › Chat exports) or `chronicle screen` sorts them into *worth analyzing*, *maybe* and *not
  worth it*, each with a topic and a one-line reason, reading only each chat's opening. Rules settle the certain cases
  without a model call (no reply, too short, translating or summarizing pasted text); Haiku (`analysis.screen_model`)
  reads the rest, 60 chats a call, knowing which projects you work on, and keeps anything about your own work at least
  *maybe*. Nothing is analyzed until you choose **Queue N worth analyzing** (`chronicle screen --queue`, `--maybe` for
  the maybes too). The Sessions list gets a *Screening* filter and shows each chat's verdict and reason until it is
  analyzed; `chronicle screen --list analyze` does the same on the command line, `--sample 200` tries it first, and
  `chronicle import --screen` screens right after importing. A chat is screened again when a newer export changes it,
  and a chat queued for analysis now stays queued when a newer export updates it.
  [Screening imported chats](docs/sources.md#screening-imported-chats)
- **Knowledge earns its trust:** every knowledge item now has a stage, *tentative*, *seen once*, *established* or
  *canonical*, computed from how many sessions confirmed it and over how long, never guessed by the model. When
  synthesis finds the same lesson in another session it reports the pair as a duplicate, and the surviving item
  takes over that session: two sessions make it established, three over at least two weeks (or a pin) make it
  canonical, and the reason is kept ("confirmed in 3 sessions over 19 days"). Search, the MCP tools and the
  SessionStart digest list the most trusted knowledge first and label it (`[gotcha · established ×3]`);
  knowledge-base bullets, knowledge cards and the knowledge table show the stage. A superseded item now names the
  item that replaced it and why (duplicate, outdated, contradicted), and established or canonical knowledge that a
  newer session overturns is listed under **Overturned** in that week's review. Existing items get their stage on
  upgrade. [How knowledge earns trust](docs/analysis.md#how-knowledge-earns-trust)
- **Every waiting session says why:** a session that is not analyzed yet explains it on its page (still active and
  analyzed around 14:20, retrying at 16:05 after a timeout, project excluded, too few prompts, from before install
  with backfill off, failed four times…), and **Status** and `chronicle status` count the queue per reason. Sessions
  that will never be analyzed without a change are now counted as *held* instead of *queued*, and the status bar no
  longer counts ready sessions twice. When the whole queue is stopped (paused, automatic analysis off, analyzer not
  found) that is said too.
- **Real context and plan usage from the status line (optional):** `chronicle install --statusline` records, per
  Claude Code session, the peak context window use and, on Pro and Max plans, how far the 5-hour and 7-day limits
  moved while it ran. Claude Code shares these only with its status line, so Chronicle wraps yours: it records the
  numbers, then runs your own status line with the same input, so it looks exactly as before (with none, it shows
  model, context and limits). Session pages and **Status** show the numbers; sessions without a record stay unknown
  rather than zero. `chronicle uninstall` restores your status line.
- **What goes wrong, and fixes to approve:** Chronicle now finds the failures that keep coming back across your
  sessions, from failed tool calls and the friction notes analysis writes, with no model call: Playwright refusing a
  screenshot path or a busy browser, edits on stale context, zsh globs that match nothing, `sleep` polling blocked,
  a missing `timeout`, ports already taken, relative `cd`s, several sessions in one tree, and more. Expected failures
  (tests failing in a dev loop, read-only checks, provider outages, calls you turned down) are kept apart as noise.
  The **What goes wrong** page and `chronicle friction` show each cause's sessions, projects, 12-week trend and
  whether it is still happening, plus the tools that fail most.
- **Suggestions:** one queue of proposed fixes for those causes, and for knowledge confirmed often enough to tell your
  agents: a line for `CLAUDE.md` or `AGENTS.md` (user level, or the project's), the Playwright MCP arguments for
  `~/.claude.json`, or a setup step such as `setopt NO_NOMATCH`, which Chronicle shows and never runs. Nothing is
  written until you apply one: **Preview** shows the diff, the file is backed up first, the line goes inside
  Chronicle's own `<!-- BEGIN chronicle -->` block at the end of the file, and **Undo** takes it back out. You can
  edit the line before applying. Warnings flag a public repository (checked with `gh`), text that looks sensitive,
  and files git doesn't track. A dismissed suggestion never comes back, and one whose cause stopped happening goes
  stale. The queue refreshes after each background sync; the rail shows a badge for new ones, Home shows the top 3,
  and `[suggestions] notify = true` adds a desktop notification. On the command line: `chronicle suggest` (`show`,
  `apply`, `dismiss`, `done`, `undo`, `refresh`). [Suggestions and What goes wrong](docs/suggestions.md)
- **Fixed: a partly downloaded export was "not a chat export".** A large ChatGPT export (gigabytes of
  attachments) whose download stopped early lacks the end of the zip, so it was rejected outright. ChatGPT puts the
  chats first, so Chronicle now reads them from such a zip and says the download was incomplete; if the cut falls
  inside the chats, it says to download the export again.

## 0.5.1 (2026-10-01)

- **Hear about new versions:** turn on **Notify me about new versions** (Status › Updates, or say yes when
  `chronicle install` asks) and the background sync asks pypi.org once a day, dashboard open or not, and shows a
  desktop notification once per release saying how to update. macOS shows it in Notification Center, Linux through
  `notify-send`. Off by default; it sends nothing about you. `chronicle install --notify-updates` (or
  `--no-notify-updates`) answers without asking.

## 0.5.0 (2026-10-01)

- **On your phone:** `chronicle tailnet on` puts the dashboard on your Tailscale network with Tailscale Serve, at
  `https://<computer>.<tailnet>.ts.net/`, for your Tailscale login only (`[server] allowed_hosts` and
  `allowed_users`); nothing is opened to the internet. On a phone the dashboard puts its sections in a tab bar at
  the bottom, uses the whole width, keeps clear of the notch and opens Sessions as cards; **Add to Home Screen**
  gives it an icon and opens it like an app.
- **One archive for several computers:** `chronicle hub enable` makes a computer the hub, and prints the `chronicle
  hub join` command to run on the others. They send their Claude Code and Codex sessions to the hub as each one ends
  and every 15 minutes (`chronicle push` sends now); the hub records and analyzes them, once, and a computer that
  already analyzed sessions hands those analyses over when it joins. Sessions from each computer are filed under the
  hub's projects by git remote, or by `[hub] path_map`. A session's page names the computer it ran on, and the new
  **Settings › Devices** page lists the computers. See [Phone and other computers](docs/devices.md).
- **Install builds the Glossary and the Map:** `chronicle install` now explains that the Glossary and the Map are
  built from analyzed sessions, says how many are waiting and how long the background would take, and offers to
  analyze them now (all, or the newest 20) with a progress bar for each stage: sessions, knowledge bases, glossary,
  map themes. `--analyze all|N|later` answers without asking. Before, a fresh install left both pages empty for
  hours while the background worked through the backlog 6 sessions at a time.
- Ctrl-C during `chronicle analyze` (or install) now stops after the sessions already in progress instead of
  running the rest of the queue.
- Where nothing can run in the background, `chronicle install` no longer says past sessions are analyzed there.
- **Linux:** `chronicle install` runs the background sync and the dashboard as systemd user units, so a Linux box
  can be the hub.

## 0.4.0 (2026-09-30)

- **Search all sessions:** the Search page (now also in the rail) lists every session that mentions a word or
  phrase, with how many times, ordered by most mentions, newest or oldest. Each session shows its mentions in
  transcript order with the terms highlighted and who said them; **Show all** lists every mention. Clicking one
  opens the transcript at that message with the terms still highlighted, including inside folded tool calls.

## 0.3.0 (2026-09-30)

- **Analyze with Codex:** sessions, knowledge bases, the glossary and weekly reviews can now be written by OpenAI
  Codex instead of Claude Code, through your own Codex login. Pick it in **Status › Analysis**, with `chronicle
  config set analysis.backend codex`, or for one run with `chronicle analyze --backend codex`; `codex_model` picks
  the model. `chronicle install` offers Codex when Claude Code is not installed, so Chronicle no longer needs
  Claude Code at all. Codex runs sandboxed like Claude does: no session is saved for the analysis, none of your
  hooks, plugins, MCP servers, `AGENTS.md` or skills load, every tool feature is off, and Chronicle discards any
  reply that follows a tool call. Codex reports tokens but no price, so Codex analyses show no cost.
- `chronicle config set <section.key> <value>` changes one setting from the command line.
- A configured `claude_bin` or `codex_bin` that does not exist now fails the analysis cleanly instead of stopping
  the background run.

## 0.2.1 (2026-09-30)

- Chronicle moved to the [Chatixia-AI](https://github.com/Chatixia-AI) organization, and the documentation to
  <https://chronicle.chatixia.net/>. Old GitHub links redirect.
- `chronicle --version` works; 0.1.2 announced it but never shipped the flag.
- `chronicle search` shows snippet labels dimmed instead of printing `[dim]` markup literally.

## 0.2.0 (2026-09-30)

- **Knowledge overview:** the Knowledge section opens on a page with a card each for the Map, All knowledge, the
  Glossary and Weekly reviews, each with a glance at what is inside; the full list moved to **All knowledge**
  (`#/knowledge/all`; older `#/knowledge?kind=…` links still work).
- **Weekly reviews you can skim:** one week at a time, picked from a strip of weeks: a three-line TL;DR, the week's
  numbers against the week before, active time per day, where the time went, outcomes and the knowledge captured,
  then themes and short lists (shipped, learned, still open, slowed you down, try next) whose items open to their
  full text. The long write-up is folded away. New reviews are written to word limits and include the TL;DR.
- **Knowledge bases and the global playbook you can skim:** a TL;DR, a few figures, chips that jump to each
  section, a filter, and each section as a card of short bullets that open to their detail and the sessions they
  came from; the overview is folded away. Synthesis now writes a TL;DR, a short overview and a title per bullet,
  within word limits; existing knowledge bases pick this up the next time they are synthesized.
- **Guided setup:** `chronicle install` (or `chronicle setup`) lists the coding agents and MCP clients it finds,
  asks which to record, imports their past sessions, asks whether to run in the background from login (the
  15-minute sync and the always-on dashboard; previously always installed) and ends with the dashboard address,
  offering to open it. `--no-launchd` / `--no-ui` now also remove those agents if installed, so
  `chronicle install --no-launchd --no-ui` turns background running off.
  `--yes` (or no terminal) takes the defaults; re-running asks only about newly installed agents. Running
  `chronicle` on its own now shows help and, before setup, points to `chronicle install`.
- **Claude.ai and ChatGPT chats:** import a claude.ai or ChatGPT data export with **Settings › Sources › Chat
  exports › Import export…** or `chronicle import <zip>`; the format is recognized. Chats become sessions you can
  search, browse and analyze on demand; re-importing a newer export adds only new and changed chats. The account
  files in the export are never read.
- **Codex Cloud tasks:** `chronicle connect codex-cloud` (or **Settings › Sources › Codex Cloud**) records the tasks
  you ran at chatgpt.com/codex, through the `codex cloud` CLI: title, repository, changed files, the diff and a link,
  archived for good. Opt-in, since it goes online. The CLI has no task conversations, so these are not analyzed.
- **Update from the dashboard:** Settings › Status › Updates upgrades Chronicle with whatever installed it (uv
  tool, pipx, pip; a checkout install is reinstalled when its files changed) and restarts the dashboard; the
  desktop app links to the latest release. Checking PyPI happens only when you click **Check for updates**. An
  update on offer shows a notification (once per release, or per new commit for a checkout install), a dot on
  Settings and a chip in the status bar; a checkout's Updates card lists the commits and files it would bring in.
  **Check for updates daily** (off by default, `[updates] check_daily`) asks PyPI once a day while the dashboard
  is open; the last answer survives a restart. See [Updating](docs/install.md#updating).
- **Map search finds everything:** **Find terms** opens every match on the map at once (terms by name, alias or
  definition, plus themes, categories, projects and agents by name), highlights them, trims the branches on the way
  to just the path, and lists the matches in the side panel. The search is kept in the link.
- The Sessions list and a project's session table have an **Agent** column (sortable), with the same colour per agent as
  the Sources page; Codex Cloud tasks show as Codex · Cloud.
- The Sessions sidebar sorts and groups by last activity, so a long-running session stays under Today.
- **MCP page:** Settings › MCP shows which agents and clients have Chronicle's MCP server (adding or removing
  the other clients moved here from Sources), ready-to-copy config for most clients, VS Code, Codex and Claude
  Code, the tools and what to ask.
- **Export sessions:** **Export** on a session page, or on a selection in the Sessions list, downloads Markdown
  (overview and conversation), JSON (every event) or the original transcript; several sessions come as a .zip with
  an index. `chronicle export <id>… --format md|json|raw` does the same from a terminal. Secrets are redacted except
  in the original transcript.
- **Analyze a selection:** tick sessions in the Sessions list (shift-click for a range, or **Select all matching**)
  and choose **Analyze** to run them in one background job, skipped ones such as imported chats included.
- **Activity:** clicking the status bar opens what is running, with a progress bar, time so far and an estimate of
  time left, plus the analysis queue and recent results. The dashboard serves the page it started with, so an
  upgrade (or an edit to a checkout) never pairs a new page with old code before the restart.
- **Sources** is a list: a row per coding agent, chat export and MCP client that opens to its checks and actions.
  A connected agent with a failing check opens on its own.
- **New dashboard design:** a simpler VS Code layout in Apple's Liquid Glass style. An icon rail and per-section
  sidebar replace the top navigation, with a glass toolbar and breadcrumbs, a status bar, and a ⌘K palette that
  searches sessions, knowledge, projects and glossary terms and runs commands. New **Appearance** settings (theme,
  Reduce transparency).
- **Session pages** lead with headline figures, the summary and its knowledge, then switch between **Transcript**
  (one-line tool calls; **Load earlier** for links into the middle of a session) and **Details**, with an outline of
  prompts and changed files that follows the scroll.
- **macOS app:** no title bar. The sidebar is native glass with the traffic lights on it; the toolbar drags and
  zooms the window; the window follows the page's theme and the macOS Reduce transparency setting.
- New app icon, favicon and per-page titles.
- **MCP for more clients:** `chronicle connect claude-desktop`, `cursor`, `windsurf` or `gemini` (or **Settings ›
  MCP › Other MCP clients**) gives them Chronicle's MCP server; `chronicle mcp --print-config` prints an entry
  for any other client. Tool results are now redacted like analysis digests, and the tools are marked read-only.
  New [MCP server](docs/mcp.md) docs page.
- MIT license. Documentation split into a short README and pages under `docs/` (English and Japanese), with
  screenshots made from demo data (`docs/demo/make_demo.py`).
- The source is public, and the documentation is online at <https://chronicle.chatixia.net/> (English and Japanese), built from
  `docs/` and the READMEs with MkDocs.

## 0.1.2 (2026-09-28)

- **Map:** stack any of four levels (Category, Theme, Project, Agent); terms open into the knowledge items and
  sessions behind them.
- **Themes:** Claude groups large glossary categories into named themes (`chronicle glossary --themes`).
- `chronicle --version` reports the installed version.
- Japanese README.

## 0.1.1 (2026-09-28)

- User-facing text describes Chronicle as agent-neutral (Claude Code, Codex, GitHub Copilot, IBM Bob).

## 0.1.0 (2026-09-28)

- First release on PyPI as `agents-chronicle`, and the macOS desktop app (menu bar, background sync, DMG).
- Records Claude Code, Codex, GitHub Copilot and IBM Bob sessions; analyzes them with `claude -p` into summaries and
  knowledge; project knowledge bases, glossary and Map, weekly reviews, Markdown vault, CLI and MCP server.
