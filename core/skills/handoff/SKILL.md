---
name: handoff
description: Write or resume a session handoff so work continues cleanly in a new Claude Code session. Use when context is around 60-70% at a task boundary, when a context-guard warning appears, when the user asks for a handoff or to "turn the session over", and when resuming from a handoff file.
---

# Handoff

A handoff is a short file that lets a fresh session pick up exactly where this one stopped. It lives in the project: `docs/handoffs/YYYY-MM-DD-HHMM-<topic>.md`. The workbench `SessionStart` hook lists the 3 most recent ones when a session starts in that project.

## Writing one

1. Copy [template.md](template.md) to `docs/handoffs/YYYY-MM-DD-HHMM-<topic>.md` (create the folder if missing; folder names cannot contain `/`).
2. Fill every section. Keep it short:
   - Reference other artifacts by path or URL; do not copy them.
   - No secrets (keys, tokens, `.env` contents).
   - Separate **verified** from **NOT verified**.
   - "Next exact step" must be a concrete first action, not a goal.
3. Tell the user the path and ask them to open a new session (`/clear` or a new terminal). You cannot clear the session yourself.

## Resuming

The hook only lists handoffs; it never injects one, because they may belong to another session running in parallel.

1. Resume only the handoff the user names. If they say "resume" without saying which, ask which.
2. Read the file. Before editing anything, re-check `git status --short --branch`, the branch and the cwd of each repo in it, and re-check any external status it mentions (tickets, deploys). The handoff is a lead, not the truth.
3. Continue from "Next exact step".

## Housekeeping

- Before deleting or archiving old handoffs: ask.
- Two sessions must not resume the same handoff and write to the same external resource in parallel.
