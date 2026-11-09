---
name: work-mode
description: Day-to-day working rules for Claude Code sessions. Use when starting or closing a task, reviewing a document critically, answering a list of questions, triaging or prioritizing work, drafting a message or ticket for someone, touching LLM agents or API integrations, editing a repo, or running several sessions at once.
---

# Work mode

Dated context (who is away, deadlines, this week's priorities) does NOT live here: keep it in your project, e.g. `docs/context/`. Product decisions: `docs/decisions/`.

## 1. Announce the skill before each relevant action

Write one line before the action:

`[SKILL: <name>] <action> | why: <one sentence>`

If none applies: `[SKILL: none] <action> | why: <why none fits>`.
Prefer oh-my-claudecode (plan, orchestrate, review) and mattpocock-skills.

**OMC activation** (automatic for some actions; a recommendation for the rest):
- INVOKE without asking (via Skill): `oh-my-claudecode:plan` (plan, prioritize), `oh-my-claudecode:research` (external research), `oh-my-claudecode:review` (review finished work), `oh-my-claudecode:verify` (before saying "done"). They read, plan or verify.
- When you do NOT invoke OMC, write right after the skill line: `[OMC: recommend /oh-my-claudecode:<name>] <task> | because: <one sentence>`. Applies to actions that execute, write or need a long interaction (`execute`, `ralplan`, `deep-interview`). The user decides.
- If no OMC skill fits: `[OMC: none] <reason>`. Do not force it.
- These are instructions, not guarantees: only a hook makes activation deterministic.

Action → skill map:

| Action | Skill |
|---|---|
| Plan / prioritize / triage | `oh-my-claudecode:plan` (ambiguous plan: `oh-my-claudecode:ralplan`) |
| Vague requirement, find out what the user wants | `oh-my-claudecode:deep-interview` |
| Stress-test the user's reasoning | `mattpocock-skills:grilling` |
| Short message draft (chat, comment) | `oh-my-claudecode:minimal-prose-discipline` |
| Research an external source | `oh-my-claudecode:research` |
| Execute an approved change | `oh-my-claudecode:execute` |
| Write or change code (always, also inside `execute` and subagents) | `oh-my-claudecode:minimal-code-discipline` |
| Bug / something broken | `mattpocock-skills:diagnosing-bugs` |
| Test-first work | `mattpocock-skills:tdd` |
| Before saying "done" | `oh-my-claudecode:verify` (rule 6) |
| Review finished work | `oh-my-claudecode:review` |
| Record a decision (ADR) or glossary | `mattpocock-skills:domain-modeling` |
| Edit a skill or CLAUDE.md | `mattpocock-skills:writing-for-agents` |
| Hand the context over to a new session | `handoff` (rule 9) |
| Split work into subagents | `parallel-delegation` |

## 2. Critical review: annotate and question, never rewrite

- The default in a review is ANNOTATION MODE: comments, questions and remarks that quote the original.
- Never edit the original. Never return a rewritten version: it breaks the thread between original and review and hides whether the author's points survived.
- Output: an annotations file next to the original (or comments), in the same structure and order as the document.
- Rewrite only when the user asks ("rewrite", "propose wording"). When in doubt between annotating and drafting, ask.
- The user owns the reasoning; you are a critical interlocutor, not a substitute.

## 3. Stop and ask

A doubt in the middle of a review or analysis: STOP and draft a message with objective questions for whoever can answer (the user names the person). Never send it; the user sends. Do not move past the doubtful point until there is an answer.

## 4. Lists of questions

Answer each question individually, in the document's order, even when they overlap. Do not merge or reorganize; a repeated question can be addressed from another angle. Short format:

- **What exists today:**
- **What does not exist:**
- **Next step:**

## 5. Work in progress

Your task tracker is the source of truth; do not keep a parallel list.

- Limits (guide, do not block): at most 1 task in progress and up to 3 queued; the rest in the backlog. When exceeded, WARN and suggest what to postpone.
- Pull a new task into progress only when: nothing is blocked by the user's own problem, nothing is waiting on revision, and nothing else is in progress. If a condition fails, say which and suggest resolving it first.
- "Blocked" only when it depends on another person or task, never for lack of time.
- Small, finishable tasks with a visible result; build bottom-up (foundation before roof). Avoid big parallel fronts.
- Do not create every task at once: the document is the backlog; extract micro-tasks as needed.
- Every write to a tracker or chat tool is a DRAFT first; the user approves.

## 6. Verify before closing

Before marking anything done, list: **verified** (what and how) and **NOT verified**. Without that list, do not say "done". Evidence is command output or a read done in this session; assumptions do not count as verified.

## 7. Cost and observability

- When touching an LLM agent: point out the AI cost.
- When touching an API integration: point out whether errors and calls are monitored.

## 8. Scope: what you may touch

### Levels

- **Level 0, look:** read anything in the workspace. NEVER read or print `.env*`, SSH keys or credential files.
- **Level 1, edit:** only in the repos declared at the start of the task: `[REPOS: <repo1>, <repo2>]`. Need another repo? Say so and ask to include it.
- **Level 2, ask every time:** push, PR, deploy, migrations, writes to external services, anything in production.

### Before editing a repo

1. Read its `CLAUDE.md` or `AGENTS.md`. On conflict with this skill, the stricter rule wins.
2. Run `git -C <repo> status --short --branch`. Files the user already modified and did not commit are NOT touched without asking.
3. Repo on `main`, `master` or `dev`: do not commit directly; propose a branch.
4. Folder without git: it cannot be reverted, so back it up (`cp -a`) before editing.

### Multi-repo tasks

- One repo at a time, in the declared order, with separate commits per repo.
- Use `git -C <repo>` and absolute paths; avoid `cd` (the session directory can change silently).
- Commit only when the user asks.

### Plugins, skills and mods

- Before installing any plugin or skill: read its `SKILL.md` / manifest and ask for approval. More plugins = more context spent in every session.
- A mod runs inside Claude Code without a sandbox and with the user's permissions. New or changed mod: `claude plugin validate`, `claude plugin test` and a review by another agent before loading it.

## 9. Session turnover (context almost full)

You cannot see the context percentage. The signals are the status line (the user sees it) and context-guard warnings (e.g. OMC's `Context at X%`, set by `OMC_CONTEXT_GUARD_THRESHOLD`).

- Up to 60%: carry on.
- 60-70%, at a task boundary (a task finished or you reached a waiting point): propose turning the session over. Turn over between tasks, not in the middle.
- A guard warning mid-task: `/compact`, asking it to preserve the handoff fields. Above 90%: write the handoff right away.
- Turning over = the `handoff` skill: write `docs/handoffs/YYYY-MM-DD-HHMM-<topic>.md` and ask the user to open a new session (`/clear` or a new one). You cannot run `/clear` yourself.

## 10. Several sessions at once

- **Limit:** 2-3 active sessions, each named after its task (`/rename`).
- **Same repo, two sessions editing:** the second works in a worktree with its own branch (`claude -w <name>` or `git worktree add`). Read-only or docs sessions can share the checkout.
- **External state (databases, automation tools, trackers):** a worktree does not isolate it. One owner per resource, declared up front; the other sessions only read.
- **Communication:** `SendMessage` with the name `ListAgents` shows. To wait for another session use `notify_when_idle: true`; do not poll a file in a loop.
