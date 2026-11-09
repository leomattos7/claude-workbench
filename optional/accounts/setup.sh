#!/usr/bin/env bash
# Install the claude-account CLI into $HOME/.local/bin.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: setup.sh [--dry-run] [--uninstall] [--help]

  --dry-run    print what would be done, write nothing
  --uninstall  remove the claude-account CLI if unmodified (accounts, aliases and dirs are left alone)
EOF
}

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dry=0
uninstall=0
for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    --uninstall) uninstall=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $a" >&2; usage >&2; exit 2 ;;
  esac
done

dst="$HOME/.local/bin/claude-account"
ts="$(date +%Y%m%d%H%M%S)"
say() { if [ "$dry" = 1 ]; then echo "[dry-run] $*"; else echo "$*"; fi; }

if [ "$uninstall" = 1 ]; then
  if [ ! -e "$dst" ]; then
    echo "not installed: $dst"
  elif cmp -s "$here/claude-account" "$dst"; then
    say "remove $dst"
    [ "$dry" = 1 ] || rm -f "$dst"
  else
    echo "kept (modified): $dst"
  fi
  exit 0
fi

if [ -f "$dst" ] && cmp -s "$here/claude-account" "$dst"; then
  echo "unchanged: $dst"
else
  if [ -e "$dst" ]; then say "backup $dst -> $dst.bak-$ts"; [ "$dry" = 1 ] || cp -p "$dst" "$dst.bak-$ts"; fi
  say "install $dst"
  if [ "$dry" != 1 ]; then mkdir -p "$(dirname "$dst")"; cp "$here/claude-account" "$dst"; chmod +x "$dst"; fi
fi

case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "note: $HOME/.local/bin is not in PATH" ;; esac
