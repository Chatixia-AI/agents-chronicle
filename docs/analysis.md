# What gets recorded and how analysis works

[← Chronicle](../README.md) · [Docs index](README.md)

## Recorded for every session

Per session: project, branch, Claude Code version, start/end, wall and active time (idle gaps over
15 min excluded), human prompts (including ones queued while Claude worked), slash commands,
interrupts, compactions, every tool call with duration and success, files read/edited with
line counts, subagents and workflows with their own usage, skills, MCP servers, hooks, PRs and
artifacts, and token usage per API call (deduplicated per message) with an API-list-price cost
estimate. Estimates match Claude Code's own `cost-state` to the cent for single-process sessions;
subscription billing differs.

Per analyzed session: title, summary, goal, outcome, work types, tags, highlights, open threads,
friction, sentiment, and knowledge items:

| Kind | Meaning |
| --- | --- |
| fix | a failure, its root cause, and the fix |
| gotcha | a pitfall and how to avoid it |
| learning | an insight about a technology or the codebase |
| decision | a design choice and its rationale |
| pattern | a reusable technique or snippet |
| command | a useful invocation |
| fact | project layout, config, endpoints, deployment |
| preference | how you want Claude to work |
| reference | an external pointer |
| todo | a follow-up |

Claude's own auto-memory notes (`projects/*/memory/*.md`) and Codex's memory notes are imported as knowledge too.

Codex, Copilot and Bob sessions fill the same fields wherever their logs carry the data: Copilot Chat logs, for
instance, have no cache split (so no cost estimate), and Bob tasks have no per-call timings.

## How analysis works

![How a session becomes knowledge: queue, digest, claude -p or codex exec, JSON validation, knowledge items, knowledge bases, glossary and weekly review](diagrams/analysis.excalidraw.svg)

1. A session is queued once it ends (hook) or has been idle for `idle_minutes`.
2. The transcript is condensed into a digest at the richest detail level that fits `chunk_chars`
   (full prompts and replies, one line per tool call, error excerpts, subagent reports). Very long
   sessions are split at prompt boundaries and map-reduced. Secrets are redacted first.
3. The digest goes to the agent chosen in `analysis.backend`, through your own login, sandboxed so that no
   session is written for the analysis itself, none of your hooks, plugins, MCP servers or instruction files load,
   and the model can only answer:
   - **Claude Code** (`backend = "claude"`, the default): `claude -p --no-session-persistence --safe-mode
     --tools "" --strict-mcp-config`.
   - **Codex** (`backend = "codex"`): `codex exec --ephemeral --ignore-user-config --sandbox read-only`, with
     every tool feature switched off (shell, code execution, sub-agents, apps, plugins, web search, images),
     hooks, `AGENTS.md` and skill instructions off, and Chronicle's instructions in place of Codex's own. Codex
     cannot switch off every tool by flag, so Chronicle also reads its event stream: a reply that follows any tool
     call is thrown away and the analysis counts as failed.

   `CHRONICLE_INTERNAL=1` makes Chronicle's own hooks inert for these runs. Switch agents in **Status ›
   Analysis**, with `chronicle config set analysis.backend codex`, or for one run with `chronicle analyze
   --backend codex`.
4. The JSON reply is validated leniently (with one repair pass) and stored. When a project gains
   `min_new_items` new items, its knowledge base is re-synthesized; items that are outdated, contradicted or
   duplicated get marked *superseded*, each naming the item that replaced it (pinned and memory items are never
   superseded). A duplicate also counts as a confirmation: see [how knowledge earns trust](#how-knowledge-earns-trust). Once every session of
   a finished week is analyzed, the model writes that week's review (a three-line TL;DR, themes, accomplishments,
   learnings, open threads, recurring friction, concrete workflow suggestions). Knowledge bases, the playbook and
   reviews are written to be skimmed: a TL;DR, a short overview, a title per knowledge-base bullet, and word
   limits on every field. The review's numbers and charts come from the database, not from the model.
5. Usage-limit or auth errors pause analysis for an hour; other failures back off 30 min → 2 h → 8 h.
   Calls have a wall-clock deadline, and a call frozen by the Mac going to sleep is killed right after wake and
   re-queued without counting as a failure. Sessions that continue after being analyzed are re-analyzed.
   A session that is not analyzed yet always says why: on its page, in **Status › Analysis** (a count per
   reason) and in `chronicle status`. *Queued* reasons clear by themselves (ready for the next run, still active,
   waiting to retry); *held* ones need a change first (project excluded, too few prompts, from before install
   with backfill off, failed four times). When the whole queue is stopped (paused for a usage limit, automatic
   analysis off, or the analyzer not found), that is said too.

## How knowledge earns trust

Every knowledge item has a stage, which says how far it has been confirmed:

| Stage | Shown as | Earned by |
| --- | --- | --- |
| `wip` | tentative | one session, and the analysis was unsure (low confidence) |
| `provisional` | seen once | one session |
| `established` | established ×N | the same lesson in 2 or more sessions; also Claude Code and Codex memory notes, and items you add |
| `canonical` | canonical ×N | the same lesson in 3 or more sessions spread over at least 14 days, or pinned by you |

The evidence comes from synthesis: when it finds that an item from one session states the same lesson as an item
from another, it reports the pair as a duplicate, and the surviving item takes over the other's sessions. The
stage is then computed from those sessions and their dates, not judged by the model, and the reason is stored
with it ("confirmed in 3 sessions over 19 days (2026-09-01 → 2026-09-20)"). Items that are merely related stay
separate, and the cross-project playbook pools evidence without retiring anything. Re-analyzing a session keeps
what its items had earned.

Stages are used wherever knowledge is read: searches and the SessionStart digest list the most trusted items first,
the MCP tools label each item (`[gotcha · established ×3]`), knowledge-base bullets carry the stage of their best
source, and syntheses see each item's stage. Leaving the ladder is a status, not a stage: a superseded item keeps
its stage and names its successor, and when an established or canonical item is overturned by a newer one (not
just merged as a duplicate), that week's review lists it under **Overturned**.

Cost: analysis runs through your own Claude Code or Codex login. With Claude, the reported cost is the API
list-price equivalent: sessions averaged about $0.38 each with Sonnet (digests average ~150k characters), and
`max_budget_usd` caps each call. Codex reports tokens but no price, so Codex analyses show no cost. On a Claude or
ChatGPT subscription the usage is drawn from the plan's allowance rather than billed. `chronicle analyze --pending
--dry-run` sizes a backlog before you spend anything.
