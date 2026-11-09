# vault: a second brain for Claude Code

An LLM wiki (Karpathy model): you drop sources into `raw/`, Claude turns them into linked Markdown pages
in `wiki/` (sources, entities, concepts, syntheses), and answers questions from those pages with citations.
Plain Markdown; works well with Obsidian but does not require it.

## What setup installs

```bash
bash optional/vault/setup.sh [--path <dir>]   # default: $HOME/vault
```

- `$CLAUDE_HOME/skills/vault/SKILL.md` (default `~/.claude/skills/vault/`), with `{{VAULT_PATH}}` rendered to your vault path.
  A differing existing file is first copied to `SKILL.md.bak-<timestamp>`.
- The vault scaffold at `<dir>`: `CLAUDE.md` (the rules), `home.md`, `dashboard.base`, `manifest.tsv`,
  `templates/`, `tools/vault.py`, `tools/web-clipper-raw-web.json`, and the empty folders
  `inbox/ raw/ wiki/{concepts,entities,sources,syntheses}`.
  Existing files are never overwritten, so pointing `--path` at an existing vault only adds what is missing.

Flags: `--dry-run` (print actions, write nothing), `--uninstall`, `--help`. Running it twice changes nothing.

## Usage

Tell Claude "ingest this", "save to my vault", "what do I know about X" or "review the vault"
from any directory. The rules live in `<dir>/CLAUDE.md`; edit them (and `TAG_ROOTS` in `tools/vault.py`) to fit you.
Optional: run `git init` inside the vault so each operation can be committed and undone.

CLI helpers: `python3 <dir>/tools/vault.py pending | register <path>... | lint [--days N]`.

## Uninstall

```bash
bash optional/vault/setup.sh --uninstall
```

Removes only the skill, and only if you have not edited it (pass the same `--path` as at install; the
top-level `./uninstall.sh` remembers it). An edited skill is kept with a warning. The vault and any
`.bak-*` backups are never deleted.
