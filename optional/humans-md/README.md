# humans-md

Installs the official [HUMANS.md](https://github.com/cmdai-hq/HUMANS.md) plugin for Claude Code. A HUMANS.md is a
small file in `~/.humans/HUMANS.md` that tells your agents how to write to you, when to ask you to decide and when to
interrupt you. The plugin lives in its own repository,
[cmdai-hq/humans-md-plugins](https://github.com/cmdai-hq/humans-md-plugins) (Apache-2.0); workbench only installs it.
Nothing is vendored here and workbench does not touch `settings.json` for it.

`--with humans-md` runs `optional/humans-md/setup.sh`, which does two things through the `claude` CLI:

```bash
claude plugin marketplace add cmdai-hq/humans-md-plugins@v0.3.2   # pinned to a tag
claude plugin install humans-md@humans-md --scope user
```

- Opt-in by name, not part of `--all`: it is third-party code that runs unsandboxed in every session start, and it
  reads a file that can hold personal information. Read the plugin's `core/SECURITY.md` first.
- Needs Node 22.18 or later. The plugin reads `~/.humans/HUMANS.md` and nothing else.
- **Your profile is yours to write.** The setup never creates or edits `~/.humans`. Without the file the plugin loads
  nothing. The upstream README explains how to write one; the format keeps preferences as form only, never a
  permission, so repo rules, workbench rules and tool approvals still win.
- Claude Code only. The upstream project also ships plugins for Codex, Cursor and others; install those from their
  own instructions if you want them, one plugin per client so the profile does not load twice.
- The pin (`REF` in `setup.sh`) moves only when workbench changes it. Read a new release before raising it.
- If a marketplace named `humans-md` is already configured, it is left as is (and not removed on uninstall).
- If the plugin is already installed, it is left as is too. `./uninstall.sh --with humans-md` runs
  `claude plugin uninstall humans-md@humans-md` only if this setup installed it, and removes the marketplace only if
  this setup added it (both recorded in workbench's state dir). `~/.humans` is never touched.
- `--dry-run` prints the commands and runs nothing. With `--no-plugins` nothing is installed and the commands to run
  yourself are printed.
