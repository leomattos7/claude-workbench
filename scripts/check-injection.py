#!/usr/bin/env python3
"""Block prompt-injection and supply-chain tricks before they reach main.

Usage: python3 -I scripts/check-injection.py [--base REF] [ROOT]
  ROOT        directory to scan (default: this repo); inside git, tracked and unignored files only
  --base REF  also compare settings fragments with REF: no deny/ask entry may be dropped, and
              env, enabledPlugins and extraKnownMarketplaces may not change (owner pushes those)
Exit: 0 = clean (warnings allowed), 1 = findings, 2 = usage error.
Some patterns are bracketed (e.g. "tc[p]") so this file does not flag itself.
Not covered (left to review): string splitting, variable indirection, hooks calling helpers elsewhere.
"""
import json
import os
import re
import subprocess
import sys

# invisible, direction-changing, filler and variation-selector characters; Unicode "tag" smuggling
INVISIBLE_RANGES = [(0x00AD, 0x00AD), (0x061C, 0x061C), (0x115F, 0x1160), (0x180E, 0x180E), (0x200B, 0x200F),
                    (0x202A, 0x202E), (0x2060, 0x2064), (0x2066, 0x2069), (0x3164, 0x3164), (0xFE00, 0xFE0F),
                    (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xE0000, 0xE007F), (0xE0100, 0xE01EF)]
INVISIBLE = re.compile("[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in INVISIBLE_RANGES) + "]")
SHELL = r"(sudo(\s+-\S+)*\s+)?(\S*/)?(ba|z|da|k)?s[h]\b"
REMOTE_EXEC = [
    (re.compile(r"\b(curl|wget)\b(?:[^\n]|\\\n)*\|\s*" + SHELL), "download piped to a shell"),
    (re.compile(r"\b(curl|wget)\b(?:[^\n]|\\\n)*\|\s*(sudo\s+)?(\S*/)?(python[0-9.]*|per[l]|rub[y]|nod[e])\b"),
     "download piped to an interpreter"),
    (re.compile(r"\bbase64\s+(-d\w*|--decode)\b[^\n]*\|\s*" + SHELL), "decoded payload piped to a shell"),
    (re.compile(r"/dev/(tc[p]|ud[p])/"), "raw socket via /dev/tcp"),
    (re.compile(r"\b(nc|ncat|netcat)\s+-|\b(nc|ncat|netcat)\b[^\n]*\s-[ec]\b"), "netcat"),
    (re.compile(r"(\beval|\bsource|(^|[\s;&|])\.)\s+[\"']?(\$\(|<\(|`)\s*(curl|wget)\b"), "eval of remote content"),
    (re.compile(r"\b((ba|z)?s[h]|python[0-9.]*|perl|ruby|node)\s+(-[ce]\s+)?[\"']?(\$\(|<\(|`)\s*(curl|wget)\b"),
     "interpreter runs remote content"),
]
NETWORK = re.compile(r"\b(curl|wget|ncat|netcat|socat|telnet|ssh|scp|rsync)\b|\bnc\s|https?:/[/]|\bfetch\s*\("
                     r"|\bWebSocket\b|XMLHttpRequest|\b(urllib|requests|socket|http\.client)\b"
                     r"|['\"`](node:)?(https?|http2|net|dgram|tls)['\"`]")
PRIVILEGED_TRIGGER = re.compile(r"\b(pull_request_targe[t]|workflow_ru[n]|issue_commen[t])\b")
HTML_COMMENT = re.compile(r"<!--(.*?)(?:-->|\Z)", re.S)
INSTRUCTION = re.compile(r"\b(ignore|disregard|instructions?|system prompt|assistant|you must|execute|run|curl|wget)\b|https?:", re.I)
FRONTMATTER_RISK = re.compile(r"^(allowed-tools|hooks)\s*:", re.M)

