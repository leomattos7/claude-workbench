#!/usr/bin/env python3
"""Collect sources into raw/ for a guided vault fill (standard library only). Rules in ../CLAUDE.md.

  python3 tools/collect.py discover [--root DIR]... [--claude-home DIR]...
  python3 tools/collect.py repo <repo>... [--commits N] [--dry-run]
  python3 tools/collect.py sessions <history-dir-or-project-path>... [--days N] [--skip-recent MIN]
                                    [--claude-home DIR]... [--dry-run]
  python3 tools/collect.py files <dir-or-file>... [--dry-run]

discover lists candidates (git repos, Claude Code session history by project, decision/ADR/handoff
folders) and writes nothing. The other commands write only under raw/repos, raw/sessions and raw/docs,
in one folder per source (<name>-<hash of its path>), never overwrite a file (a changed source lands next
to the old copy as <name>.<date><ext>; an unchanged one is skipped), and redact secret-looking strings in
every text file they write. Ingesting what was collected is a separate step (CLAUDE.md, Ingest).
"""
import argparse, datetime, hashlib, json, os, re, subprocess, sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
RAW = VAULT / "raw"
TODAY = os.environ.get("COLLECT_TODAY") or datetime.date.today().isoformat()   # env only for tests

TEXT_EXT = {".md", ".mdx", ".markdown", ".txt", ".rst", ".adoc"}
DOC_EXT = TEXT_EXT | {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".html", ".htm"}
DECISION_DIRS = {"adr", "adrs", "decisions", "handoffs"}
REPO_DOC_DIRS = {"docs", "doc"} | DECISION_DIRS
SKIP_DIRS = {"node_modules", "__pycache__", "venv", "dist", "build", "target", "vendor"}
MAX_TEXT = 1_000_000          # bytes; bigger text files are skipped
MAX_BINARY = 20_000_000       # bytes; bigger PDFs/Office files are skipped
MAX_REPO_FILES = 300
MAX_FOLDER_FILES = 500
MAX_TURN = 4000               # characters kept per session turn
KEYWORD = r"(?:api[_-]?key|secret|token|passw(?:or)?d|credential)\w*"


def _with_digit(m):
    return "[REDACTED]" if re.search(r"\d", m.group()) else m.group()


SECRETS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*?"
                r"(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|\Z)", re.S), "[REDACTED]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[REDACTED]"),
    (re.compile(r"\b(?:sk|pk|rk)[-_][A-Za-z0-9_-]{20,300}"), _with_digit),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"), "[REDACTED]"),
    (re.compile(r"\b(?:glpat-[\w-]{20,}|hf_[A-Za-z0-9]{30,}|npm_[A-Za-z0-9]{36})"), "[REDACTED]"),
    (re.compile(r"\b(?:xox[abprs]|xapp)-[A-Za-z0-9-]{10,}"), "[REDACTED]"),
    (re.compile(r"(://hooks\.[\w.-]+/services/)\S+"), r"\1[REDACTED]"),   # chat webhook URLs
    (re.compile(r"\bSG\.[\w-]{20,}\.[\w-]{20,}"), "[REDACTED]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}"), "[REDACTED]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED]"),
    (re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{20,}"), r"\1[REDACTED]"),
    (re.compile(r"(://)[^/\s:@]+:[^/\s@]+(@)"), r"\1[REDACTED]\2"),       # user:password@host
    (re.compile(r"(://)[^/\s:@]{20,}(@)"), r"\1[REDACTED]\2"),            # token@host
    (re.compile(r"(?i)(" + KEYWORD + r"[\"']?\s*[:=]\s*)([\"'])[^\"'\n]{1,200}\2"), r"\1\2[REDACTED]\2"),
    (re.compile(r"(?i)(" + KEYWORD + r"[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]{8,}"), r"\1[REDACTED]"),
]
NOISE = re.compile(r"<(system-reminder|task-notification|local-command-stdout|local-command-stderr|"
                   r"local-command-caveat|command-message|bash-input|bash-stdout|bash-stderr|"
                   r"user-prompt-submit-hook)>.*?</\1>", re.S)


def redact(text):
    for pattern, repl in SECRETS:
        text = pattern.sub(repl, text)
    return text


def slot(name, path):
    """Folder name unique per source, stable across runs: two 'decisions' folders never merge."""
    return f"{safe_name(name)}-{hashlib.sha1(str(path).encode()).hexdigest()[:6]}"


