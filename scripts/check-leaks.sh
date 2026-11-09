#!/usr/bin/env bash
# Scan the working tree and git history for terms you never want to publish.
#
# The denylist lives OUTSIDE the repo (a public list of private terms would itself leak them):
#   ${WORKBENCH_DENYLIST:-~/.config/workbench/denylist}
# One case-insensitive extended regex per line; lines starting with # are ignored.
#
# Usage: scripts/check-leaks.sh [--tree-only]
# Exit:  0 = clean, 1 = hits found, 2 = no/invalid denylist or scan error. Commit author names are not scanned (public by design).
set -uo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
list="${WORKBENCH_DENYLIST:-$HOME/.config/workbench/denylist}"
[ -s "$list" ] || { echo "no denylist at $list (see header of this script)" >&2; exit 2; }

patterns="$(mktemp)"; trap 'rm -f "$patterns"' EXIT
tr -d '\r' < "$list" | grep -vE '^\s*(#|$)' > "$patterns" || true
[ -s "$patterns" ] || { echo "denylist $list has no patterns" >&2; exit 2; }
# a malformed pattern must fail loudly, never read as "clean"
printf '' | grep -i -E -f "$patterns" >/dev/null; [ $? -le 1 ] || { echo "invalid regex in $list" >&2; exit 2; }

# LICENSE carries the author's name on purpose.
exclude=(':!LICENSE')
hits=0

cd "$root"
tree="$(git grep -n -I -i -E -f "$patterns" --untracked -- . "${exclude[@]}")"; rc=$?
[ "$rc" -le 1 ] || { echo "git grep failed (exit $rc)" >&2; exit 2; }
if [ -n "$tree" ]; then echo "== working tree"; echo "$tree"; hits=1; fi

if [ "${1:-}" != "--tree-only" ] && git rev-parse -q --verify HEAD >/dev/null; then
  hist="$(git log -p --all --format='commit %h' -- . "${exclude[@]}" | grep -n -i -E -f "$patterns" | grep -v '^[0-9]*:commit ' || true)"
  msgs="$(git log --all --format='%h %s%n%b' | grep -i -E -f "$patterns" || true)"
  if [ -n "$hist$msgs" ]; then echo "== git history"; printf '%s\n%s\n' "$hist" "$msgs" | sed '/^$/d'; hits=1; fi
fi

[ "$hits" = 0 ] && echo "check-leaks: clean"
exit "$hits"
