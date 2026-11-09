---
name: port-from-master
description: Port improvements from your private Claude Code harness into this public workbench repo, sanitized. Use when working in this repo and the user says "port", "sync from master", "process the port inbox", or asks what changed in the private harness.
---

# Port from master

Maintainer tool. Your private harness (your real `~/.claude`, private project rules, private mods) keeps evolving; a `PostToolUse` hook there appends one line per changed harness file to `.port/inbox.md`, and `wb-note "<idea>"` appends improvement ideas. This skill turns those lines into clean, public commits. `.port/` is gitignored: inbox lines carry private paths.

Porting is never automatic: a private file can mix general ideas with private names, people, clients and paths.

## Steps

1. Read `.port/inbox.md`. Work on unticked lines (`- [ ]`), oldest first. Group lines that touch the same feature.
2. For each group, read the private file and decide, telling the user one line per item:
   - **port**: the change is general (a better rule, a fixed bug in a mod, a new hook) → step 3;
   - **reject**: private-only (company rules, specific trackers, people, client paths) → tick it with `rejected: <reason>`;
   - **ask**: unclear → AskUserQuestion before touching anything.
3. Port by re-writing, not copying: apply the idea to the matching workbench file (`core/`, `optional/`, `install.sh`), in English, with generic names. Never paste private text wholesale.
4. Run `tests/run.sh` (includes `scripts/check-leaks.sh` against the private denylist). Fix until it passes.
5. Show the user the diff and the proposed commit message. Commit only when they approve. Never push without an explicit OK.
6. Tick the ported lines: `- [x] ... → <commit sha>`.

## Rules

- Follow `oh-my-claudecode:minimal-code-discipline` for code.
- The denylist lives outside the repo (`~/.config/workbench/denylist`); add any newly found private term there, never in the repo.
- A port that changes installer behaviour needs a test in `tests/run.sh`.
