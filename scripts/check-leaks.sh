#!/usr/bin/env bash
# Scan the working tree and git history for terms you never want to publish.
#
# The denylist lives OUTSIDE the repo (a public list of private terms would itself leak them):
#   ${WORKBENCH_DENYLIST:-~/.config/workbench/denylist}
# One case-insensitive extended regex per line; lines starting with # are ignored.
# Optional allowlist (same format, also outside the repo): text matching it is removed from a hit
# line before re-checking, e.g. a public profile URL that contains a private term:
#   ${WORKBENCH_ALLOWLIST:-~/.config/workbench/allowlist}
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

allow="${WORKBENCH_ALLOWLIST:-$HOME/.config/workbench/allowlist}"
# drop hit lines that only match because of allowlisted text
filter() {
  [ -s "$allow" ] || { cat; return; }
  python3 -I -c '
import re, sys
def load(p):
    return [re.compile(l.strip(), re.I) for l in open(p, encoding="utf-8") if l.strip() and not l.lstrip().startswith("#")]
deny, allow = load(sys.argv[1]), load(sys.argv[2])
for line in sys.stdin:
    rest = line
    for a in allow:
        rest = a.sub("", rest)
    if any(d.search(rest) for d in deny):
        sys.stdout.write(line)' "$patterns" "$allow"
}

# LICENSE carries the author's name on purpose.
exclude=(':!LICENSE')
hits=0

cd "$root"
tree="$(git grep -n -I -i -E -f "$patterns" --untracked -- . "${exclude[@]}")"; rc=$?
[ "$rc" -le 1 ] || { echo "git grep failed (exit $rc)" >&2; exit 2; }
tree="$(printf '%s' "$tree" | filter)"
if [ -n "$tree" ]; then echo "== working tree"; echo "$tree"; hits=1; fi

if [ "${1:-}" != "--tree-only" ] && git rev-parse -q --verify HEAD >/dev/null; then
  hist="$(git log -p --all --format='commit %h' -- . "${exclude[@]}" | grep -n -i -E -f "$patterns" | grep -v '^[0-9]*:commit ' | filter || true)"
  msgs="$(git log --all --format='%h %s%n%b' | grep -i -E -f "$patterns" | filter || true)"
  if [ -n "$hist$msgs" ]; then echo "== git history"; printf '%s\n%s\n' "$hist" "$msgs" | sed '/^$/d'; hits=1; fi
fi

[ "$hits" = 0 ] && echo "check-leaks: clean"
exit "$hits"
