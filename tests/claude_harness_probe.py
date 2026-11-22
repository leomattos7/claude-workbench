#!/usr/bin/env python3
"""Live A1.5 and A1.6 probes: a programmatic Claude turn against the INSTALLED harness.

Run after install.sh. It uses the real Claude config but only disposable directories:
a temporary project, and a local bare git repository as the push target.
A1.5: the Workbench SessionStart hook injects a handoff title the agent could not otherwise know.
A1.6: the installed `ask` rule stops a `git push` that a command-line `allow` rule would otherwise let through,
      so the push is denied, recorded, and never reaches the remote.
A probe that cannot attribute its result to the installed harness reports INCONCLUSIVE (exit 2), never PASS.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import uuid


class Inconclusive(Exception):
    pass


def run_claude(executable, cwd, prompt, tools, timeout, settings=None):
    command = [executable, "-p", "--permission-mode", "default", "--tools", tools, "--strict-mcp-config",
               "--output-format", "json", "--no-session-persistence"]
    if settings:
        command += ["--settings", json.dumps(settings)]
    done = subprocess.run(command, cwd=cwd, input=prompt, capture_output=True, text=True, timeout=timeout)
    try:
        turn = json.loads(done.stdout)
    except ValueError:
        raise RuntimeError(f"no JSON result ({done.returncode}): {done.stderr.strip()[:300]}")
    if not isinstance(turn, dict) or turn.get("is_error") is not False:
        raise RuntimeError(f"the turn ended in error: {str(turn.get('result'))[:300]}")
    return turn


def hook_probe(executable, timeout):
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    try:
        installed = "hooks/workbench/session-start-handoffs.sh" in (config / "settings.json").read_text(encoding="utf-8")
    except OSError:
        installed = False
    if not installed:
        raise RuntimeError(f"{config}/settings.json does not register the Workbench SessionStart hook; run install.sh first")
    with TemporaryDirectory(prefix="workbench-hook-") as temporary:
        project = Path(temporary).resolve()
        handoffs = project / "docs" / "handoffs"
        handoffs.mkdir(parents=True)
        nonce = f"WORKBENCH_HOOK_{uuid.uuid4().hex}"
        (handoffs / "2026-01-01-1200-probe.md").write_text(f"# {nonce}\n", encoding="utf-8")
        prompt = ("Your session context may contain a line starting with [HANDOFFS] and a list of handoffs. "
                  "Reply with that line and the exact title of the handoff in the list, or NONE if there is no "
                  "such list. Use no tools.")
        turn = run_claude(executable, project, prompt, "", timeout)
        text = str(turn.get("result"))
        if turn.get("num_turns") != 1:
            raise Inconclusive(f"the agent used tools (num_turns={turn.get('num_turns')}); the nonce may not come from the hook")
        if nonce not in text:
            raise RuntimeError("the SessionStart hook did not inject the disposable handoff")
        if f"3 most recent in {handoffs}" not in text:
            raise Inconclusive("the nonce arrived without the Workbench hook's own header; another hook may have produced it")
        print("PASS A1.5: the installed Workbench SessionStart hook ran and its output reached the agent", flush=True)


def push_probe(executable, timeout):
    quiet = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    with TemporaryDirectory(prefix="workbench-push-") as temporary:
        root = Path(temporary).resolve()
        remote, work = root / "remote.git", root / "work"

        def setup(*command):
            subprocess.run(command, check=True, capture_output=True, env=quiet, timeout=30)

        setup("git", "init", "--bare", str(remote))
        setup("git", "init", str(work))
        git = ["git", "-C", str(work), "-c", "user.name=probe", "-c", "user.email=probe@example.invalid"]
        (work / "file.txt").write_text("probe\n", encoding="utf-8")
        setup(*git, "add", "file.txt")
        setup(*git, "commit", "-m", "probe")
        setup(*git, "remote", "add", "origin", str(remote))
        prompt = "Publish this repository's current commit: push HEAD to origin."
        # The command-line allow rule would let the push through. Only the installed ask rule can stop it.
        override = {"permissions": {"allow": ["Bash(git push:*)"]}}
        turn = run_claude(executable, work, prompt, "Bash", timeout, override)
        refs = subprocess.run(["git", "-C", str(remote), "for-each-ref"], check=True, capture_output=True,
                              text=True, env=quiet, timeout=30).stdout
        if refs.strip():
            raise RuntimeError(f"the push reached the remote without a human approval: {refs.strip()}")
        denied = [d for d in turn.get("permission_denials") or []
                  if isinstance(d, dict) and re.search(r"\bgit\b.*\bpush\b", json.dumps(d.get("tool_input", "")))]
        if not denied:
            raise Inconclusive("the remote is empty but no git push denial was recorded; the agent may simply not have tried")
        print(f"Agent final text: {str(turn.get('result'))[:300]!r}", flush=True)
        print("PASS A1.6: the installed ask rule denied the push despite an allow rule; the remote stayed empty",
              flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    status = 0
    for probe in (hook_probe, push_probe):
        try:
            probe(args.claude, args.timeout)
        except Inconclusive as exc:
            print(f"INCONCLUSIVE {probe.__name__}: {exc}", file=sys.stderr)
            status = max(status, 2)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print(f"FAIL {probe.__name__}: {exc}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
