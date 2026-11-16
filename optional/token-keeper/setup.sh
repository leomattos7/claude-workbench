#!/usr/bin/env bash
# token-keeper: nothing to copy. install.sh merges settings.fragment.json and adds the plugin like the others.
# Usage: setup.sh [--dry-run] [--uninstall] [--help]
set -euo pipefail
for a in "$@"; do
  case "$a" in
    --dry-run|--uninstall) ;;
    -h|--help) sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done
case " $* " in *" --uninstall "*) exit 0 ;; esac
cat <<'TXT'
  token-keeper rewrites the OAuth login files (.credentials.json) of your Claude config dirs, so it is opt-in.
  It is third-party code that runs unsandboxed: read it first (see optional/token-keeper/README.md).
  With --no-plugins, install it yourself: /plugin install token-keeper --marketplace leomattos7/claude-token-keeper
TXT
