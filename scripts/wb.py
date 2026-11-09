#!/usr/bin/env python3
"""Workbench helpers for install.sh (stdlib only).

  wb.py check   <settings.json> <CLAUDE.md> [NAME...] exit 1 with a readable message if unusable
  wb.py merge   <settings.json> <fragment.json> <receipt.json|-> <component>
  wb.py unmerge <settings.json> <receipt.json> <component>
  wb.py block-insert <CLAUDE.md> <block-file> <NAME>
  wb.py block-remove <CLAUDE.md> <NAME>

merge only ADDS: it never changes a value the user already has. Everything it adds is
recorded in the receipt, so unmerge removes exactly that and nothing the user owned.
Before the first rewrite of a file in a run, a real copy is saved as <file>.bak-$WB_STAMP.
Writes are atomic and go through symlinks (a symlinked settings.json stays a symlink).
"""
import json
import os
import re
import shutil
import sys
import tempfile

PLUGIN_DIRS = "CLAUDE_CODE_PLUGIN_DIRS"
# objects under these keys belong to whoever created them: never merge into an existing one
ATOMIC_PARENTS = {("extraKnownMarketplaces",), ("enabledPlugins",)}


def die(msg):
    sys.stderr.write(f"wb: {msg}\n")
    sys.exit(1)


def read_raw(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write_raw(path, text, backup=True):
    """Back up once per run, then replace atomically (through symlinks)."""
    real = os.path.realpath(path)
    stamp = os.environ.get("WB_STAMP")
    if backup and stamp and os.path.exists(real):
        bak = f"{path}.bak-{stamp}"
        if not os.path.exists(bak):
            shutil.copyfile(real, bak)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real) or ".", prefix=".wb-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    if os.path.exists(real):
        shutil.copymode(real, tmp)
    else:
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
    os.replace(tmp, real)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    text = read_raw(path)
    if not text.strip():
        return default
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON ({e}); fix it and rerun")
    if not isinstance(data, dict):
        die(f"{path} must contain a JSON object")
    return data


def save_json(path, data, backup=True):
    new = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if not os.path.exists(path) or read_raw(path) != new:
        write_raw(path, new, backup)


def hook_commands(entry):
    return {h.get("command") for h in entry.get("hooks", [])}


def merge(cur, frag, path, ops):
    for key, val in frag.items():
        here = path + [key]
        if key == PLUGIN_DIRS and isinstance(val, str):
            have = [d for d in cur.get(key, "").split(":") if d]
            for d in (d for d in val.split(":") if d):
                if d not in have:
                    have.append(d)
                    ops.append({"op": "plugin_dir", "path": here, "value": d})
            if have:
                cur[key] = ":".join(have)
        elif path == ["hooks"] and isinstance(val, list):
            lst = cur.setdefault(key, [])
            existing = set().union(*(hook_commands(e) for e in lst)) if lst else set()
            for entry in val:
                if hook_commands(entry) & existing:
                    continue
                lst.append(entry)
                ops.append({"op": "list_add", "path": here, "value": entry})
        elif tuple(path) in ATOMIC_PARENTS:
            if key not in cur:
                cur[key] = val
                ops.append({"op": "set", "path": here, "value": val})
        elif isinstance(val, dict):
            if key not in cur:
                cur[key] = {}
                ops.append({"op": "created", "path": here})
            if isinstance(cur[key], dict):
                merge(cur[key], val, here, ops)
        elif isinstance(val, list):
            lst = cur.setdefault(key, [])
            for item in val:
                if item not in lst:
                    lst.append(item)
                    ops.append({"op": "list_add", "path": here, "value": item})
        elif key not in cur:
            cur[key] = val
            ops.append({"op": "set", "path": here, "value": val})


def walk(data, path):
    for k in path:
        if not isinstance(data, dict) or k not in data:
            return None
        data = data[k]
    return data


def unmerge(cur, ops):
    for op in reversed(ops):
        parent, key = walk(cur, op["path"][:-1]), op["path"][-1]
        if not isinstance(parent, dict) or key not in parent:
            continue
        kind = op["op"]
        if kind == "set" and parent[key] == op["value"]:
            del parent[key]
        elif kind == "list_add" and isinstance(parent[key], list):
            if op["value"] in parent[key]:
                parent[key].remove(op["value"])
            if not parent[key]:
                del parent[key]
        elif kind == "plugin_dir":
            dirs = [d for d in parent[key].split(":") if d and d != op["value"]]
            if dirs:
                parent[key] = ":".join(dirs)
            else:
                del parent[key]
        elif kind == "created" and parent[key] == {}:
            del parent[key]