class Writer:
    """Writes into raw/ without ever replacing a file; counts what happened."""

    def __init__(self, dry):
        self.dry, self.n = dry, {"written": 0, "versions": 0, "unchanged": 0, "kept": 0}
        self.skipped, self.unredacted, self.roots = [], 0, set()

    def put(self, dest, data, text=True):
        """Skip if the original or any dated copy already holds this content; otherwise write the
        original name, or <name>.<today><ext> when the original exists with other content."""
        anc = dest.parent
        while not anc.exists():
            anc = anc.parent
        if not (anc.resolve().is_relative_to(RAW.resolve()) or RAW.is_relative_to(anc)):
            self.skip(str(dest), "resolves outside raw/ (symlink?)")
            return
        data = redact(data).encode("utf-8") if text else data
        self.roots.add(dest.relative_to(VAULT).parts[:3])
        if dest.exists():
            dated = re.compile(re.escape(dest.stem) + r"\.\d{4}-\d{2}-\d{2}" + re.escape(dest.suffix) + "$")
            copies = [dest] + [p for p in dest.parent.iterdir() if dated.match(p.name)]
            if any(p.read_bytes() == data for p in copies):
                self.n["unchanged"] += 1
                return
            dest = dest.with_name(f"{dest.stem}.{TODAY}{dest.suffix}")
            if dest.exists():
                self.n["kept"] += 1
                return
            self.n["versions"] += 1
        self.n["written"] += 1
        self.unredacted += not text
        if not self.dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

    def skip(self, what, why):
        self.skipped.append(f"skipped  {what}  ({why})")

    def report(self):
        verb = "would write" if self.dry else "written"
        print(f"{verb}: {self.n['written']} (new versions of changed files: {self.n['versions']}), "
              f"unchanged: {self.n['unchanged']}, changed again today, not written: {self.n['kept']}, "
              f"skipped: {len(self.skipped)}")
        for r in sorted(self.roots):
            print("into    " + "/".join(r) + "/")
        if self.unredacted:
            print(f"note: {self.unredacted} binary file(s) (PDF/Office) were copied as is; secrets inside them are not redacted")
        for line in self.skipped[:50]:
            print(line)
        if len(self.skipped) > 50:
            print(f"... and {len(self.skipped) - 50} more skipped")


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-.") or "unnamed"


def inside_vault(p):
    try:
        return p.resolve().is_relative_to(VAULT)
    except OSError:
        return False


def read_text(w, f):
    try:
        return f.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        w.skip(str(f), e.strerror or "unreadable")
        return None


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def claude_homes(extra):
    """Claude config dirs that have a projects/ folder, deduplicated (shared configs are often symlinked)."""
    cands = [Path(p).expanduser() for p in extra]
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        cands.append(Path(os.environ["CLAUDE_CONFIG_DIR"]))
    home = Path.home()
    cands += [home / ".claude"] + sorted(home.glob(".claude-*"))
    seen, out = set(), []
    for c in cands:
        proj = c / "projects"
        if proj.is_dir() and proj.resolve() not in seen:
            seen.add(proj.resolve())
            out.append(c)
    return out


def session_cwd(project_dir):
    for f in sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]:
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    if i > 200:
                        break
                    if '"cwd"' in line:
                        try:
                            d = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(d, dict) and d.get("cwd"):
                            return d["cwd"]
        except OSError:
            continue
    return None


# ---------- discover

def find_repos(roots, max_depth=3, budget=20000):
    repos = []
    for root in roots:
        stack = [(Path(root).expanduser(), 0)]
        while stack and budget > 0:
            d, depth = stack.pop()
            budget -= 1
            try:
                if inside_vault(d):
                    continue
                dot_git = d / ".git"
                if dot_git.is_dir():
                    repos.append(d)
                    continue
                if dot_git.is_file() or depth >= max_depth:   # .git file = linked worktree or submodule
                    continue
                kids = [k for k in d.iterdir() if k.is_dir() and not k.is_symlink()]
            except OSError:   # unreadable directory (Python <= 3.12 raises from is_dir)
                continue
            stack += [(k, depth + 1) for k in kids if not k.name.startswith(".") and k.name not in SKIP_DIRS]
    return repos


