# accounts: several Claude accounts, one shared config

Run a second (or third) Claude account side by side, each with its own login, while sharing
your skills, plugins, hooks, settings and `CLAUDE.md`. Install a skill or plugin once, every account gets it.

How it works: each account is a config dir `~/.claude-<name>` started through an alias

```bash
alias claude-<name>='CLAUDE_CONFIG_DIR=$HOME/.claude-<name> claude'
```

The dir keeps its own credentials and sessions. `CLAUDE.md`, `settings.json`, `skills`, `plugins`, `hooks`
and `plans` are symlinks to the main config (`$CLAUDE_HOME`, default `~/.claude`).

## What setup installs

```bash
bash optional/accounts/setup.sh    # flags: --dry-run, --uninstall, --help
```

Installs the `claude-account` CLI to `~/.local/bin/claude-account` (a differing existing file is backed up
as `claude-account.bak-<timestamp>`). Creates no accounts by itself.

## Usage

```bash
claude-account add work                  # ~/.claude-work + alias claude-work
claude-account add work --share-history  # also link projects/ (transcripts + auto-memory)
claude-account list
claude-account remove work               # --force to also delete a dir that holds credentials
```

Every subcommand accepts `--dry-run`. The alias is written to `~/.bashrc` (and `~/.zshrc` if it exists)
between `# >>> workbench account <name> >>>` and `# <<< workbench account <name> <<<` markers.
Open a new shell, run `claude-<name>` and log in. `<name>` must match `^[a-z0-9-]+$`.

Safety: a path in the account dir that exists and is not the expected symlink is renamed to `<path>.bak-<timestamp>`
before linking, never overwritten. `remove` deletes only the symlinks it created and the alias block, and
refuses to delete a dir containing credentials unless `--force` is given. `.bashrc`/`.zshrc` are backed up before edits.
The `add` command is idempotent; shared items missing from `$CLAUDE_HOME` are skipped (re-run `add` once they exist).

## Caveats

- Sessions of one account do not appear in the other account's `--resume` list or `ListAgents`.
  `--share-history` shares the transcript files, but `claude --resume <id>` must still run in the folder
  where the session was created.
- Login lives in the account dir (`.credentials.json`/`.claude.json`); on systems that use a keychain
  it may be stored there instead, so `list` can show `LOGIN no` for a logged-in account.

## Uninstall

```bash
claude-account remove <name>       # for each account you want gone
bash optional/accounts/setup.sh --uninstall
```

The uninstall removes only the CLI, and only if you have not edited it (an edited copy is kept with a
warning). Accounts and aliases stay until you `remove` them.
