# wsl

Windows integration for WSL users.

- **Notification toast**: when a Claude Code session asks for permission or input, a Windows toast
  appears titled `Claude (<account>) · <folder>`. The account comes from `CLAUDE_CONFIG_DIR`
  (`~/.claude` is `default`, `~/.claude-work` is `work`). On plain Linux it falls back to
  `notify-send`; with neither available it does nothing. The hook never blocks and always exits 0.
- **`import-from-windows`**: copies files from your Windows `Downloads` folder (or any Windows or WSL
  path) into a project folder, verifies the sha256, never overwrites a different file, and refuses
  files whose names look like secrets (`.env*`, `*.pem`, `*.key`, `*.ppk`, `*.kdbx`, `.npmrc`,
  `credentials*`, `id_rsa*`, `ssh/` folders, ...; case-insensitive). It is a file-name filter, not
  a content scan: a secret in a file with an ordinary name is copied.

## Installed

| What | Where |
| --- | --- |
| `notify.sh` | `$CLAUDE_HOME/hooks/workbench/notify.sh` (default `~/.claude/...`) |
| `import-from-windows` | `~/.local/bin/import-from-windows` |

The repo's `./install.sh --with wsl` merges `settings.fragment.json` (a `Notification` hook, timeout 5s)
into `settings.json`; running `setup.sh` alone only copies the two files above.
Existing different files are copied to `<file>.bak-<timestamp>` first.

## Usage

```bash
import-from-windows --recent 5                 # newest files in Windows Downloads
import-from-windows report.pdf                 # bare name: looked up in Downloads, copied to ./incoming
import-from-windows -d docs/in 'C:\Users\me\Desktop\notes.md'
```

The Windows profile is detected with `cmd.exe`; set `WIN_DOWNLOADS=/mnt/c/Users/<you>/Downloads`
to override.

## Setup / uninstall

```bash
bash setup.sh --dry-run      # show what would happen, write nothing
bash setup.sh
bash setup.sh --uninstall    # removes only the unchanged files it installed; backups are kept
```

`setup.sh` (install or `--uninstall`) never edits `settings.json`. The `Notification` hook is added by
`./install.sh --with wsl` and removed by `./uninstall.sh --with wsl`, both run from the repo root.
