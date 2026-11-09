#!/usr/bin/env python3
"""Vault utility (standard library only). Rules in ../CLAUDE.md.

  python3 tools/vault.py pending              # raw/ sources not yet ingested (or changed)
  python3 tools/vault.py register <path>...   # record ingested sources in manifest.tsv
  python3 tools/vault.py lint [--days N]      # wiki health report (fixes nothing)

Exit 0 = nothing to report; 1 = the report has items.
"""
import hashlib, re, sys, datetime
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
RAW, WIKI = VAULT / "raw", VAULT / "wiki"
MANIFEST = VAULT / "manifest.tsv"
TAG_ROOTS = {"topic", "work", "method", "tech", "personal", "source"}  # keep in sync with CLAUDE.md
REQUIRED = ["type", "aliases", "tags", "sources", "updated", "reviewed"]
LINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def raw_files(paths=None):
    roots = [VAULT / p for p in paths] if paths else [RAW]
    for r in roots:
        for f in ([r] if r.is_file() else sorted(r.rglob("*"))):
            if f.is_file() and not f.name.startswith("."):
                yield f


def manifest():
    m = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()[1:]:
            h, path, _date = line.split("\t")
            m[path] = h
    return m


def raw_status():
    """Yield (state, relative path) for each raw/ file that is new or changed."""
    m = manifest()
    for f in raw_files():
        rel = f.relative_to(VAULT).as_posix()
        if rel not in m:
            yield "new", rel
        elif m[rel] != sha(f):
            yield "changed", rel


def cmd_pending():
    out = [f"{'NEW' if s == 'new' else 'CHANGED':<9} {rel}" + ("  (raw/ is immutable: check)" if s == "changed" else "")
           for s, rel in raw_status()]
    print("\n".join(out) or "nothing pending")
    return 1 if out else 0


def cmd_register(paths):
    if not paths:
        sys.exit("usage: register <file-or-folder in raw/>...")
    m, today, new = manifest(), datetime.date.today().isoformat(), []
    for f in raw_files(paths):
        rel = f.relative_to(VAULT).as_posix()
        if not rel.startswith("raw/"):
            sys.exit(f"outside raw/: {rel}")
        if m.get(rel) != (h := sha(f)):
            new.append(f"{h}\t{rel}\t{today}")
    if not MANIFEST.exists():
        MANIFEST.write_text("sha256\tpath\tingested\n", encoding="utf-8")
    with MANIFEST.open("a", encoding="utf-8") as fh:
        fh.writelines(line + "\n" for line in new)
    print(f"registered: {len(new)}")
    return 0


def frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.split("#")[0].strip()
    return fm


def items(v):
    return [a.strip().strip("\"'").lower() for a in v.strip("[]").split(",") if a.strip().strip("\"'")]


def cmd_lint(days=90):
    pages = {p.stem: p for p in WIKI.rglob("*.md") if p.stem not in ("index", "log")}
    index = (WIKI / "index.md").read_text(encoding="utf-8")
    inbound = {s: 0 for s in pages}
    issues, names = [], {}
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    for slug, p in sorted(pages.items()):
        rel = p.relative_to(VAULT).as_posix()
        text = p.read_text(encoding="utf-8")
        fm = frontmatter(text)
        if fm is None:
            issues.append(f"no frontmatter       {rel}")
            continue
        for k in REQUIRED:
            if k not in fm:
                issues.append(f"missing '{k}'        {rel}")
        if fm.get("type") == "source":
            r = fm.get("raw", "")
            if not r or not (VAULT / r).exists():
                issues.append(f"raw file missing     {rel} -> {r or '(empty)'}")
        elif fm.get("sources", "[]") in ("[]", ""):
            issues.append(f"no sources           {rel}")
        if not items(fm.get("aliases", "")):
            issues.append(f"no aliases           {rel}")
        for tag in items(fm.get("tags", "")):
            if "/" not in tag or tag.split("/")[0] not in TAG_ROOTS:
                issues.append(f"tag not in taxonomy  {rel} -> {tag}")
        for name in items(fm.get("aliases", "")) + [slug.lower()]:
            names.setdefault(name, set()).add(slug)
        try:
            if datetime.date.fromisoformat(fm.get("updated", "")) < cutoff:
                issues.append(f"stale (>{days}d)         {rel}")
        except ValueError:
            issues.append(f"invalid updated     {rel}")
        if (n := text.count("\n")) > 400:
            issues.append(f"large ({n} lines)    {rel}")
        if f"[[{slug}]]" not in index:
            issues.append(f"not in index         {rel}")
        for target in set(LINK.findall(text)):
            target = target.strip()
            if target in inbound and target != slug:
                inbound[target] += 1
            elif target not in pages:
                issues.append(f"dead link            {rel} -> [[{target}]]")
    issues += [f"orphan (no backlinks) {s}" for s, n in inbound.items() if n == 0]
    issues += [f"possible duplicate   '{a}': {', '.join(sorted(s))}" for a, s in names.items() if len(s) > 1]
    issues += [f"raw {'not ingested' if s == 'new' else 'CHANGED     '}    {rel}" for s, rel in raw_status()]
    print("\n".join(issues) or "wiki ok")
    return 1 if issues else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("pending", "register", "lint"):
        sys.exit(__doc__)
    if a[0] == "pending":
        sys.exit(cmd_pending())
    if a[0] == "register":
        sys.exit(cmd_register(a[1:]))
    days = int(a[a.index("--days") + 1]) if "--days" in a else 90
    sys.exit(cmd_lint(days))