def decision_dirs(repo):
    """{folder: number of tracked doc files} for decision/ADR/handoff folders in a repo."""
    found = {}
    for f in git(repo, "ls-files", "-z").split("\0"):
        parts = f.split("/")
        for i, p in enumerate(parts[:-1]):
            if p.lower() in DECISION_DIRS:
                if Path(f).suffix.lower() in DOC_EXT:
                    key = repo.joinpath(*parts[:i + 1])
                    found[key] = found.get(key, 0) + 1
                break
    return found


def cmd_discover(a):
    print(f"vault: {VAULT}\n")
    repos = find_repos(a.root or [str(Path.home())])
    rows = sorted(((git(r, "log", "-1", "--format=%cs").strip() or "0000-00-00", r) for r in repos), reverse=True)
    print("REPOS (latest commit first; * = has decision/ADR/handoff folders; linked worktrees not listed)")
    folders = {}   # folder -> (count, where)
    for date, r in rows[:40]:
        dec = decision_dirs(r)
        folders.update({k: (n, f"in repo {r}") for k, n in dec.items()})
        print(f"  {date if date[0] != '0' else 'no commits'}  {r}{'  *' if dec else ''}")
    if len(rows) > 40:
        print(f"  ... and {len(rows) - 40} more")
    print("\nCLAUDE CODE SESSIONS (by project, latest first; pass the history: path to `sessions`)")
    cutoff = datetime.datetime.now().timestamp() - 30 * 86400
    srows = []
    for h in claude_homes(a.claude_home or []):
        for p in (h / "projects").iterdir():
            files = list(p.glob("*.jsonl")) if p.is_dir() else []
            if not files:
                continue
            mt = [f.stat().st_mtime for f in files]
            srows.append((max(mt), len(files), sum(m >= cutoff for m in mt), session_cwd(p), p))
    for last, n, recent, cwd, p in sorted(srows, key=lambda r: r[0], reverse=True)[:40]:
        day = datetime.date.fromtimestamp(last).isoformat()
        print(f"  {day}  {n:>4} sessions ({recent} in 30d)  {cwd or '(project path unknown)'}\n"
              f"              history: {p}")
        c = Path(cwd) if cwd else None
        if c and c.is_dir() and not (c / ".git").exists():   # project folder outside git: look in the usual places
            for x in [c / n for n in DECISION_DIRS] + [c / "docs" / n for n in DECISION_DIRS]:
                if x.is_dir():
                    folders[x] = (sum(1 for y in x.rglob("*") if y.is_file() and y.suffix.lower() in DOC_EXT),
                                  "outside git")
    if not srows:
        print("  none found")
    print("\nDECISION / ADR / HANDOFF FOLDERS (those in a repo are already covered by `repo` on that repo)")
    for f, (n, where) in folders.items():
        print(f"  {n:>4} files  {f}  ({where})")
    if not folders:
        print("  none found")
    return 0


# ---------- repo

def wanted_repo_file(rel):
    parts, ext = rel.lower().split("/"), Path(rel).suffix.lower()
    if ext not in TEXT_EXT:
        return False
    if len(parts) == 1:
        return ext != ".txt"   # README, CLAUDE.md, AGENTS.md...; not requirements.txt
    return (parts[-1].startswith("readme.") or parts[0] in REPO_DOC_DIRS
            or any(p in DECISION_DIRS for p in parts[:-1]))


def repo_file_rank(rel):
    parts = rel.lower().split("/")
    if any(p in DECISION_DIRS for p in parts[:-1]):
        return 0
    return 1 if len(parts) == 1 else 2 if parts[-1].startswith("readme.") else 3


