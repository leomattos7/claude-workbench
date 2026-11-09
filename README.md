# workbench

A working setup for [Claude Code](https://docs.claude.com/en/docs/claude-code): rules, skills, mods and hooks that make long, multi-session work predictable. It covers planning before coding, verifying before saying "done", cheap subagents and clean handoffs between sessions.

It builds on [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) for orchestration and adds the glue a daily driver needs.

## Install

```bash
git clone https://github.com/leomattos7/workbench && cd workbench
./install.sh --dry-run --all     # see what would change; writes nothing
./install.sh --all               # or: ./install.sh --with vault,wsl
```

Then open Claude Code and run `/oh-my-claudecode:omc-setup` once. It adds the OMC rules block and the status line HUD.

Requirements: Linux or WSL, `git` and `python3`. Claude Code must already be installed. `node` 20+ is needed for the HUD, and Claude Code ≥ 2.1.287 for the mods (older versions skip them with a warning). macOS is untested.

## What you get

### Core (always installed)

| Piece | What it does |
|---|---|
| **Rules** (`CLAUDE.md` block) | Think before acting, simplicity first, surgical changes, verifiable goals. "Done" always comes with a verified / not verified list. Outbound writes are drafts until you approve. |
| **`work-mode` skill** | Day-to-day agreements: announce the skill in use, annotate instead of rewriting in reviews, work-in-progress limits, scope levels (look / edit declared repos / ask every time), session turnover, several sessions at once. |
| **`parallel-delegation` skill** | When to split work into subagents, how to brief them, and which model each one gets (always explicit). |
| **`handoff` skill + `SessionStart` hook** | At ~60-70% context Claude writes `docs/handoffs/YYYY-MM-DD-HHMM-<topic>.md`. The next session in that project gets the 3 most recent handoffs listed, never auto-injected. |
| **`model-router` mod** | Caps each subagent's model by agent type (e.g. explorers and executors at sonnet). Never upgrades a model. [Details](core/mods/README.md) |
| **`session-board` mod** | Warns once at 65% context; `/board` lists open sessions. |
| **Safe defaults** | Denies the `Read` tool on `.env*` and `~/.ssh`. Asks before `git push`, `gh pr create/merge` and `gh repo delete`. Denies `Agent(fork)` so every subagent gets an explicit model. Context guard at 70%. These are pattern rules, so variants such as `git -C dir push` or `cat .env` are not caught. |
| **Plugins** (from their marketplaces) | `oh-my-claudecode` (pinned v5.7.31), `mattpocock-skills`, `andrej-karpathy-skills`. |

### Optionals (`--with <name>`, or `--all` for all but `panels`)

| Name | What it does |
|---|---|
| `vault` | A second brain (LLM wiki, Karpathy model). Drop sources in `raw/` and Claude builds linked pages in `wiki/`, then answers from them. [Details](optional/vault/README.md) |
| `accounts` | Several Claude accounts with one shared config: `claude-account add work` gives you `claude-work`. [Details](optional/accounts/README.md) |
| `wsl` | A Windows toast when a session needs you (falls back to `notify-send` on Linux), plus `import-from-windows` to copy files from Downloads without secrets. [Details](optional/wsl/README.md) |
| `briefing` | A morning summary from your git repos and handoffs, run through `claude -p` with built-in tools, MCP servers and customizations disabled. Opt-in cron, and it costs tokens per run. [Details](optional/briefing/README.md) |
| `panels` | A lean status line: turns off the HUD's context and quota items so they are not shown twice next to the `context-bar` and `orca-quota` panels. Opt-in by name (not in `--all`); the panels are third-party and installed by you. [Details](optional/panels/README.md) |

## How it installs

- Files are copied into `~/.claude` (or `$CLAUDE_CONFIG_DIR`), `~/.local/share/workbench` and `~/.local/bin`. A different existing file is first saved as `.bak-<timestamp>`, and so are `settings.json` and `CLAUDE.md` before their first change.
- `settings.json` is **merged**: only additions, never changing a value you already set (a marketplace or plugin you already configured is left as is). Each addition is recorded in a receipt.
- Rules go into `CLAUDE.md` between `<!-- WORKBENCH:<NAME>:START/END -->` markers, so your own text is untouched. If a marker is broken, the installer stops and asks you to fix it rather than guess.
- Running the installer twice changes no file (the plugin commands simply run again).

## Uninstall

```bash
./uninstall.sh                 # everything workbench added (optionals, then core)
./uninstall.sh --with briefing # just one optional
```

The uninstaller reverts exactly what the receipt recorded. A file you edited after installing is kept, with a warning, and a file workbench had replaced is restored. Backups and your vault content stay. Plugins stay installed too; remove them with `claude plugin uninstall <name>`.

## Limits

The rules and skills are instructions, not locks. A model can still ignore them. The real locks are the `deny` / `ask` permissions and your own approval. Mods run inside Claude Code unsandboxed, with your permissions, so read [core/mods/README.md](core/mods/README.md) before enabling them.

## Development

```bash
tests/run.sh    # install / idempotency / uninstall in a throwaway HOME, hooks, mods, leak check
```

## Credits

- [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode): orchestration, HUD, planning and verification workflows.
- [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) (MIT): the guidelines adapted in the rules block.
- [obra/superpowers](https://github.com/obra/superpowers) (MIT): ideas behind `parallel-delegation`.
- [mattpocock-skills](https://github.com/anthropics/claude-plugins-official): TDD, bug diagnosis, grilling, domain modeling.

MIT licensed.
