#!/usr/bin/env bash
# token-keeper: installs the plugin from its own repository, pinned to a tag. Nothing is copied or merged.
# Usage: setup.sh [--dry-run] [--uninstall] [--no-plugins] [--help]
set -euo pipefail

REPO="leomattos7/claude-token-keeper"; REF="v0.1.0"   # pin; raise it after reading the new release
MARKET="claude-token-keeper"; PLUGIN="token-keeper@$MARKET"
STATE="${STATE:-$HOME/.local/share/workbench/state/manual}"; MARK="$STATE/token-keeper-marketplace"   # present = this setup added the marketplace
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
  run claude plugin uninstall "$PLUGIN" --scope user || echo "  could not uninstall $PLUGIN (already gone?)" >&2
  if [ -f "$MARK" ]; then
    run claude plugin marketplace remove "$MARKET" || echo "  could not remove marketplace $MARKET" >&2
    [ "$dry" = 1 ] || rm -f "$MARK"
  else
    echo "  marketplace $MARKET was not added by this setup: kept"
  fi
  exit 0
fi

cat <<'TXT'
  token-keeper rewrites the OAuth login files (.credentials.json) of your Claude config dirs, so it is opt-in.
  It is third-party code that runs unsandboxed: read it first (see optional/token-keeper/README.md).
TXT
if [ "$plugins" = 0 ]; then
  echo "  --no-plugins: not installed. Install it yourself: claude plugin marketplace add $REPO@$REF && claude plugin install $PLUGIN --scope user"
  exit 0
fi
if [ "$dry" = 0 ] && ! command -v claude >/dev/null; then
  echo "  claude not found: install it yourself later: claude plugin marketplace add $REPO@$REF && claude plugin install $PLUGIN --scope user" >&2
  exit 0
fi

if [ "$dry" = 0 ] && claude plugin marketplace list 2>/dev/null | grep -qw "$MARKET"; then
  echo "  marketplace $MARKET already configured: left as is"
elif run claude plugin marketplace add "$REPO@$REF"; then
  [ "$dry" = 1 ] || { mkdir -p "$STATE"; : > "$MARK"; }
else
  echo "  could not add marketplace $REPO@$REF (retry: claude plugin marketplace add $REPO@$REF)" >&2; exit 0
fi
run claude plugin install "$PLUGIN" --scope user || echo "  could not install $PLUGIN (retry: claude plugin install $PLUGIN --scope user)" >&2
