"""Compare harness configuration from the three installed CLI entry points."""

import json
from pathlib import Path
import subprocess
import sys

home = Path.home()
roots = {"claude": home / ".claude/skills", "codex": home / ".agents/skills", "cursor": home / ".cursor/skills"}
expected_vault = str(Path(sys.argv[1]).resolve())
reports = []
for agent, root in roots.items():
    script = root / "workbench-sessions/workbench.py"
    report = json.loads(subprocess.check_output([sys.executable, str(script), "harness", "--agent", agent]))
    assert report["vault"] == expected_vault, report
    assert report["matches"], report
    reports.append(report)
assert len({item["rules_sha256"] for item in reports}) == 1, reports
assert len({item["state"] for item in reports}) == 1, reports
for item in reports:
    print(item["agent"], item["rules_sha256"], item["vault"])
