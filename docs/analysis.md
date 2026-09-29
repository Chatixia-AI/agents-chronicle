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

![How a session becomes knowledge: queue, digest, claude -p, JSON validation, knowledge items, knowledge bases, glossary and weekly review](diagrams/analysis.excalidraw.svg)

1. A session is queued once it ends (hook) or has been idle for `idle_minutes`.
2. The transcript is condensed into a digest at the richest detail level that fits `chunk_chars`
   (full prompts and replies, one line per tool call, error excerpts, subagent reports). Very long
   sessions are split at prompt boundaries and map-reduced. Secrets are redacted first.
3. `claude -p` runs with `--no-session-persistence --safe-mode --tools "" --strict-mcp-config`:
   no transcript is written for the analysis itself, no hooks/plugins/MCP load, and the model can only answer.
   `CHRONICLE_INTERNAL=1` makes the hooks inert for these runs.
4. The JSON reply is validated leniently (with one repair pass) and stored. When a project gains
   `min_new_items` new items, its knowledge base is re-synthesized; items that are outdated or
   duplicated get marked *superseded* (pinned and memory items are never superseded). Once every session of
   a finished week is analyzed, Claude writes that week's review (themes, accomplishments, learnings, open
   threads, recurring friction, concrete workflow suggestions).
5. Usage-limit or auth errors pause analysis for an hour; other failures back off 30 min → 2 h → 8 h.
   Calls have a wall-clock deadline, and a call frozen by the Mac going to sleep is killed right after wake and
   re-queued without counting as a failure. Sessions that continue after being analyzed are re-analyzed.

Cost: analysis runs through your Claude Code login. The reported cost is the API list-price equivalent: sessions
averaged about $0.38 each with Sonnet (digests average ~150k characters). On a Claude subscription that is drawn
from the plan's usage allowance rather than billed. `chronicle analyze --pending --dry-run` sizes a backlog, and
`max_budget_usd` caps each call.
