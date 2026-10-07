# A hub in Docker

[← Chronicle](../README.md) · [Docs index](README.md)

A team can run its [hub](devices.md#your-other-computers) on any server with Docker. `docker/compose.yaml` starts three
containers:

- **the hub**, from the image `ghcr.io/chatixia-ai/chronicle-hub`;
- **Caddy** in front of it, which gets and renews the HTTPS certificate;
- **Postgres** for the [team store](devices.md#teammates-lessons-and-a-team-store-in-postgres), which merges what
  each computer learned and sends teammates' lessons back.

The hub takes **knowledge only**. Each computer records and analyzes its own sessions with its own Claude Code,
Codex or model provider, then sends the hub each session's summary and project lessons. Transcripts, prompts and
file paths stay on the computers. The hub analyzes nothing, so it needs no model and no API key.

## Before you start

- A server with Docker and Docker Compose.
- A name for the hub, such as `chronicle.example.com`, whose DNS points at the server.
- Ports 80 and 443 open to the computers that will use the hub. Caddy also needs them to get a certificate from
  Let's Encrypt; for a name only your company network can reach, see [Your own certificate](#your-own-certificate).

## Start it

Download the three files into an empty folder:

```bash
mkdir chronicle-hub && cd chronicle-hub
base=https://raw.githubusercontent.com/Chatixia-AI/agents-chronicle/main/docker
curl -fsSL "$base/compose.yaml" -o compose.yaml
curl -fsSL "$base/Caddyfile" -o Caddyfile
curl -fsSL "$base/.env.example" -o .env
```

Fill in `.env`:

```bash
CHRONICLE_DOMAIN=chronicle.example.com   # the hub's name
CHRONICLE_ADMIN_EMAIL=you@example.com    # its first admin
CHRONICLE_ADMIN_NAME=You
POSTGRES_PASSWORD=...                    # long and random: openssl rand -hex 24
```

Then start it and read the first admin's invite:

```bash
docker compose up -d
docker compose logs hub
```

```text
Added You (you@example.com) as this hub's admin. The invite works once, for 7 days:

  In a browser, to open the hub's dashboard:  https://chronicle.example.com/signin?code=ABCD-EFGH-JKLM
  Or on their computer, to join it:           chronicle hub join https://chronicle.example.com --code ABCD-EFGH-JKLM --share knowledge
```

The invite is printed only once. If you miss it, or it expires, make another:

```bash
docker compose exec hub chronicle hub invite you@example.com
```

Open the link to use the dashboard as the admin. An invite opens one browser or joins one computer, so to also send
what your own computer learns, make a second invite with the command above and run its join command on your computer.

The container won't serve anything until the hub has an admin. A hub with no people lets in anyone who reaches it
as an admin, so a start without `CHRONICLE_ADMIN_EMAIL` stops with an error and serves nothing.

## Invite your team

In the dashboard, **Team › People** adds people and makes their invites. From the server:

```bash
docker compose exec hub chronicle hub invite "Bob" --email bob@example.com --all-projects
docker compose exec hub chronicle hub invite "Vic" --email vic@example.com --role readonly --project web-app
docker compose exec hub chronicle hub people
```

Commands run in the container act as an admin, like commands on any hub computer
([People and roles](devices.md#people-and-roles)). Requests through the dashboard never do: the container sets
`[server] behind_proxy`, so everyone who opens the dashboard signs in, admins included.

The hub in the container never runs a session in your repositories, so it doesn't know their git remotes. After
joining, each member adds their folder for each project, or their computer shares nothing:
`chronicle hub add-folder ~/work/demo-app --project demo-app`. Sessions in other folders stay on their computer
([Sharing knowledge only](devices.md#sharing-knowledge-only)). To take back what a computer sent:
`docker compose exec hub chronicle hub purge bob@example.com --project demo-app`
([Taking back what a computer sent](devices.md#taking-back-what-a-computer-sent)).

## What the hub takes

On its first start, the container sets two settings that an admin can change later:

| Setting | Value | Meaning |
|---|---|---|
| `[hub] accept` | `"knowledge"` | The hub turns away a computer that sends transcripts. |
| `[hub] shared_token` | `false` | Computers join with an invite of their own, not the hub's one token. |

To let the hub take transcripts and analyze them itself, it needs a model provider's API. The image doesn't include
Claude Code or Codex, so they can't be used here:

```bash
docker compose exec hub chronicle config set hub.accept everything
docker compose exec hub chronicle config set analysis.backend anthropic
docker compose exec hub chronicle config set-key anthropic   # asks for the key
docker compose restart hub
```

[Model providers](analysis.md#model-providers) lists the others.

## Settings

The container sets up `config.toml` from these variables on every start. A variable that is set wins over
`config.toml`; one that is unset or empty leaves it as it is. Other settings stay in `config.toml`. Change them with
`docker compose exec hub chronicle config set ...` and restart the hub.

| Variable | Default | |
|---|---|---|
| `CHRONICLE_HUB_URL` | (required) | The address computers and browsers reach the hub at. It becomes `[hub] address`, and its host name joins `[server] allowed_hosts`. `compose.yaml` sets it from `CHRONICLE_DOMAIN`. |
| `CHRONICLE_ADMIN_EMAIL` | (required at first) | The first admin, added when the hub has no people. |
| `CHRONICLE_ADMIN_NAME` | the email's first part | Their name. |
| `CHRONICLE_HUB_NAME` | `Chronicle hub` | The name the dashboard shows (`[hub] name`). |
| `CHRONICLE_HOST` | `0.0.0.0` | The address the dashboard listens on. `compose.yaml` sets `127.0.0.1`: the hub shares Caddy's network, so only Caddy reaches it. |
| `CHRONICLE_PORT` | `11524` | The dashboard's port. |
| `CHRONICLE_ALLOWED_HOSTS` | | More names the dashboard answers to, separated by commas. |
| `CHRONICLE_TRUSTED_PROXIES` | `127.0.0.1, ::1` | Addresses of the proxies whose `X-Forwarded-Proto` the hub believes, separated by commas. Set this when your own proxy forwards to the container ([below](#with-your-own-proxy)). |
| `CHRONICLE_TEAM_STORE` | | `postgres` keeps the team store in Postgres, connecting with `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` and `PGSSLMODE`. `compose.yaml` sets all of them. |
| `CHRONICLE_WORK_MINUTES` | `15` | How often the hub reads what computers sent and runs its background work. `0` turns it off. |

Everything the hub keeps is in the `hub-data` volume, at `/data` in the container. The team store's data is in the
`postgres-data` volume.

## Your own certificate

Caddy gets a certificate from Let's Encrypt, which must reach the server on port 80 or 443. For a name only your
company network reaches, give Caddy your company's certificate. Mount it in `compose.yaml` (under `caddy`, add
`- ./certs:/certs:ro` to `volumes`) and add a `tls` line to the `Caddyfile`:

```text
{$CHRONICLE_DOMAIN} {
	tls /certs/chronicle.crt /certs/chronicle.key
	reverse_proxy 127.0.0.1:11524
}
```

With `tls internal`, Caddy makes its own certificate instead. Every computer and browser that uses the hub must then
trust Caddy's root certificate.

## With your own proxy

Without `compose.yaml`, run the image alone and put your own HTTPS proxy (nginx, a load balancer) in front of it, as
in [Reaching the hub without Tailscale](devices.md#reaching-the-hub-without-tailscale):

```bash
docker run -d --name chronicle-hub --restart unless-stopped -p 11524:11524 -v chronicle-hub:/data \
  -e CHRONICLE_HUB_URL=https://chronicle.example.internal -e CHRONICLE_ADMIN_EMAIL=you@example.com \
  -e CHRONICLE_TRUSTED_PROXIES=10.0.4.12 ghcr.io/chatixia-ai/chronicle-hub
```

Set `CHRONICLE_TRUSTED_PROXIES` to the proxy's address as the container sees it, so the hub believes the proxy's
`X-Forwarded-Proto` and marks its sign-in cookies `Secure`. For a proxy on the same server reaching a published port,
that is usually Docker's bridge gateway, `172.17.0.1`. Let only the proxy reach port 11524. Without a team store, computers that share get no teammates'
lessons back. Add Postgres with `CHRONICLE_TEAM_STORE=postgres` and the `PG*` variables.

## Update

```bash
docker compose pull
docker compose up -d
```

To stay on one version, set `CHRONICLE_VERSION` in `.env` (e.g. `0.13.0`). The dashboard can't update a container:
**Status** says to pull the new image instead.

## Back up

Copy the hub's database while it runs, and dump the team store:

```bash
docker compose exec hub python -c "import sqlite3; sqlite3.connect('/data/chronicle.db').backup(sqlite3.connect('/data/backup.db'))"
docker compose cp hub:/data/backup.db ./chronicle-backup.db
docker compose exec -T postgres pg_dump -U chronicle chronicle > team-store.sql
```

Never copy `chronicle.db` itself while the hub is running: the copy can be corrupted.
