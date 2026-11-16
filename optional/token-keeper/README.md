# token-keeper

Keeps the OAuth login of your Claude config dirs fresh while any Claude Code session is open, so an account you
rarely use does not end up logged out. The mod lives in its own repository,
[leomattos7/claude-token-keeper](https://github.com/leomattos7/claude-token-keeper); workbench only installs it.
Nothing is vendored here and workbench does not touch `settings.json` for it.

`--with token-keeper` runs `optional/token-keeper/setup.sh`, which does two things through the `claude` CLI:

```bash
claude plugin marketplace add leomattos7/claude-token-keeper@v0.1.1   # pinned to a tag
claude plugin install token-keeper@claude-token-keeper --scope user
```

- Opt-in by name, not part of `--all`: the mod **rewrites `.credentials.json` files** (the login of each config dir).
  Read its README, in particular "How it works" and "Limits", before enabling it.
- The pin (`REF` in `setup.sh`) moves only when workbench changes it. Read a new release before raising it.
- It pairs with the [`accounts`](../accounts/README.md) optional: the default option `accounts=auto` keeps `~/.claude`
  and every `~/.claude-<name>` dir created by `claude-account add`. For a single account, set the plugin option
  `accounts` to `current` in `/plugin`.
- Run `/token-keeper` in a session to see when each login expires; `/token-keeper now` forces a refresh.
- If a marketplace named `claude-token-keeper` is already configured, it is left as is (and not removed on uninstall).
- `./uninstall.sh --with token-keeper` runs `claude plugin uninstall token-keeper@claude-token-keeper` and removes the
  marketplace only if this setup added it (recorded in workbench's state dir).
- `--dry-run` prints the commands and runs nothing. With `--no-plugins` nothing is installed and the commands to run
  yourself are printed.
