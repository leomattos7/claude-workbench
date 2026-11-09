---
name: vault
description: Personal second brain (LLM Wiki, Karpathy model) at {{VAULT_PATH}}. Use when the user says "ingest this", "save to my vault", "second brain", "what do I know about X", "what is in my vault", "review the vault", or asks to keep an article/PDF/transcript as knowledge, from any directory. NOT a project's technical wiki and NOT Claude's automatic memory.
---

# Vault

1. Read `{{VAULT_PATH}}/CLAUDE.md`. It is the schema and the only source of the rules.
   If it does not exist, the vault is not set up: tell the user to run the vault setup instead of inventing a layout.
2. Run the requested operation (ingest, query or review) exactly as that file defines it, using absolute vault paths.
   Run the tools from the vault: `python3 {{VAULT_PATH}}/tools/vault.py pending|register|lint`.
3. If the user gives a file outside the vault to ingest, copy it into `{{VAULT_PATH}}/raw/` first (the original stays where it is).