def cmd_repo(a):
    w = Writer(a.dry_run)
    for arg in a.paths:
        repo = Path(arg).expanduser().resolve()
        if not (repo / ".git").exists():
            w.skip(arg, "not a git repository root")
            continue
        if inside_vault(repo):
            w.skip(arg, "this is the vault itself")
            continue
        dest = RAW / "repos" / slot(repo.name, repo)
        files = sorted((f for f in git(repo, "ls-files", "-z").split("\0") if f and wanted_repo_file(f)),
                       key=lambda f: (repo_file_rank(f), f))
        if len(files) > MAX_REPO_FILES:
            w.skip(f"{repo.name}: {len(files) - MAX_REPO_FILES} doc files",
                   f"over {MAX_REPO_FILES} per repo; decisions, top-level files and READMEs were kept first")
        for f in files[:MAX_REPO_FILES]:
            src = repo / f
            if not src.is_file() or src.is_symlink() or not src.resolve().is_relative_to(repo):
                continue
            if src.stat().st_size > MAX_TEXT:
                w.skip(f"{repo.name}/{f}", "larger than 1 MB")
                continue
            text = read_text(w, src)
            if text is not None:
                w.put(dest / f, text)
        log = git(repo, "log", "-n", str(a.commits), "--date=short", "--format=%ad %h %s")
        head = (f"# Git history: {repo.name}\n\n- path: {repo}\n- branch: {git(repo, 'branch', '--show-current').strip()}\n"
                f"- remote: {git(repo, 'remote', 'get-url', 'origin').strip() or '(none)'}\n"
                f"- last {a.commits} commits\n\n```\n{log}```\n")
        w.put(dest / "git-log.md", head)
    w.report()
    return 0


# ---------- sessions

def project_dirs(arg, homes):
    p = Path(arg).expanduser()
    if p.is_dir() and p.parent.name == "projects" and any(p.glob("*.jsonl")):
        return [p]
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(p.resolve()))
    return [h / "projects" / slug for h in homes if (h / "projects" / slug).is_dir()]


def clean_user(text):
    text = NOISE.sub("", text)
    text = re.sub(r"^\[Request interrupted by user[^\]]*\]$", "", text, flags=re.M)
    return re.sub(r"</?(command-name|command-args)>", " ", text).strip()


def clip(text):
    return text if len(text) <= MAX_TURN else text[:MAX_TURN] + f"\n\n[... {len(text) - MAX_TURN} characters cut]"


