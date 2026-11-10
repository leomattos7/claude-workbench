# Vault — second brain (LLM Wiki, Karpathy model)

This file is the vault **schema**: the single source of the ingest/query/lint rules.
The `vault` skill only points here.

The layout follows the Obsidian "Karpathy LLM Wiki" plugin, so the plugin and Claude Code can
operate on the same vault without conflict. Obsidian is optional: everything is plain Markdown.

## Structure

| Path | Owner | Rule |
|---|---|---|
| `raw/` | user | Sources (md, PDF, DOCX, PPTX, XLSX, transcripts, Web Clipper). **Immutable**: never edit, move or delete. |
| `wiki/sources/` | Claude | One page per ingested source. |
| `wiki/entities/` | Claude | People, organizations, products, events, places. |
| `wiki/concepts/` | Claude | Theories, methods, terms, frameworks. |
| `wiki/syntheses/` | Claude | Analyses that cross sources; query answers worth keeping. |
| `wiki/index.md` | Claude | Catalog: one line per page (`- [[slug]] — one-line summary`), grouped by folder. |
| `wiki/log.md` | Claude | Append-only record of every operation (narrative). |
| `manifest.tsv` | Claude | What was already ingested: `sha256 · path · date`, one `raw/` file per line. Written only by `tools/vault.py register`. |
| `tools/vault.py` | Claude | `pending` (what is left to ingest), `register`, `lint`. Standard library only. |
| `raw/repos/`, `raw/sessions/`, `raw/docs/` | Claude | Snapshots written by `tools/collect.py` from repos, Claude Code sessions and doc folders (secret-looking strings redacted). One folder per source (`<name>-<hash>`). Same rule as `raw/`; a changed source arrives as a new `<name>.<date>` file. |
| `tools/collect.py` | Claude | `discover` (candidates, writes nothing), `repo`, `sessions`, `files`. Used by the guided bootstrap (skill `vault`, `bootstrap.md`). |
| `raw/web/` | user | Web Clipper destination (template `tools/web-clipper-raw-web.json`). Same rule as `raw/`. |
| `inbox/` | user | Quick notes (default folder for new notes, template `templates/note.md`). Ingesting = moving to `raw/notes/` untouched, then ingesting from there. |
| `home.md`, `dashboard.base` | Claude | Landing page and Bases views (recent, to review, by type, sources, aging). Not sources. |
| `templates/` | user | Templates. Not sources. |

Notes the user wrote by hand outside `raw/` and `wiki/` (except the structural files above) are also valid sources and are never modified.

## Tag taxonomy

Every tag is `root/subtopic`, and the root comes from this list (`lint` enforces it). A new subtopic is fine;
a new root needs the user's OK (then update this table and `TAG_ROOTS` in `tools/vault.py`). Reuse existing subtopics before creating new ones.
Edit this starter list to fit your life; keep the two in sync.

| Root | Use | Current subtopics |
|---|---|---|
| `topic` | Subject-matter content | _(grow as needed)_ |
| `work` | Your job and projects | _(grow as needed)_ |
| `method` | How to work | _(grow as needed)_ |
| `tech` | Tools and infrastructure | _(grow as needed)_ |
| `personal` | Personal life and projects | _(grow as needed)_ |
| `source` | Origin of a `source` page | `web`, `note`, `book`, `video`, `paper`, `repo`, `session`, `doc` |

## Page format

File `kebab-case.md`, in the vault's working language (technical terms may stay in the original). Links only as `[[slug]]`.

```yaml
---
type: source | entity | concept | synthesis
aliases: [Full Name, ACRONYM, other-language name]   # required, >=1 (dedup across languages)
tags: [root/subtopic]                                 # see "Tag taxonomy"
sources: ["[[source-slug]]"]                          # where each claim comes from
raw: raw/file.pdf                                     # only for type: source
updated: YYYY-MM-DD
reviewed: false                                       # true = user reviewed it -> do not rewrite
---
```

Body: 1-3 sentence summary at the top, then sections. A `source` page ends with `## Source excerpts`
(short literal quotes that support the generated pages).

## Operations

### Ingest ("ingest this", "save to my vault", "ingest raw")
0. "ingest the inbox": move each note `inbox/<note>.md` to `raw/notes/<YYYY-MM-DD>-<note>.md` (content intact; use `git mv` if the vault is a git repo), then continue from step 1.
1. Target = the file named by the user, or the output of `python3 tools/vault.py pending` (new = not ingested; CHANGED = someone touched `raw/`: warn the user, do not ingest).
2. Read the whole source (PDF/DOCX/PPTX/XLSX: use the matching skills; public video: `yt-dlp` for subtitles).
3. Read `wiki/index.md` and the related pages **before** writing. Look for duplicates by title **and** aliases.
4. Write `wiki/sources/<slug>.md`. For a `raw/sessions/` transcript keep it short: decisions, problems and their fixes,
   open questions, people and tools involved; skip chit-chat. A collected `<name>.<date>.<ext>` file is a newer
   version of `<name>.<ext>`: update that source page (and point `raw:` to the new file) instead of creating another.
5. Update/create the entity/concept pages touched (typically 5-15). Updating > creating a duplicate.
   A page with `reviewed: true`: do not rewrite it, only append to `## Pending updates` for the user to approve.
6. Contradiction with what already exists: do not overwrite; record it under `## Divergences`, citing both sources.
7. Update `wiki/index.md`, append to `wiki/log.md`, and run `python3 tools/vault.py register <ingested files>`.
8. Report: created, updated, divergences.

### Query (any question about what was saved)
1. `wiki/index.md` -> `grep -ril` in `wiki/` (titles, aliases, body) -> read pages -> follow `[[links]]` 1-2 hops.
2. Answer citing `[[pages]]`. State explicitly what is **not** in the wiki; outside knowledge only when marked as such.
3. A useful synthesis -> offer to save it in `wiki/syntheses/`.

### Review ("lint", "review the vault")
1. Run `python3 tools/vault.py lint` (frontmatter, tags outside the taxonomy, dead links, orphans, pages missing from the index,
   duplicate aliases, pages without `sources`, pages > 400 lines, `updated` older than 90 days, pending or changed `raw/` files).
2. Add what the script cannot catch: contradictions, unsourced claims in the body, concepts mentioned on 3+ pages without their own page.
3. Report, and fix only with the user's OK.

## Log

```
## YYYY-MM-DD — ingest | query | lint | fix
- raw: raw/file.pdf
- created: [[a]], [[b]]
- updated: [[c]]
- notes: ...
```

## Limits

- Private or confidential material may live here, but never send it through third-party services
  (online converters, web readers, search APIs) unless the user explicitly allows it.
- Every claim points to a source; Claude's own inference is marked _(inference)_.
- Do not delete pages without an explicit request.
- Recommended: keep the vault a local git repo (`git init`, no remote). At the end of each operation that changes files:
  `git add -A && git commit -m "<op>: <summary>"`. Undo = `git revert`/`git restore`, never by deleting by hand.
  Add a remote only if private and only with the user's OK.
- Do not confuse with a project's technical wiki or Claude's automatic memory (preferences and working context).
  The vault is for **content knowledge**.
