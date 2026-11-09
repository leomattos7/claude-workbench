#!/usr/bin/env bash
# Install workbench into your Claude Code config (Linux and WSL; macOS untested).
#
# Usage:
#   ./install.sh                          core only
#   ./install.sh --with vault,wsl         core + chosen optionals (vault, accounts, wsl, briefing, panels)
#   ./install.sh --all                    core + every optional except panels (opt-in by name)
#   ./install.sh --dry-run [...]          show what would happen, change nothing
#   ./install.sh --no-plugins [...]       skip the marketplace plugins (and do not enable them)
#   ./install.sh --vault-path DIR [...]   where the vault lives (default ~/vault)
#   ./install.sh --uninstall [--with ...] remove what workbench installed (without --with: everything)
#
# Targets: $CLAUDE_CONFIG_DIR (default ~/.claude), ~/.local/share/workbench, ~/.local/bin.
# Never copies credentials and never logs in anywhere. Before a file is rewritten, a real copy is
# kept as <file>.bak-<timestamp>. Settings are merged (additions only) and recorded in a receipt,
# so --uninstall removes exactly what was added; installed files are removed only if unmodified,
# and files they replaced are restored.
set -euo pipefail

WB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"; CLAUDE_HOME="${CLAUDE_HOME%/}"
SHARE="$HOME/.local/share/workbench"
STATE="$SHARE/state/$(printf '%s' "$CLAUDE_HOME" | sha1sum | cut -c1-12)"   # one per config dir
RECEIPT="$STATE/receipt.json"; FILES="$STATE/files.tsv"
WB_STAMP="$(date +%Y%m%d%H%M%S)"
ALL_OPTIONALS="vault accounts wsl briefing"   # what --all installs
KNOWN_OPTIONALS="$ALL_OPTIONALS panels"       # panels removes HUD items, so it is never implied by --all
OPTIONALS=""; DRY=0; PLUGINS=1; UNINSTALL=0; VAULT_PATH="$HOME/vault"
MIN_MODS_VERSION="2.1.287"
export CLAUDE_HOME WB_STAMP

need() { [ -n "${2:-}" ] || { echo "$1 needs a value (see --help)" >&2; exit 1; }; }
while [ $# -gt 0 ]; do
  case "$1" in
    --with) need "$1" "${2:-}"; OPTIONALS="${2//,/ }"; shift ;;
    --with=*) OPTIONALS="${1#--with=}"; OPTIONALS="${OPTIONALS//,/ }" ;;
    --all) OPTIONALS="$ALL_OPTIONALS" ;;
    --dry-run) DRY=1 ;;
    --no-plugins) PLUGINS=0 ;;
    --vault-path) need "$1" "${2:-}"; VAULT_PATH="$2"; shift ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 1 ;;
  esac
  shift
done
for o in $OPTIONALS; do
  case " $KNOWN_OPTIONALS " in *" $o "*) ;; *) echo "unknown optional: $o (choose from: $KNOWN_OPTIONALS)" >&2; exit 1 ;; esac
