# Vault bootstrap: guided fill from the user's own material

Goal: in a few targeted questions, fill `{{VAULT_PATH}}` with what the user already has (repos, Claude Code
session history, decisions and handoffs, docs and notes) and ingest it. The questions come from what
`discover` finds on this machine, so the user picks from real options instead of typing paths.

Tool: `python3 {{VAULT_PATH}}/tools/collect.py` (run with `--help` for flags). If the file is missing,
the vault predates this feature: tell the user to re-run the vault setup (it only adds missing files), then stop.

Ask with the AskUserQuestion tool: one call per round, at most 4 questions, 2-4 options each, the recommended
option first with "(Recommended)". Without that tool, ask the same questions as one numbered list.

## 1. Discover (writes nothing)

Run `collect.py discover`. If the user keeps code outside `$HOME` (or deeper than 3 levels), add `--root <dir>`;
for extra Claude accounts, `--claude-home <dir>` (repeat the same flags on `sessions` later). Read the output
yourself; do not paste it to the user. Each session project comes with a `history:` path: that is what `sessions` takes.

## 2. Round 1: what and how much

One AskUserQuestion call:
1. "What should go into the vault?" (multiSelect)
   - Repos: READMEs, `docs/`, decision/ADR/handoff folders and recent git history
   - Claude Code sessions: what you asked and what Claude answered, without tool output
   - Decision and handoff folders: the ones discover lists (those inside a chosen repo come with it)
   - Other docs and notes: a folder you name (Markdown, PDF, Office files)
2. "After collecting, how much do I ingest now?"
   - A sample first: 5 sources, then you review the pages (Recommended)
   - Everything now (slower; costs tokens per source)
   - Collect only; ingest later with "ingest raw"

If the user says "quick" or "just do it", skip round 2: take the 3 most recent repos, the sessions of the
3 most active projects for 30 days and every decision folder not inside those repos, then go to step 4.

## 3. Round 2: which ones

One call, only for the categories chosen in round 1 (split into two calls if more than 4 questions):
- Repos (multiSelect): up to 4 options from discover, most recent first, favoring those marked `*`.
  The user types other paths in "Other".
- Session projects (multiSelect): up to 4 projects from discover, by sessions in the last 30 days.
- Session period: 30 days (Recommended) / 7 days / 90 days / all.
- Decision folders (multiSelect): from the discover list, leaving out those inside a chosen repo; or the docs folder, with options built from
  folders that exist (e.g. `~/Documents`, `~/notes`) and "Other" for a path.

A project or folder the user has said holds confidential or client material: confirm it belongs in the vault
before collecting.

## 4. Plan and confirm

Run one collect command per source with `--dry-run`, so each line of the table has its own count:
- `collect.py repo <path>`
- `collect.py sessions <history path> --days <N>` (`--days 0` = all; sessions written in the last hour are
  skipped as probably still running, this one included)
- `collect.py files <dir>` (decision folders and docs folders)

Show a short table (source → files that would be written) and, for "everything now", the number of
sources to ingest. Over 40 sources: propose batches of 10-20 instead. Confirm with one question:
Collect / Adjust / Cancel.

## 5. Collect

Run the same commands without `--dry-run`. They write only into `raw/repos/`, `raw/sessions/` and `raw/docs/`,
one folder per source, never overwrite a file (a changed source lands next to the old copy as `<name>.<date>.<ext>`),
and redact secret-looking strings in text files (not inside PDF or Office files: say so
if any were copied). If the vault is a git repo, commit: `collect: <what>`.

## 6. Ingest

Follow **Ingest** in `{{VAULT_PATH}}/CLAUDE.md` for the pending files (`tools/vault.py pending`), up to the amount
chosen in round 1. Order: decisions and handoffs, then repo docs, then sessions (the noisiest).
Tags: `source/repo`, `source/session` or `source/doc` on the source page.

## 7. Close

Run `tools/vault.py lint`, then report: collected (per source), ingested, pages created and updated,
divergences, what is still pending. Commit if the vault is a git repo. Tell the user they can run the bootstrap
again any time: unchanged sources are skipped, so it only adds what is new or changed.
