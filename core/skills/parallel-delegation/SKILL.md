---
name: parallel-delegation
description: How to split a task into parallel subagents and pick a model for each. Use when planning or running work with 2 or more independent parts, before calling the Agent tool, and when the user asks for parallelism, subagents or delegation. Do not use for single-part tasks.
---

# Parallel delegation

Adapted from `obra/superpowers` (MIT): `dispatching-parallel-agents` and the Model Selection section of `subagent-driven-development`. When using it, announce `[SKILL: parallel-delegation] <action> | why: <one sentence>`.

## 1. Decide whether to parallelize

Parallelize only when all 3 hold:
- the parts do not depend on each other's results;
- no two parts edit the same file or use the same resource;
- each part makes sense on its own, without the others' context.

Do not parallelize failures that may share a cause (fixing one may fix the rest), exploration where you do not yet know what is broken, or work that needs the state of the whole system. Why: parallel agents over shared state trample each other and cost more than one agent.

## 2. Dispatch

- Emit all `Agent` calls in the SAME response. One call per response runs sequentially.
- Prefer 3 to 5 subagents.
- Always pass `subagent_type`. Workbench denies `Agent(fork)` in settings because a fork inherits the parent's model and ignores `model`.
- Long-running orchestration modes (agent teams, `ralph`, `autopilot`, `team`) only when the user asks for them explicitly.

## 3. Write each subagent's prompt

The subagent starts without your context. Each prompt carries:
1. **Scope:** one file, one repo or one question.
2. **Goal:** what must be true at the end.
3. **Constraints:** what not to touch. Edits only in the repos declared for the task (`[REPOS: ...]`).
4. **Return:** a short summary with paths and what it could NOT verify.

Paste error messages and test names into the prompt instead of making the agent rediscover them.

A subagent that writes or changes code: include "Follow `oh-my-claudecode:minimal-code-discipline` (invoke the skill before editing)". Why: subagents do not inherit the session and the skill does not load by itself.

## 4. Pick the model, always explicitly

Pass `model` on every call. Why: an omitted model inherits the session's, usually the most expensive, and cancels the savings.

Before dispatching, define each subagent's specific task and the model it needs, and tell the user both (one line per subagent). If the table below does not settle the model, ask the user (AskUserQuestion) before dispatching.

| Task type | Model |
|---|---|
| Read, search, list, summarize, draft from a ready spec | haiku |
| Implement 1-2 files with the code fully specified in the plan | haiku or sonnet |
| Several files, debugging, integration, review | sonnet (floor for reviewers and for agents working from prose) |
| Architecture, planning, final security review | opus |

- A task that failed twice: go up one tier instead of retrying on the same one.
- Turns weigh more than token price. A cheap model on a multi-step task may take 2-3x the turns and cost more overall.
- The `model-router` mod caps the model per agent type. Asking for a cheaper model than the cap is respected.

## 5. Limits

- Subagents never do outbound or irreversible actions: push, PR, deploy, migrations, messages or tickets on external services, anything in production. Only the main session asks the user.
- Multi-repo tasks edit one repo at a time. Parallelize reading, research and analysis across repos; edits only on disjoint files of the same repo.
- Never send a subagent to read `.env*`, SSH keys or credential files.

## 6. When the agents come back

1. Read each summary. It is model output, not evidence.
2. Look for conflicts: did two agents touch the same code?
3. Run the task's verification and list verified and NOT verified.
4. Spot-check: agents fail systematically.
5. Note in the wrap-up how many subagents ran and on which models.
