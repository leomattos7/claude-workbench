---
name: vault
description: Personal second brain (LLM Wiki, Karpathy model) at {{VAULT_PATH}}. Use when the user says "ingest this", "save to my vault", "second brain", "what do I know about X", "what is in my vault", "review the vault", "set up / bootstrap / populate / fill my vault" (from repos, Claude Code sessions, decisions or docs), or asks to keep an article/PDF/transcript as knowledge, from any directory. NOT a project's technical wiki and NOT Claude's automatic memory.
---

# Vault

1. Read `{{VAULT_PATH}}/CLAUDE.md`. It is the schema and the only source of the rules.
   If it does not exist, the vault is not set up: tell the user to run the vault setup instead of inventing a layout.
2. Run the requested operation (ingest, query or review) exactly as that file defines it, using absolute vault paths.
   Run the tools from the vault: `python3 {{VAULT_PATH}}/tools/vault.py pending|register|lint`.
3. If the user gives a file outside the vault to ingest, copy it into `{{VAULT_PATH}}/raw/` first (the original stays where it is).
4. To fill the vault from the user's own material (repos, Claude Code sessions, decisions, docs), for example right after setup
   or when the vault is empty, follow `bootstrap.md` in this skill's folder: a short guided interview, then collect and ingest.

## Writing wiki pages shared by several agents

Read the vault rules and prepare the Markdown as usual. Use `python3 <this skill directory>/vault-write.py "{{VAULT_PATH}}" <batch.json>` for wiki writes. Compute the SHA-256 of every existing file as you read it, and keep that version while drafting. The batch is a JSON object with `edits`, an array of objects with `path` (relative to the vault), `expected_sha256` (`null` for a new file), and `text` (the complete updated Markdown). Include `wiki/index.md` and `wiki/log.md` updates in the same batch. For ingest, add a `register` array of relative `raw/` file paths and the tool will run the existing `tools/vault.py register` under the same lock.

On a version conflict, re-read the affected pages, combine both sets of changes, and submit a new batch. The lock file is local runtime state. Exclude `.workbench-vault-lock.sqlite3` from any vault commit. Keep raw files immutable, and follow the vault rules for placing new sources in `raw/`.
