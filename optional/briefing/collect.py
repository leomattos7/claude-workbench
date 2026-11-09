#!/usr/bin/env python3
"""Collect facts for the morning briefing and print them as markdown.

Usage: python3 -I collect.py [--notes FILE] [--date YYYY-MM-DD] REPO [REPO ...]
"""
import argparse
import datetime as dt
import glob
import os
import subprocess


def previous_workday(today):
    back = {0: 3, 6: 2}.get(today.weekday(), 1)  # Mon -> Fri, Sun -> Fri, else yesterday
    return today - dt.timedelta(days=back)


def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def handoffs(repo, limit=3):
    files = sorted(glob.glob(os.path.join(repo, "docs", "handoffs", "*.md")),
                   key=os.path.getmtime, reverse=True)[:limit]
    out = []
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            title = next((l.strip().lstrip("#").strip() for l in fh if l.strip()), "(empty)")
        mtime = dt.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        out.append(f"- {title} ({os.path.basename(f)}, {mtime})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("repos", nargs="*")
    a = ap.parse_args()

    today = dt.date.fromisoformat(a.date)
    since = previous_workday(today)
    print(f"# Facts for {today} ({today:%A})\n\nCommit window: since {since} 00:00.\n")

    for path in a.repos:
        repo = os.path.expanduser(path)
        print(f"## {os.path.basename(repo.rstrip('/')) or repo}")
        if not git(repo, "rev-parse", "--git-dir"):
            print("Not a git repository or not readable.\n")
            continue
        print(f"- Branch: {git(repo, 'branch', '--show-current') or '(detached)'}")
        changes = git(repo, "status", "--porcelain").splitlines()
        print(f"- Uncommitted changes: {len(changes)}")
        log = git(repo, "log", "--all", "--no-merges", f"--since={since} 00:00",
                  "--date=format:%a %H:%M", "--format=%h %ad %s")
        print("- Commits:" if log else "- Commits: none")
        for line in log.splitlines():
            print(f"  - {line}")
        hs = handoffs(repo)
        print("- Latest handoffs:" if hs else "- Latest handoffs: none")
        for h in hs:
            print(f"  {h}")
        print()

    if a.notes and os.path.isfile(os.path.expanduser(a.notes)):
        with open(os.path.expanduser(a.notes), encoding="utf-8", errors="replace") as fh:
            print(f"## Notes\n\n{fh.read(4000).strip()}\n")


if __name__ == "__main__":
    main()
