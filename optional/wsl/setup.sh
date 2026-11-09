#!/usr/bin/env bash
# Install the WSL integration: notification hook + import-from-windows CLI.
# Usage: setup.sh [--dry-run] [--uninstall] [--help]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
claude_home="${CLAUDE_HOME:-$HOME/.claude}"
hook_dir="$claude_home/hooks/workbench"
bin_dir="$HOME/.local/bin"
dry=0; uninstall=0

for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    --uninstall) uninstall=1 ;;
    -h|--help) sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done

run() { # run <description> <command...>
  local desc="$1"; shift
  if [ "$dry" = 1 ]; then echo "[dry-run] $desc"; else "$@"; fi
}

install_file() { # install_file <src> <dst>
  local src="$1" dst="$2"
  if [ -e "$dst" ] && cmp -s "$src" "$dst"; then
    if [ "$dry" = 1 ]; then echo "[dry-run] unchanged: $dst"; else echo "unchanged: $dst"; fi
    return
  fi
  if [ -e "$dst" ]; then
    run "back up $dst to $dst.bak-<timestamp>" cp -p "$dst" "$dst.bak-$(date +%Y%m%d%H%M%S)"
  fi
  run "mkdir -p $(dirname "$dst")" mkdir -p "$(dirname "$dst")"
  run "install $src -> $dst" install -m 755 "$src" "$dst"
  [ "$dry" = 1 ] || echo "installed: $dst"
}

remove_file() { # remove_file <src> <dst>: only if it is still the file we shipped
  local src="$1" dst="$2"
  if [ ! -e "$dst" ]; then return; fi
  if cmp -s "$src" "$dst"; then
    run "remove $dst" rm -f "$dst"; [ "$dry" = 1 ] || echo "removed: $dst"
  else
    echo "kept (modified since install): $dst"
  fi
}

if [ "$uninstall" = 1 ]; then
  remove_file "$here/notify.sh" "$hook_dir/notify.sh"
  remove_file "$here/import-from-windows" "$bin_dir/import-from-windows"
  [ "$dry" = 1 ] || rmdir "$hook_dir" 2>/dev/null || true
  echo "setup.sh does not edit settings.json: the Notification hook entry stays until ./uninstall.sh --with wsl (repo root) removes it."
  exit 0
fi

install_file "$here/notify.sh" "$hook_dir/notify.sh"
install_file "$here/import-from-windows" "$bin_dir/import-from-windows"

echo "note: setup.sh does not add the Notification hook to settings.json; ./install.sh --with wsl (repo root) does."
if ! grep -qi microsoft /proc/version 2>/dev/null; then
  echo "note: not running on WSL. The toast falls back to notify-send (if installed);"
  echo "      import-from-windows only works inside WSL."
fi
