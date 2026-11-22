#!/usr/bin/env bash
# humans-md: installs the official HUMANS.md plugin from its own repository, pinned to a tag. Nothing is copied or merged.
# Usage: setup.sh [--dry-run] [--uninstall] [--no-plugins] [--help]
set -euo pipefail

REPO="cmdai-hq/humans-md-plugins"; REF="v0.3.2"   # pin; raise it after reading the new release
MARKET="humans-md"; PLUGIN="humans-md@$MARKET"
STATE="${STATE:-$HOME/.local/share/workbench/state/manual}"
MARK="$STATE/humans-md-marketplace"; MARK_PLUGIN="$STATE/humans-md-plugin"   # present = this setup added the marketplace / installed the plugin
dry=0; uninstall=0; plugins=1
for a in "$@"; do
  case "$a" in
    --dry-run) dry=1 ;;
    --uninstall) uninstall=1 ;;
    --no-plugins) plugins=0 ;;
    -h|--help) sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done
say() { if [ "$dry" = 1 ]; then echo "  [dry-run] $*"; else echo "  $*"; fi; }
run() { say "$*"; [ "$dry" = 1 ] || "$@"; }

if [ "$uninstall" = 1 ]; then
  command -v claude >/dev/null || { echo "  claude not found: remove it yourself with: claude plugin uninstall $PLUGIN" >&2; exit 0; }
  if [ -f "$MARK_PLUGIN" ]; then
    run claude plugin uninstall "$PLUGIN" --scope user || echo "  could not uninstall $PLUGIN (already gone?)" >&2
    [ "$dry" = 1 ] || rm -f "$MARK_PLUGIN"
  else
    echo "  plugin $PLUGIN was not installed by this setup: kept"
  fi
  if [ -f "$MARK" ]; then
    run claude plugin marketplace remove "$MARKET" || echo "  could not remove marketplace $MARKET" >&2
    [ "$dry" = 1 ] || rm -f "$MARK"
  else
    echo "  marketplace $MARKET was not added by this setup: kept"
  fi
  echo "  your profile (~/.humans) is never touched by this setup"
  exit 0
fi

cat <<'TXT'
  humans-md installs a third-party plugin whose SessionStart hook reads ~/.humans/HUMANS.md and gives your agent
  the approved preferences in it. The plugin runs unsandboxed and needs Node 22.18 or later: read it first
  (see optional/humans-md/README.md). This setup never creates or edits your profile.
TXT
if [ "$plugins" = 0 ]; then
  echo "  --no-plugins: not installed. Install it yourself: claude plugin marketplace add $REPO@$REF && claude plugin install $PLUGIN --scope user"
  exit 0
fi
if [ "$dry" = 0 ] && ! command -v claude >/dev/null; then
  echo "  claude not found: install it yourself later: claude plugin marketplace add $REPO@$REF && claude plugin install $PLUGIN --scope user" >&2
  exit 0
fi
command -v node >/dev/null || echo "  warning: node not found; the plugin needs Node 22.18 or later" >&2

if [ "$dry" = 0 ] && claude plugin marketplace list 2>/dev/null | grep -qw "$MARKET"; then
  echo "  marketplace $MARKET already configured: left as is"
elif run claude plugin marketplace add "$REPO@$REF"; then
  [ "$dry" = 1 ] || { mkdir -p "$STATE"; : > "$MARK"; }
else
  echo "  could not add marketplace $REPO@$REF (retry: claude plugin marketplace add $REPO@$REF)" >&2; exit 0
fi
if [ "$dry" = 0 ] && claude plugin list 2>/dev/null | grep -qF "$PLUGIN"; then
  echo "  plugin $PLUGIN already installed: left as is"
elif run claude plugin install "$PLUGIN" --scope user; then
  [ "$dry" = 1 ] || { mkdir -p "$STATE"; : > "$MARK_PLUGIN"; }
else
  echo "  could not install $PLUGIN (retry: claude plugin install $PLUGIN --scope user)" >&2
fi
if [ "$dry" = 0 ] && [ ! -f "$HOME/.humans/HUMANS.md" ]; then
  echo "  no ~/.humans/HUMANS.md yet: the plugin loads nothing until you write your profile (see the README)"
fi
