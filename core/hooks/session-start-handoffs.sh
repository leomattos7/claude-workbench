#!/usr/bin/env bash
# SessionStart hook: list the 3 most recent handoffs of the current project.
# Looks in $CLAUDE_PROJECT_DIR/docs/handoffs (falls back to the cwd). Silent when there are none.
# Lists only; never injects a handoff, because it may belong to another session running in parallel.
dir="${CLAUDE_PROJECT_DIR:-$PWD}/docs/handoffs"
[ -d "$dir" ] || exit 0
mapfile -t files < <(ls -t "$dir"/[0-9]*.md 2>/dev/null | head -3)
[ "${#files[@]}" -gt 0 ] || exit 0
echo "[HANDOFFS] 3 most recent in $dir (may belong to ANOTHER session running in parallel)."
echo "Do not resume one on your own: if the user asks to resume without saying which, ask which."
echo "When resuming: read the file, re-check git status, branch and cwd before editing (see the handoff skill)."
for f in "${files[@]}"; do
  title="$(sed -n '1s/^# *//p' "$f")"
  echo "- $f · ${title:-untitled} · $(date -r "$f" '+%F %H:%M')"
done
exit 0
