#!/usr/bin/env bash
# Install the morning briefing: CLI, collector, prompt, and a default config (only if none exists).
# Usage: setup.sh [--dry-run] [--uninstall] [--help]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
share="$HOME/.local/share/workbench/briefing"
bin="$HOME/.local/bin/workbench-briefing"
conf="$HOME/.config/workbench/briefing.conf"
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

install_file() { # install_file <src> <dst> <mode>
  local src="$1" dst="$2" mode="$3"
  if [ -e "$dst" ] && cmp -s "$src" "$dst"; then
    if [ "$dry" = 1 ]; then echo "[dry-run] unchanged: $dst"; else echo "unchanged: $dst"; fi
    return
  fi
  if [ -e "$dst" ]; then
    run "back up $dst to $dst.bak-<timestamp>" cp -p "$dst" "$dst.bak-$(date +%Y%m%d%H%M%S)"
  fi
  run "mkdir -p $(dirname "$dst")" mkdir -p "$(dirname "$dst")"
  run "install $src -> $dst" install -m "$mode" "$src" "$dst"
  [ "$dry" = 1 ] || echo "installed: $dst"
}

remove_file() { # remove_file <src> <dst>: only if it is still the file we shipped
  local src="$1" dst="$2"
  [ -e "$dst" ] || return 0
  if cmp -s "$src" "$dst"; then
    run "remove $dst" rm -f "$dst"; [ "$dry" = 1 ] || echo "removed: $dst"
  else
    echo "kept (modified since install): $dst"
  fi
}

if [ "$uninstall" = 1 ]; then
  remove_file "$here/workbench-briefing" "$bin"
  remove_file "$here/collect.py" "$share/collect.py"
  remove_file "$here/prompt.md" "$share/prompt.md"
  [ "$dry" = 1 ] || rmdir "$share" 2>/dev/null || true
  echo "Kept: $conf and your briefings. Run 'workbench-briefing --uninstall-cron' first if you enabled cron."
  exit 0
fi

install_file "$here/collect.py" "$share/collect.py" 644
install_file "$here/prompt.md" "$share/prompt.md" 644
install_file "$here/workbench-briefing" "$bin" 755

if [ -e "$conf" ]; then
  if [ "$dry" = 1 ]; then echo "[dry-run] config exists, left alone: $conf"; else echo "config exists, left alone: $conf"; fi
else
  run "mkdir -p $(dirname "$conf")" mkdir -p "$(dirname "$conf")"
  run "write default config $conf" cp "$here/briefing.conf.example" "$conf"
  [ "$dry" = 1 ] || echo "wrote default config: $conf (edit REPOS)"
fi

echo "Next: edit $conf, then 'workbench-briefing --dry-run'. Cron is opt-in: 'workbench-briefing --install-cron'."
