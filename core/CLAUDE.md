## Workbench rules

Apply to any non-trivial task: code, analysis, documents, data, planning, operations.
On trivial requests, use judgment. Project rules (`CLAUDE.md` / `AGENTS.md` in the repo) win on conflict.

### Guidelines (adapted from andrej-karpathy-skills, MIT)

1. **Think before acting.** State assumptions. If there is more than one reading of the request, show them; do not pick silently.
   If a simpler path exists, say so. If something is unclear, stop, name the doubt and ask.
2. **Simplicity first.** The minimum that solves it. Nothing beyond the request: no single-use abstractions,
   no unrequested "flexibility", no handling of impossible cases.
3. **Surgical changes.** Touch only what is needed and follow the existing style. Do not "improve" what sits next to it.
   Someone else's dead code: mention it, do not delete it. Clean up only what your own change orphaned.
4. **Goal-driven execution.** Turn the task into a verifiable criterion (bug → a test that reproduces it and then passes;
   refactor → tests pass before and after). In multi-step tasks, state the plan with `→ verify:` per step and iterate until verified.

### Working agreements

- **Announce the skill** before each relevant action: `[SKILL: <name>] <action> | why: <one sentence>` (details in the `work-mode` skill).
- **Done means verified.** Before saying "done", list what was **verified** (what and how) and what was **not verified**.
- **Outbound writes are drafts first.** Push, PR, deploy, migrations, messages, tickets and comments on external services:
  prepare them, then ask. The user approves and sends.
- **Critical review = annotate and question.** Never rewrite the original unless explicitly asked.
- **Code changes** follow `oh-my-claudecode:minimal-code-discipline`, including inside subagent prompts.
- **Subagents** always get an explicit `model`; see the `parallel-delegation` skill.
- **Context at ~60-70%:** propose a session handoff at the next task boundary (`handoff` skill).
