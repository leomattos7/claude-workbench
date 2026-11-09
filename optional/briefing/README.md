# briefing

A short morning briefing built from your git repositories. No task tracker needed.

Each weekday run collects facts (commits since the previous workday, current branch, uncommitted
change count, the latest 3 handoffs in `<repo>/docs/handoffs/*.md`, plus an optional notes file),
sends them to `claude -p`, and saves `$OUT_DIR/YYYY-MM-DD.md`. The call is text in, text out:

- `--tools ""` disables every built-in tool (no Bash, file or web access).
- `--strict-mcp-config` (with no `--mcp-config`) skips every MCP server.
- `--safe-mode` disables customizations: CLAUDE.md, skills, plugins, hooks, custom commands and
  agents. Admin-managed (policy) settings still apply.

The input is **untrusted**: commit subjects (from `git log --all`, so also branches you did not
write) and handoff titles can contain text meant to steer the model. With the isolation above the
worst case is a misleading briefing, so treat the output as a summary, not as instructions.

**Cost: every run calls Claude and spends tokens** (one short request per day). `--dry-run` calls nothing.

## Installed

| What | Where |
| --- | --- |
| `workbench-briefing` CLI | `~/.local/bin/workbench-briefing` |
| `collect.py`, `prompt.md` | `~/.local/share/workbench/briefing/` |
| default config (only if none exists) | `~/.config/workbench/briefing.conf` |

Cron is **not** installed by setup.

## Usage

```bash
bash setup.sh                       # install
$EDITOR ~/.config/workbench/briefing.conf   # set REPOS, OUT_DIR, MODEL, NOTES_FILE, NOTIFY
workbench-briefing --dry-run        # print collected facts and the claude command; nothing written
workbench-briefing                  # generate today's briefing (once per day)
workbench-briefing --force          # regenerate
workbench-briefing --no-notify      # skip the notification
workbench-briefing --install-cron   # opt-in: 07:30 Mon-Fri, between "# workbench-briefing" markers
workbench-briefing --uninstall-cron
```

Notification: `$CLAUDE_CONFIG_DIR/hooks/workbench/notify.sh` (default `~/.claude/...`) if present (the `wsl` optional), else
`notify-send`, else nothing. Log: `$OUT_DIR/.log`.

## Uninstall

```bash
workbench-briefing --uninstall-cron   # if you enabled cron
bash setup.sh --uninstall             # keeps your config and briefings
```
