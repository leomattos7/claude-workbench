# token-keeper

Keeps the OAuth login of your Claude config dirs fresh while any Claude Code session is open, so an account you
rarely use does not end up logged out. The mod lives in its own repository,
[leomattos7/claude-token-keeper](https://github.com/leomattos7/claude-token-keeper); workbench only adds and
enables it. Nothing is vendored here.

`--with token-keeper` merges two entries into `settings.json` and installs the plugin the same way the core
plugins are installed:

- `extraKnownMarketplaces.claude-token-keeper` (the repository above), and
- `enabledPlugins["token-keeper@claude-token-keeper"]`.

- Opt-in by name, not part of `--all`: the mod **rewrites `.credentials.json` files** (the login of each config dir).
  Read its README, in particular "How it works" and "Limits", before enabling it.
- It pairs with the [`accounts`](../accounts/README.md) optional: the default option `accounts=auto` keeps `~/.claude`
  and every `~/.claude-<name>` dir created by `claude-account add`. For a single account, set the plugin option
  `accounts` to `current`.
- Run `/token-keeper` in a session to see when each login expires; `/token-keeper now` forces a refresh.
- It never overrides an entry you already set (a marketplace or plugin you configured is left as is).
- `./uninstall.sh --with token-keeper` removes exactly what was added to `settings.json`. As with the other plugins,
  the plugin itself stays installed: `claude plugin uninstall token-keeper`.
- With `--no-plugins` nothing is merged or installed (the fragment is only plugin entries); the installer prints the
  command to run yourself.