def session_markdown(path):
    """Transcript JSONL -> Markdown with the user's and Claude's words only (no tool output, no subagents)."""
    turns, meta, title = [], {}, None
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            kind = d.get("type")
            if kind == "custom-title" and isinstance(d.get("customTitle"), str):
                title = d["customTitle"]
            if (kind not in ("user", "assistant") or d.get("isSidechain") or d.get("isMeta")
                    or d.get("isCompactSummary") or d.get("isVisibleInTranscriptOnly")):
                continue
            for k in ("cwd", "gitBranch", "sessionId", "timestamp"):
                if d.get(k) and k not in meta:
                    meta[k] = d[k]
            if d.get("timestamp"):
                meta["end"] = d["timestamp"]
            msg = d.get("message")
            content = msg.get("content") if isinstance(msg, dict) else None
            if isinstance(content, str):
                texts, tools = [content], []
            else:
                blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
                texts = [str(b.get("text") or "") for b in blocks if b.get("type") == "text"]
                tools = [str(b.get("name") or "?") for b in blocks if b.get("type") == "tool_use"]
            text = "\n\n".join(t for t in texts if t.strip())
            if kind == "user":
                text = clean_user(text)
            if not text and not tools:
                continue
            if turns and turns[-1][0] == kind:
                turns[-1][1].append(text)
                turns[-1][2].extend(tools)
            else:
                turns.append((kind, [text], tools))
    users = [t for t in turns if t[0] == "user"]
    if not users:
        return None, None
    first = next((x for x in users[0][1] if x), "session").splitlines()[0][:80]
    out = [f"# Session: {title or first}\n",
           f"- project: {meta.get('cwd')}", f"- session: {meta.get('sessionId')}",
           f"- branch: {meta.get('gitBranch')}", f"- started: {meta.get('timestamp')}", f"- ended: {meta.get('end')}",
           f"- turns: {len(users)} from the user, {len(turns) - len(users)} from Claude",
           "- note: tool calls and their output are omitted; long turns are cut", ""]
    for kind, texts, tools in turns:
        out.append("## User" if kind == "user" else "## Claude")
        body = clip(redact("\n\n".join(t for t in texts if t)))   # redact before cutting: a cut key escapes the patterns
        if body:
            out.append(body)
        if tools:
            counts = {t: tools.count(t) for t in dict.fromkeys(tools)}
            out.append("_tools: " + ", ".join(f"{t} x{n}" if n > 1 else t for t, n in counts.items()) + "_")
        out.append("")
    day = str(meta.get("timestamp") or "")[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = datetime.date.fromtimestamp(path.stat().st_mtime).isoformat()
    return "\n".join(out), day


def cmd_sessions(a):
    w = Writer(a.dry_run)
    homes = claude_homes(a.claude_home or [])
    now = datetime.datetime.now().timestamp()
    cutoff = now - a.days * 86400 if a.days else 0
    live = now - a.skip_recent * 60
    for arg in a.paths:
        dirs = project_dirs(arg, homes)
        if not dirs:
            w.skip(arg, "no Claude Code session history for this path (pass the history: path from discover)")
            continue
        for d in dirs:
            cwd = session_cwd(d)
            name = slot(Path(cwd).name if cwd else d.name, cwd or d)
            for f in sorted(d.glob("*.jsonl")):
                mtime = f.stat().st_mtime
                if mtime < cutoff:
                    continue
                if mtime > live:
                    w.skip(f.name, f"active in the last {a.skip_recent} min; collect it later")
                    continue
                try:
                    md, day = session_markdown(f)
                except (OSError, AttributeError, TypeError) as e:
                    w.skip(f.name, f"unreadable transcript: {e}")
                    continue
                if md is None:
                    w.skip(f.name, "no user messages")
                    continue
                w.put(RAW / "sessions" / name / f"{day}-{f.stem[:8]}.md", md)
    w.report()
    return 0


# ---------- files

def cmd_files(a):
    w = Writer(a.dry_run)
    for arg in a.paths:
        src = Path(arg).expanduser().resolve()
        if not src.exists():
            w.skip(arg, "not found")
            continue
        if inside_vault(src):
            w.skip(arg, "already inside the vault")
            continue
        base = src.parent if src.is_file() else src
        if src.is_file():
            items = [src]
        else:
            items = []
            onerror = lambda e: w.skip(e.filename, e.strerror or "unreadable")   # noqa: E731
            for root, dirs, names in os.walk(src, onerror=onerror):
                dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in SKIP_DIRS
                                 and not inside_vault(Path(root) / x))   # a folder that contains the vault
                items += [Path(root) / n for n in sorted(names)
                          if not n.startswith(".") and Path(n).suffix.lower() in DOC_EXT]
        if len(items) > MAX_FOLDER_FILES:
            w.skip(f"{src}: {len(items) - MAX_FOLDER_FILES} files", f"over {MAX_FOLDER_FILES} per folder; pass subfolders")
        dest_root = RAW / "docs" / slot(f"{base.parent.name}-{base.name}", base)
        for f in items[:MAX_FOLDER_FILES]:
            ext = f.suffix.lower()
            if f.is_symlink() or ext not in DOC_EXT:
                continue
            try:
                size = f.stat().st_size
            except OSError:
                continue
            if size > (MAX_TEXT if ext in TEXT_EXT else MAX_BINARY):
                w.skip(str(f), "too large")
                continue
            dest = dest_root / f.relative_to(base)
            if ext in TEXT_EXT:
                text = read_text(w, f)
                if text is not None:
                    w.put(dest, text)
            else:
                try:
                    w.put(dest, f.read_bytes(), text=False)
                except OSError as e:
                    w.skip(str(f), e.strerror or "unreadable")
    w.report()
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--root", action="append", help="where to look for git repos (default: $HOME, depth 3)")
    d.add_argument("--claude-home", action="append", help="extra Claude config dir to read sessions from")
    r = sub.add_parser("repo")
    r.add_argument("paths", nargs="+")
    r.add_argument("--commits", type=int, default=200)
    s = sub.add_parser("sessions")
    s.add_argument("paths", nargs="+", help="a history: path from discover, or the project's working directory")
    s.add_argument("--days", type=int, default=30, help="only sessions active in the last N days (0 = all)")
    s.add_argument("--skip-recent", type=int, default=60, metavar="MIN",
                   help="skip sessions written in the last MIN minutes, likely still running (default 60)")
    s.add_argument("--claude-home", action="append", help="extra Claude config dir (same as given to discover)")
    f = sub.add_parser("files")
    f.add_argument("paths", nargs="+")
    for p in (r, s, f):
        p.add_argument("--dry-run", action="store_true", help="count what would be written, write nothing")
    a = ap.parse_args()
    return {"discover": cmd_discover, "repo": cmd_repo, "sessions": cmd_sessions, "files": cmd_files}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
