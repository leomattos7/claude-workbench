# vault: a second brain for Claude Code

An LLM wiki (Karpathy model): you drop sources into `raw/`, Claude turns them into linked Markdown pages
in `wiki/` (sources, entities, concepts, syntheses), and answers questions from those pages with citations.
Plain Markdown; works well with Obsidian but does not require it.

## What setup installs

```bash
bash optional/vault/setup.sh [--path <dir>]   # default: $HOME/vault
```

- `$CLAUDE_HOME/skills/vault/SKILL.md` and `bootstrap.md` (default `~/.claude/skills/vault/`), with `{{VAULT_PATH}}` rendered to your vault path.
  A differing existing file is first copied to `SKILL.md.bak-<timestamp>`.
- The vault scaffold at `<dir>`: `CLAUDE.md` (the rules), `home.md`, `dashboard.base`, `manifest.tsv`,
  `templates/`, `tools/vault.py`, `tools/collect.py`, `tools/web-clipper-raw-web.json`, and the empty folders
  `inbox/ raw/ wiki/{concepts,entities,sources,syntheses}`.
  Existing files are never overwritten, so pointing `--path` at an existing vault only adds what is missing.

Flags: `--dry-run` (print actions, write nothing), `--uninstall`, `--help`. Running it twice changes nothing.

## Usage

Tell Claude "ingest this", "save to my vault", "what do I know about X" or "review the vault"
from any directory. The rules live in `<dir>/CLAUDE.md`; edit them (and `TAG_ROOTS` in `tools/vault.py`) to fit you.
Optional: run `git init` inside the vault so each operation can be committed and undone.

CLI helpers: `python3 <dir>/tools/vault.py pending | register <path>... | lint [--days N]`.

### Fill it from what you already have

Tell Claude "bootstrap my vault" (or "populate my vault"). It runs `tools/collect.py discover` to find your git repos,
Claude Code session history by project and decision/ADR/handoff folders, then asks two short rounds of questions:
what to bring in (repos, sessions, decisions, a docs folder) and how much to ingest now, then which repos, projects,
period and folders. It shows a dry run, collects into `raw/` and ingests.

- `repo`: tracked READMEs, top-level Markdown, `docs/` and decision/ADR/handoff folders, plus the last 200 commits.
- `sessions`: one Markdown file per Claude Code session (your words and Claude's, no tool output, long turns cut;
  subagent transcripts skipped), from `~/.claude*/projects` and `$CLAUDE_CONFIG_DIR`.
- `files`: Markdown, text, PDF, Office, CSV and HTML files from a folder (hidden files skipped).

Everything stays local. Text files are scanned for secret-looking strings (API keys, tokens, private keys,
`password=`, credentials in URLs), which are replaced by `[REDACTED]`; PDF and Office files are copied as is.
The patterns are a safety net, not a guarantee: skim what was collected before adding a git remote.
Each source gets its own folder (`raw/docs/<name>-<hash>/`), so two `decisions` folders never mix. Re-running only
adds what is new; a changed source arrives as `<name>.<date>.<ext>` next to the old copy. Sessions written in the
last hour are skipped as probably still running (`--skip-recent`).
Run it by hand: `python3 <dir>/tools/collect.py --help`.

## Uninstall

```bash
bash optional/vault/setup.sh --uninstall
```

Removes only the skill, and only if you have not edited it (pass the same `--path` as at install; the
top-level `./uninstall.sh` remembers it). An edited skill is kept with a warning. The vault and any
`.bak-*` backups are never deleted.
