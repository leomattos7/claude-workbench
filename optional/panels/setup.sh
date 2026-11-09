#!/usr/bin/env bash
# panels: nothing to copy. install.sh merges settings.fragment.json (a lean OMC HUD).
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
  The HUD no longer shows context (ctx) or quota (5h, wk). Install the panels that do, yourself:
    claude plugin marketplace add hamzafer/claude-code-mods && claude plugin install context-bar@claude-code-mods --scope user
    claude plugin marketplace add mutlumehmet/claude-plugins && claude plugin install orca-quota@mehmetmutlu --scope user
  They are third-party code that runs unsandboxed: read them first (see optional/panels/README.md).
TXT