done
case "$VAULT_PATH" in /*) ;; *) VAULT_PATH="$PWD/$VAULT_PATH" ;; esac
VAULT_PATH="${VAULT_PATH%/}"

ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$*" >&2; exit 1; }
dry()  { [ "$DRY" = 1 ] && echo "  [dry-run] $*"; [ "$DRY" = 1 ]; }
wbpy() { python3 -I "$WB/scripts/wb.py" "$@"; }
sha()  { sha256sum "$1" | cut -d' ' -f1; }
upper() { printf '%s' "$1" | tr '[:lower:]' '[:upper:]'; }
version_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

# render <src> <dst>: fill placeholders; point $HOME/.claude/ at CLAUDE_HOME when it differs
render() {
  local claude_ref="\$HOME/.claude/"
  [ "$CLAUDE_HOME" = "$HOME/.claude" ] || claude_ref="$CLAUDE_HOME/"
  MODS_DIR="$SHARE/mods" VAULT_PATH="$VAULT_PATH" CLAUDE_REF="$claude_ref" python3 -I -c '
import os, sys
t = open(sys.argv[1], encoding="utf-8").read()
for k in ("MODS_DIR", "VAULT_PATH"):
    t = t.replace("{{" + k + "}}", os.environ[k])
t = t.replace("$HOME/.claude/", os.environ["CLAUDE_REF"])
open(sys.argv[2], "w", encoding="utf-8").write(t)' "$1" "$2"
}

# files.tsv: component <TAB> path <TAB> sha256 of what we installed <TAB> backup we made (or -)
record() { # record <component> <path> <sha> <backup|->  (keeps the first backup ever made; stable order)
  local bak="$4" line
  if [ -f "$FILES" ] && [ "$bak" = "-" ]; then
    bak="$(awk -F'\t' -v c="$1" -v p="$2" '$1==c && $2==p {print $4}' "$FILES")"; bak="${bak:--}"
  fi
  line="$(printf '%s\t%s\t%s\t%s' "$1" "$2" "$3" "$bak")"
  if [ -f "$FILES" ] && grep -qxF "$line" "$FILES"; then return 0; fi
  if [ -f "$FILES" ] && awk -F'\t' -v c="$1" -v p="$2" '$1==c && $2==p {f=1} END {exit !f}' "$FILES"; then
    awk -F'\t' -v c="$1" -v p="$2" -v l="$line" '$1==c && $2==p {print l; next} {print}' "$FILES" > "$FILES.tmp" && mv "$FILES.tmp" "$FILES"
  else
    printf '%s\n' "$line" >> "$FILES"
  fi
}

recorded_sha() { [ -f "$FILES" ] && awk -F'\t' -v c="$1" -v p="$2" '$1==c && $2==p {print $3}' "$FILES"; }

# install_tree <component> <src-dir> <dst-dir>: copy, render text files, back up different files
install_tree() {
  local comp="$1" src="$2" dst="$3" f rel tmp bak
  while IFS= read -r -d '' f; do
    rel="${f#"$src"/}"; tmp="$(mktemp)"; bak="-"
    case "$rel" in *.md|*.json|*.sh) render "$f" "$tmp" ;; *) cp "$f" "$tmp" ;; esac
    if [ -e "$dst/$rel" ] && cmp -s "$tmp" "$dst/$rel"; then
      [ "$DRY" = 1 ] || record "$comp" "$dst/$rel" "$(sha "$tmp")" "-"; rm -f "$tmp"; continue
    fi
    if dry "write $dst/$rel"; then rm -f "$tmp"; continue; fi
    if [ -e "$dst/$rel" ] && [ "$(sha "$dst/$rel")" != "$(recorded_sha "$comp" "$dst/$rel")" ]; then
      bak="$dst/$rel.bak-$WB_STAMP"; cp -pL "$dst/$rel" "$bak"; warn "replaced (backup $(basename "$bak")): $dst/$rel"
    fi
    mkdir -p "$(dirname "$dst/$rel")"; [ -x "$f" ] && chmod +x "$tmp"; chmod go+r "$tmp"
    record "$comp" "$dst/$rel" "$(sha "$tmp")" "$bak"; mv "$tmp" "$dst/$rel"
  done < <(find "$src" -type f -not -path '*/node_modules/*' -not -path '*/.claude-plugin/types/*' -print0)
}

merge_settings() { # merge_settings <component> <fragment>
  local comp="$1" frag tmp out
  frag="$(mktemp)"; render "$2" "$frag"
  if [ "$PLUGINS" = 0 ]; then
    python3 -I -c '
import json, sys
d = json.load(open(sys.argv[1])); d.pop("enabledPlugins", None); d.pop("extraKnownMarketplaces", None)
json.dump(d, open(sys.argv[1], "w"))' "$frag"
  fi
  if [ "$DRY" = 1 ]; then
    tmp="$(mktemp)"; [ -f "$CLAUDE_HOME/settings.json" ] && cp -L "$CLAUDE_HOME/settings.json" "$tmp"
    out="$(WB_STAMP= wbpy merge "$tmp" "$frag" - "$comp")"; rm -f "$tmp"
    echo "  [dry-run] settings.json: $out ($comp)"
  else
    out="$(wbpy merge "$CLAUDE_HOME/settings.json" "$frag" "$RECEIPT" "$comp")"
    ok "settings.json: $out ($comp)"
  fi
  rm -f "$frag"
}

insert_block() { # insert_block <NAME> <block-file>
  local tmp; tmp="$(mktemp)"; render "$2" "$tmp"
  if [ "$DRY" = 1 ]; then echo "  [dry-run] CLAUDE.md: insert/refresh block $1"
  else wbpy block-insert "$CLAUDE_HOME/CLAUDE.md" "$tmp" "$1" || { rm -f "$tmp"; exit 1; }; ok "CLAUDE.md: block $1"; fi
  rm -f "$tmp"
}

optional_args() { OPT_ARGS=(); case "$1" in vault) OPT_ARGS=(--path "$VAULT_PATH") ;; esac; }
# remember the vault path so uninstall compares against the same rendered skill
if [ "$VAULT_PATH" = "$HOME/vault" ] && [ -f "$STATE/vault-path" ] && [ "$UNINSTALL" = 1 ]; then VAULT_PATH="$(cat "$STATE/vault-path")"; fi

install_optional() {
  local o="$1" d="$WB/optional/$1"; optional_args "$o"
  echo "== optional: $o"
  if [ "$DRY" = 1 ]; then bash "$d/setup.sh" --dry-run "${OPT_ARGS[@]}"; else bash "$d/setup.sh" "${OPT_ARGS[@]}"; fi
  if [ -f "$d/settings.fragment.json" ]; then merge_settings "$o" "$d/settings.fragment.json"; fi
  if [ -f "$d/CLAUDE.md" ]; then insert_block "$(upper "$o")" "$d/CLAUDE.md"; fi
  if [ "$DRY" = 0 ] && ! grep -qxF "optional	$o" "$FILES" 2>/dev/null; then printf 'optional\t%s\n' "$o" >> "$FILES"; fi
  if [ "$DRY" = 0 ] && [ "$o" = vault ]; then printf '%s\n' "$VAULT_PATH" > "$STATE/vault-path"; fi
}

remove_component() { # remove_component <component> [block-name]
  local comp="$1" c p s b
  if dry "remove $comp: unmodified recorded files, its settings and its CLAUDE.md block"; then return; fi
  [ -f "$RECEIPT" ] && ok "settings.json: $(wbpy unmerge "$CLAUDE_HOME/settings.json" "$RECEIPT" "$comp") ($comp)"
  if [ -n "${2:-}" ]; then wbpy block-remove "$CLAUDE_HOME/CLAUDE.md" "$2"; fi
  [ -f "$FILES" ] || return 0
  while IFS=$'\t' read -r c p s b; do
    [ "$c" = "$comp" ] || continue
    [ -e "$p" ] || continue
    if [ "$(sha "$p")" != "$s" ]; then warn "kept (modified since install): $p"; continue; fi
    rm -f "$p"
    if [ "$b" != "-" ] && [ -e "$b" ]; then mv "$b" "$p"; ok "restored your earlier file: $p"
    else rmdir "$(dirname "$p")" 2>/dev/null || true; fi
  done < "$FILES"
  awk -F'\t' -v c="$comp" '$1!=c && !($1=="optional" && $2==c)' "$FILES" > "$FILES.tmp" && mv "$FILES.tmp" "$FILES"
  ok "removed: $comp"
}

# ---------------------------------------------------------------- uninstall
if [ "$UNINSTALL" = 1 ]; then
  echo "== workbench uninstall ($CLAUDE_HOME)"
  [ -f "$FILES" ] || [ -f "$RECEIPT" ] || fail "nothing recorded for $CLAUDE_HOME: workbench does not look installed there"
  wbpy check "$CLAUDE_HOME/settings.json" "$CLAUDE_HOME/CLAUDE.md" CORE $(upper "$ALL_OPTIONALS")
  installed=" $(awk -F'\t' '$1=="optional"{print $2}' "$FILES" 2>/dev/null | tr '\n' ' ') "
  targets=""
  for o in ${OPTIONALS:-$installed}; do
    case "$installed" in *" $o "*) targets="$targets $o" ;; *) warn "$o is not installed here: skipped" ;; esac
  done
  for o in $targets; do
    echo "== optional: $o"; optional_args "$o"
    if [ "$DRY" = 1 ]; then bash "$WB/optional/$o/setup.sh" --uninstall --dry-run "${OPT_ARGS[@]}"
    else bash "$WB/optional/$o/setup.sh" --uninstall "${OPT_ARGS[@]}"; fi
    remove_component "$o" "$(upper "$o")"
  done
  if [ -z "$OPTIONALS" ]; then
    echo "== core"; remove_component core CORE
    if [ "$DRY" = 0 ]; then
      for d in "$SHARE/mods" "$CLAUDE_HOME/hooks/workbench"; do [ -d "$d" ] && find "$d" -depth -type d -empty -delete; done
      rm -f "$RECEIPT" "$FILES" "$STATE/vault-path"; rmdir "$STATE" "$SHARE/state" "$SHARE" 2>/dev/null || true
    fi
  fi
  echo "== Done. Backups (*.bak-*) were kept. Plugins stay installed: remove with 'claude plugin uninstall <name>'."
  exit 0
fi

# ---------------------------------------------------------------- install
echo "== 1. Prerequisites"
for c in git python3 sha256sum; do command -v "$c" >/dev/null || fail "missing '$c'"; done
ok "git, python3"
wbpy check "$CLAUDE_HOME/settings.json" "$CLAUDE_HOME/CLAUDE.md" CORE $(upper "$ALL_OPTIONALS") || fail "fix the file above before installing (nothing was changed)"
command -v node >/dev/null && ok "node $(node -v)" || warn "node missing: needed by the oh-my-claudecode status line (HUD)"
MODS=1
if command -v claude >/dev/null; then
  cv="$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
  ok "claude $cv"
  if ! version_ge "${cv:-0}" "$MIN_MODS_VERSION"; then MODS=0; warn "mods need Claude Code >= $MIN_MODS_VERSION: skipping them (update with 'claude update')"; fi
else
  [ "$DRY" = 1 ] || fail "Claude Code not found. Install it first: https://docs.claude.com/en/docs/claude-code (then rerun)"
  warn "Claude Code not found (dry-run continues)"
fi

echo "== 2. Core ($CLAUDE_HOME)"
[ "$DRY" = 1 ] || mkdir -p "$STATE" "$CLAUDE_HOME"
for s in work-mode parallel-delegation handoff; do install_tree core "$WB/core/skills/$s" "$CLAUDE_HOME/skills/$s"; done
ok "skills: work-mode, parallel-delegation, handoff"
install_tree core "$WB/core/hooks" "$CLAUDE_HOME/hooks/workbench"
ok "hook: session-start-handoffs"
frag="$WB/core/settings.fragment.json"
if [ "$MODS" = 1 ]; then
  install_tree core "$WB/core/mods" "$SHARE/mods"; ok "mods: model-router, session-board ($SHARE/mods)"
else
  frag="$(mktemp)"; python3 -I -c '
import json, sys
d = json.load(open(sys.argv[1])); d["env"].pop("CLAUDE_CODE_PLUGIN_DIRS", None)
json.dump(d, open(sys.argv[2], "w"))' "$WB/core/settings.fragment.json" "$frag"
fi
merge_settings core "$frag"
insert_block CORE "$WB/core/CLAUDE.md"

for o in $OPTIONALS; do install_optional "$o"; done

if [ "$PLUGINS" = 1 ]; then
  echo "== Plugins (user scope, from their marketplaces)"
  for m in "https://github.com/Yeachan-Heo/oh-my-claudecode.git#v5.7.31" \
           anthropics/claude-plugins-official \
           forrestchang/andrej-karpathy-skills; do
    if dry "claude plugin marketplace add $m"; then continue; fi
    claude plugin marketplace add "$m" >/dev/null 2>&1 && ok "marketplace $m" || warn "marketplace $m: failed or already added"
  done
  for p in oh-my-claudecode@omc mattpocock-skills@claude-plugins-official andrej-karpathy-skills@karpathy-skills; do
    if dry "claude plugin install $p --scope user"; then continue; fi
    claude plugin install "$p" --scope user >/dev/null 2>&1 && ok "$p" || warn "failed: $p (retry: claude plugin install $p --scope user)"
  done
fi

echo
echo "== Done. Next steps:"
cat <<TXT
  1. Open Claude Code and run /oh-my-claudecode:omc-setup (adds the OMC rules block and the status line HUD).
  2. Check: /skills lists work-mode, parallel-delegation, handoff; /plugin shows the 2 mods.
  3. In any project, handoffs go to docs/handoffs/ and are listed when a session starts there.
  Uninstall: ./uninstall.sh  (or ./uninstall.sh --with <optional>)
TXT
