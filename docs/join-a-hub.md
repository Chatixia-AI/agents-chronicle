# Joining your team's hub

[← Chronicle](../README.md) · [Docs index](README.md)

Your team runs a Chronicle hub, and its admin sent you a command like this one:

```bash
chronicle hub join https://chronicle.example.com --code XXXX-XXXX-XXXX --share knowledge
```

This page takes you from that command to sharing what your coding agents learn in your team's project, and getting
your teammates' lessons back. It takes about five minutes. Whoever runs the hub follows
[A hub in Docker](docker.md).

## What is shared

- **Sent to the hub:** for the projects the admin gave you, each analyzed session's summary and project lessons,
  with its details (times, counts, models).
- **Never sent:** your prompts, transcripts, files and commands; lessons about you, such as your preferences;
  sessions in any other project; chats you imported from ChatGPT or claude.ai.
- **Your own computer still analyzes your sessions,** with your own Claude Code, Codex or model provider, as it did
  before. The hub analyzes nothing.

## 1. Install Chronicle

Skip this if Chronicle is already installed.

```bash
uv tool install --python 3.13 agents-chronicle
chronicle install
```

[Install](install.md) explains the choices `chronicle install` offers.

## 2. Join the hub

If your computer already sends to another hub, leave it first:

```bash
chronicle hub leave
```

Then run, in a terminal, the `chronicle hub join …` command your admin sent you. It lists the projects you share:

```text
Projects you share with it: Website. Add your folder for each one: …
```

A code works once, for 7 days. Opening it as a link in your browser also uses it up, so for this step ask your
admin for the `chronicle hub join` command, not the link.

## 3. Add your project folder

Tell the hub where the project is on your computer:

```bash
chronicle hub add-folder ~/code/website --project Website
```

Use your folder for the project and the project's name from step 2. This sends what your computer has already
analyzed there. A clone of a git repository the hub already knows is filed under its project without this step,
but running it does no harm.

Your dashboard can do the same: **Settings › Devices › Projects on the hub › Join a project**, then pick the project
and your folder.

## 4. Check

```bash
chronicle hub status
```

It shows the hub's address, when your computer last sent, and how many of your teammates' lessons it holds. Your
dashboard's **Settings › Devices** shows the same. **Open the hub's dashboard** there signs you in to the hub's
dashboard, where you see your projects.

## From then on

- **After each analysis,** your computer sends the project's new summaries and lessons. `chronicle push`, or
  **Share now** in **Settings › Devices**, sends right away.
- **Each time it sends,** it gets back what your teammates learned in the project. Your agents find those lessons
  through Chronicle's MCP tools, marked as teammates'. With start-of-session notes on (`chronicle install
  --inject-context`), new sessions also list them under "From teammates' sessions".
- **Your own dashboard** keeps showing your own sessions, as before.

To stop sharing to one project, choose **Leave** next to it in **Settings › Devices** (or run `chronicle hub leave
--project <name>`). What you shared there stays on the hub. Added the wrong folder? **Remove** next to it takes the
folder back, and the hub deletes what your computer shared from it. To stop sending altogether, choose **Leave the
hub…** (or run `chronicle hub leave`). What you already sent stays on the hub.

## If something goes wrong

- **The code doesn't work.** It was used already, or it is more than 7 days old. Ask your admin for a new one.
- **"this hub takes knowledge only".** Your computer was set to send transcripts. Run
  `chronicle config set hub.share knowledge`, then `chronicle push`.
- **"This computer is a hub itself".** Your computer is a hub that other computers may send to. Check with
  whoever set it up, then run `chronicle hub disable` before you join.
- **A certificate error.** Your computer doesn't trust the hub's HTTPS certificate. Tell your admin.
