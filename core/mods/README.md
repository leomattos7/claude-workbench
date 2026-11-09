# Claude Code mods

Two local mods written against the official Claude Code mods contract (requires Claude Code >= 2.1.287).
A mod runs inside Claude Code, unsandboxed, with your permissions. These two do not use `tool.check`,
`http.fetch`, `process.run`, `fs.*` or `prompt.submit`: they do not approve tools, run processes, touch the
network, or submit prompts on your behalf.

| Mod | What it does |
|---|---|
| `model-router` | On `agent.spawn`, caps each subagent's model at its agent type's ceiling (haiku/sonnet). Never upgrades a model, leaves forks alone, fails open. |
| `session-board` | Publishes the session to `$.store`, warns once at 65% context, and offers `/board` to list open sessions. |

## Router policy

| Subagent type | Ceiling |
|---|---|
| `explore`, `writer`, `executor`, `debugger`, `test-engineer`, `qa-tester`, `designer`, `tracer`, `git-master`, `scientist`, `verifier` | sonnet |
| `document-specialist`, `architect`, `critic`, `planner`, `security-reviewer`, `code-reviewer`, `analyst`, `general-purpose`, `Plan` | unchanged |

- The caller may ask for `model: haiku` on any type; that is respected (the ceiling only limits upward).
- With no `model` in the call, the router does nothing: the agent definition's model applies. With `inherit`, the parent's model applies and is only ever lowered to the ceiling, never raised.
- Documentation-research agents are left out on purpose: that work is multi-step, and a cheaper model may need more turns.
- Only `oh-my-claudecode:*` agents and native names (for example `Explore`) are recognized; agents from other plugins are left untouched.
- **Forks inherit the parent's model and ignore `model`**, so the router cannot cap them. Deny them in settings (see Activate) so every subagent goes through `agent.spawn` with an explicit model.
- `WORKBENCH_MODEL_ROUTER=observe` reports what would change (as a toast) without changing anything. Any other value enforces.
- If the hook fails before calling `next`, Claude Code skips it and the spawn proceeds normally (fail-open, on purpose). The `gating hook without .catch` warning from `claude plugin validate` is expected.

## Session board

- Publishes `{ id, cwd, model, percent, updatedAt }` under `s:<session id>` in `$.store` after each context measurement, and removes it on session end.
- Warns once when context reaches 65%; re-arms after it drops below 50% (compaction, `/clear`).
- `/board` lists live sessions, newest first, marking the current one. Entries older than 2 hours or malformed are dropped. Store values are treated as untrusted data: control, invisible and bidi characters are replaced and lengths capped.

## Verify

```bash
cd core/mods/<mod> && claude plugin validate . && claude plugin test
```

## Activate

- In `~/.claude/settings.json`, set `env.CLAUDE_CODE_PLUGIN_DIRS` to the absolute paths of both mod directories, separated by `:`.
- In the same file, set `permissions.deny` to include `"Agent(fork)"`.
- Reload with `/reload-plugins` or restart Claude Code; check with `/plugin`.

## Disable

- Remove the paths from `CLAUDE_CODE_PLUGIN_DIRS`, or run `claude --safe-mode` for one session.
- Remove `Agent(fork)` from `permissions.deny` to restore default fork behavior.

## Known limits

- Not verified: whether `agent.spawn` fires for agents started by other orchestration layers or by the `Workflow` tool.
- Concurrent writes to `$.store` from several sessions: the docs do not say whether this is safe; the worst case is a stale board.
- Cross-session messaging stays native (`ListAgents`/`SendMessage`, `/list-agents`); `session-board` only displays the board.
