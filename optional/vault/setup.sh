#!/usr/bin/env bash
# Install the "vault" second-brain skill and scaffold an empty vault.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: setup.sh [--path <dir>] [--dry-run] [--uninstall] [--help]

  --path <dir>  vault location (default: $HOME/vault)
  --dry-run     print what would be done, write nothing
  --uninstall   remove the installed skill files that are unmodified (use the same --path as
                at install); the vault and modified files are never touched

Env: CLAUDE_HOME = Claude config dir (default: $HOME/.claude)
EOF
}

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
claude_home="${CLAUDE_HOME:-$HOME/.claude}"
vault="$HOME/vault"
dry=0
uninstall=0

while [ $# -gt 0 ]; do
  case "$1" in
    --path) [ $# -ge 2 ] || { echo "--path needs a value" >&2; exit 2; }; vault="$2"; shift ;;
    --dry-run) dry=1 ;;
    --uninstall) uninstall=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

case "$vault" in /*) ;; *) vault="$PWD/$vault" ;; esac
vault="${vault%/}"
skill_dst="$claude_home/skills/vault"
ts="$(date +%Y%m%d%H%M%S)"

say() { if [ "$dry" = 1 ]; then echo "[dry-run] $*"; else echo "$*"; fi; }

# Skill file content with {{VAULT_PATH}} replaced by the vault path.
render() { local c; c="$(<"$1")"; printf '%s' "${c//\{\{VAULT_PATH\}\}/$vault}"; }

# Render a skill file to $dst; back up a different existing file first.
install_skill_file() {
  local src="$1" dst="$2" content
  content="$(render "$src")"
  if [ -f "$dst" ] && [ "$content" = "$(<"$dst")" ]; then
    echo "unchanged: $dst"
    return
  fi
  if [ -e "$dst" ]; then say "backup $dst -> $dst.bak-$ts"; [ "$dry" = 1 ] || cp -p "$dst" "$dst.bak-$ts"; fi
  say "write $dst"
  if [ "$dry" != 1 ]; then mkdir -p "$(dirname "$dst")"; printf '%s\n' "$content" > "$dst"; fi
}

if [ "$uninstall" = 1 ]; then
  while IFS= read -r -d '' f; do
    rel="${f#"$here"/skill/}"
    [ -e "$skill_dst/$rel" ] || continue
    if [ -f "$skill_dst/$rel" ] && [ "$(render "$f")" = "$(<"$skill_dst/$rel")" ]; then
      say "remove $skill_dst/$rel"
      [ "$dry" = 1 ] || rm -f "$skill_dst/$rel"
    else
      echo "kept (modified): $skill_dst/$rel"
    fi
  done < <(find "$here/skill" -type f -print0)
  if [ "$dry" != 1 ] && [ -d "$skill_dst" ]; then rmdir "$skill_dst" 2>/dev/null || true; fi
  echo "vault left untouched: $vault"
  exit 0
fi

while IFS= read -r -d '' f; do
  install_skill_file "$f" "$skill_dst/${f#"$here"/skill/}"
done < <(find "$here/skill" -type f -print0)

# Scaffold: add only the files that are missing; never overwrite.
while IFS= read -r -d '' f; do
  dst="$vault/${f#"$here"/scaffold/}"
  if [ -e "$dst" ]; then continue; fi
  say "create $dst"
  if [ "$dry" != 1 ]; then mkdir -p "$(dirname "$dst")"; cp -p "$f" "$dst"; fi
done < <(find "$here/scaffold" -type f -print0)

echo "vault: $vault (skill: $skill_dst)"