# A block is appended as: <separator><START[ eof-nonl]>\n<body>\n<END>\n
# separator = "" (empty file), "\n" (file ended with a newline), "\n\n" (it did not; flagged
# "eof-nonl" in the START marker). block_remove undoes exactly that, byte for byte.
NONL = " eof-nonl"


def find_block(text, name, md):
    starts = list(re.finditer(rf"<!-- WORKBENCH:{re.escape(name)}:START(?:{NONL})? -->", text))
    ends = list(re.finditer(rf"<!-- WORKBENCH:{re.escape(name)}:END -->", text))
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or ends[0].start() < starts[0].start():
        die(f"{md}: the WORKBENCH:{name} START/END markers are broken (found {len(starts)} START, "
            f"{len(ends)} END). Fix them by hand (keep exactly one pair, or delete both) and rerun.")
    m = re.compile(
        rf"<!-- WORKBENCH:{re.escape(name)}:START(?P<flag>{NONL})? -->\r?\n.*?<!-- WORKBENCH:{re.escape(name)}:END -->(?:\r?\n)?",
        re.S,
    ).search(text)
    if not m:
        die(f"{md}: the WORKBENCH:{name} block is malformed; fix it by hand and rerun.")
    return m


def block_insert(md, block_file, name):
    body = read_raw(block_file).strip("\r\n")
    text = read_raw(md) if os.path.exists(md) else ""
    m = find_block(text, name, md)
    if m:
        flag = m.group("flag") or ""
        block = f"<!-- WORKBENCH:{name}:START{flag} -->\n{body}\n<!-- WORKBENCH:{name}:END -->\n"
        new = text[: m.start()] + block + text[m.end():]
    else:
        flag = NONL if text and not text.endswith("\n") else ""
        sep = "" if not text else ("\n\n" if flag else "\n")
        new = f"{text}{sep}<!-- WORKBENCH:{name}:START{flag} -->\n{body}\n<!-- WORKBENCH:{name}:END -->\n"
    if new != text:
        write_raw(md, new)


def block_remove(md, name):
    if not os.path.exists(md):
        return
    text = read_raw(md)
    m = find_block(text, name, md)
    if not m:
        return
    before, after = text[: m.start()], text[m.end():]
    if m.group("flag") and before.endswith("\n\n"):
        before = before[:-2]
    elif before.endswith("\r\n"):
        before = before[:-2]
    elif before.endswith("\n"):
        before = before[:-1]
    new = before + after
    if new or os.path.islink(md):
        write_raw(md, new)  # a symlinked CLAUDE.md keeps its link
    else:
        stamp = os.environ.get("WB_STAMP")
        if stamp and not os.path.exists(f"{md}.bak-{stamp}"):
            shutil.copyfile(os.path.realpath(md), f"{md}.bak-{stamp}")
        os.remove(md)  # it only held workbench blocks, so it did not exist before


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "check" and len(argv) >= 4:
        load_json(argv[2], {})
        if os.path.exists(argv[3]):
            try:
                text = read_raw(argv[3])
            except UnicodeDecodeError:
                die(f"{argv[3]} is not UTF-8 text")
            for name in argv[4:]:
                find_block(text, name, argv[3])
    elif cmd == "merge" and len(argv) == 6:
        settings, frag_path, receipt_path, comp = argv[2:]
        cur, frag = load_json(settings, {}), load_json(frag_path, {})
        ops = []
        merge(cur, frag, [], ops)
        if ops and receipt_path != "-":
            save_json(settings, cur)
            receipt = load_json(receipt_path, {})
            receipt.setdefault(comp, []).extend(ops)
            save_json(receipt_path, receipt, backup=False)
        print(f"{len(ops)} setting(s) added")
    elif cmd == "unmerge" and len(argv) == 5:
        settings, receipt_path, comp = argv[2:]
        receipt = load_json(receipt_path, {})
        ops = receipt.pop(comp, [])
        if ops and os.path.exists(settings):
            cur = load_json(settings, {})
            unmerge(cur, ops)
            save_json(settings, cur)
        save_json(receipt_path, receipt, backup=False)
        print(f"{len(ops)} setting(s) removed")
    elif cmd == "block-insert" and len(argv) == 5:
        block_insert(*argv[2:])
    elif cmd == "block-remove" and len(argv) == 4:
        block_remove(*argv[2:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