FRAGMENT_KEYS = {"env", "permissions", "hooks", "enabledPlugins", "extraKnownMarketplaces", "omcHud"}
PERMISSION_KEYS = {"deny", "ask"}
FROZEN_KEYS = ("env", "enabledPlugins", "extraKnownMarketplaces")
ENV_ALLOWED = {"CLAUDE_CODE_PLUGIN_DIRS", "OMC_CONTEXT_GUARD_THRESHOLD"}
PLUGIN_KEYS = {"name", "version", "description", "author"}
CONFIG_FILES = {"settings.json", "settings.local.json", ".mcp.json", ".lsp.json"}
HOOK_COMMAND = re.compile(r'^"\$HOME/\.claude/hooks/workbench/[A-Za-z0-9._-]+"$')

findings, warnings = [], []


def lineno(text, pos):
    return text.count("\n", 0, pos) + 1


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, check=True).stdout
        return sorted({os.fsdecode(p) for p in out.split(b"\0") if p})
    except (OSError, subprocess.CalledProcessError):
        return sorted(os.path.relpath(os.path.join(d, f), root)
                      for d, dirs, fs in os.walk(root) if ".git" not in d.split(os.sep) for f in fs)


def hooks_of(fragment):
    for groups in (fragment.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                yield hook


def fragment_hook_files(root, rel):
    """Basenames that the settings fragment next to `rel` installs as hooks."""
    try:
        frag = read_json(os.path.join(root, os.path.dirname(rel), "settings.fragment.json"))
        return {str(h.get("command", "")).strip('"').rsplit("/", 1)[-1] for h in hooks_of(frag)}
    except (OSError, ValueError, AttributeError, TypeError):
        return set()


def check_fragment(rel, text):
    try:
        frag = json.loads(text)
        assert isinstance(frag, dict)
    except (ValueError, AssertionError):
        findings.append(f"{rel}: settings fragment is not a JSON object")
        return
    for key in sorted(set(frag) - FRAGMENT_KEYS):
        findings.append(f"{rel}: settings fragment sets '{key}' (allowed: {', '.join(sorted(FRAGMENT_KEYS))})")
    for key in sorted(set(frag.get("permissions") or {}) - PERMISSION_KEYS):
        findings.append(f"{rel}: settings fragment sets permissions.{key} (only deny/ask may be added)")
    for name in sorted(set(frag.get("env") or {}) - ENV_ALLOWED):
        findings.append(f"{rel}: settings fragment sets env {name} (not in the checker's ENV_ALLOWED)")
    hud = frag.get("omcHud")
    if hud is not None:  # display toggles only: other omcHud keys (e.g. a rate-limit provider command) can run code
        els = hud.get("elements") if isinstance(hud, dict) else None
        if not (isinstance(hud, dict) and set(hud) == {"elements"} and isinstance(els, dict)
                and all(isinstance(v, bool) for v in els.values())):
            findings.append(f"{rel}: omcHud may only hold 'elements' with true/false values")
    for hook in hooks_of(frag):
        if not isinstance(hook, dict) or hook.get("type") != "command" or not HOOK_COMMAND.match(str(hook.get("command"))):
            findings.append(f"{rel}: hook must be a command \"$HOME/.claude/hooks/workbench/<file>\", got {json.dumps(hook)}")


def compare_with_base(root, base, head_files):
    try:
        out = subprocess.run(["git", "-C", root, "ls-tree", "-r", "-z", "--name-only", base],
                             capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        print(f"cannot read git ref {base}", file=sys.stderr)
        sys.exit(2)
    names = {os.fsdecode(p) for p in out.split(b"\0") if p} | set(head_files)
    for rel in sorted(n for n in names if n.rsplit("/", 1)[-1] == "settings.fragment.json"):
        old = subprocess.run(["git", "-C", root, "show", f"{base}:{rel}"], capture_output=True, text=True)
        try:
            before = json.loads(old.stdout) if old.returncode == 0 else {}
        except ValueError:
            before = {}
        try:
            after = read_json(os.path.join(root, rel))
        except (OSError, ValueError):
            after = {}
        if not isinstance(before, dict) or not isinstance(after, dict):
            continue  # check_fragment already reports a non-object head
        for kind in ("deny", "ask"):
            gone = set((before.get("permissions") or {}).get(kind, [])) - set((after.get("permissions") or {}).get(kind, []))
            for entry in sorted(gone):
                findings.append(f"{rel}: permissions.{kind} entry removed since {base}: {entry}")
        for key in FROZEN_KEYS:
            if before.get(key) != after.get(key):
                findings.append(f"{rel}: '{key}' changed since {base} (only the owner changes it, by direct push)")


def scan(root, rel):
    path = os.path.join(root, rel)
    if not os.path.isfile(path) or os.path.islink(path):
        return
    parts = rel.split("/")
    name = parts[-1]
    with open(path, "rb") as f:
        data = f.read()
    if b"\0" in data:
        findings.append(f"{rel}: binary file (NUL byte); this repo holds text only")
        return
    if name in CONFIG_FILES:
        findings.append(f"{rel}: Claude Code config file; it would run on whoever opens this repo")
    text = data.decode("utf-8", "replace")
    for m in INVISIBLE.finditer(text):
        findings.append(f"{rel}:{lineno(text, m.start())}: invisible or bidi character U+{ord(m.group()):04X}")
    for rx, why in REMOTE_EXEC:
        for m in rx.finditer(text):
            findings.append(f"{rel}:{lineno(text, m.start())}: {why}: {m.group().strip()}")
    is_hook = "hooks" in parts[:-1] or rel.startswith("core/mods/") or name in fragment_hook_files(root, rel)
    if is_hook and name != "settings.fragment.json":
        for m in NETWORK.finditer(text):
            findings.append(f"{rel}:{lineno(text, m.start())}: network access in hook or mod code: {m.group().strip()}")
    if name == "settings.fragment.json":
        check_fragment(rel, text)
    if name == "plugin.json" and parts[-2:-1] == [".claude-plugin"]:
        try:
            extra = set(json.loads(text)) - PLUGIN_KEYS
        except (ValueError, TypeError):
            extra = {"<not a JSON object>"}
        for key in sorted(extra):
            findings.append(f"{rel}: plugin.json sets '{key}' (allowed: {', '.join(sorted(PLUGIN_KEYS))})")
    if rel.startswith(".github/workflows/"):
        for m in PRIVILEGED_TRIGGER.finditer(text):
            findings.append(f"{rel}:{lineno(text, m.start())}: privileged trigger {m.group()} (base context with secrets)")
    if rel.endswith(".md"):
        if text.startswith("---\n"):
            front = text[4:text.find("\n---", 4)]
            for m in FRONTMATTER_RISK.finditer(front):
                findings.append(f"{rel}:{lineno(front, m.start()) + 1}: frontmatter '{m.group(1)}' grants tools or runs hooks")
        for m in HTML_COMMENT.finditer(text):
            if INSTRUCTION.search(m.group(1)):
                warnings.append(f"{rel}:{lineno(text, m.start())}: hidden HTML comment with instruction-like text")


def main(argv):
    base = None
    if argv[:1] == ["--base"]:
        if len(argv) < 2:
            print(__doc__, file=sys.stderr)
            return 2
        base, argv = argv[1], argv[2:]
    if len(argv) > 1 or (argv and argv[0].startswith("-")):
        print(__doc__, file=sys.stderr)
        return 2
    root = argv[0] if argv else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = list_files(root)
    for rel in files:
        scan(root, rel)
    if base:
        compare_with_base(root, base, files)
    for w in warnings:
        print(f"warn {w}")
    for f in findings:
        print(f"FAIL {f}")
    if findings:
        return 1
    print("check-injection: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
