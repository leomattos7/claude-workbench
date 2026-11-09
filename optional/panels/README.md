# panels

Removes the duplication between the status line and the panels above the prompt.

The oh-my-claudecode HUD (bottom) shows context (`ctx`) and quota (`5h`, `wk`). The `context-bar` and
`orca-quota` plugins draw the same numbers, with more detail, above the prompt. With both you read the
same data twice.

`--with panels` sets two HUD elements to `false` in `settings.json` under `omcHud.elements`:
`contextBar` and `rateLimits`. The HUD keeps profile, model, effort and session time.

- Not part of `--all`: it removes information, and it only makes sense if you add the panels below.
- It never overrides a value you already set (a `contextBar: true` of yours stays).
- `./uninstall.sh --with panels` removes exactly what was added.

## The panels (not installed by workbench)

| Plugin | Shows | Install |
|---|---|---|
| `context-bar` ([hamzafer/claude-code-mods](https://github.com/hamzafer/claude-code-mods)) | Context window by category, tokens, compaction point | `claude plugin marketplace add hamzafer/claude-code-mods && claude plugin install context-bar@claude-code-mods --scope user` |
| `orca-quota` ([mutlumehmet/claude-plugins](https://github.com/mutlumehmet/claude-plugins)) | 5h and weekly quota | `claude plugin marketplace add mutlumehmet/claude-plugins && claude plugin install orca-quota@mehmetmutlu --scope user` |

They are third-party code that runs inside Claude Code, unsandboxed, with your permissions (the same
caveat as [core/mods](../../core/mods/README.md)). Workbench does not install or pin them: read them first.
Versions in use when this was written: context-bar 0.1.5, orca-quota 0.2.8.

## Undo by hand

Delete `omcHud.elements.contextBar` and `omcHud.elements.rateLimits` from `settings.json`, or run `/oh-my-claudecode:hud` and turn them back on.
