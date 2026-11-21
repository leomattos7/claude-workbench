#!/usr/bin/env python3
"""Live A2.1 probe for Claude Code's approval host using disposable files."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import uuid

SERVER = "workbench_approval_probe"
TOOL = "approve"


def save(path, data):
    staged = path.with_suffix(".new")
    staged.write_text(json.dumps(data), encoding="utf-8")
    staged.replace(path)


def permission(arguments, root, marker, payload):
    denied = {"behavior": "deny", "message": "The probe only allows one confirmed write to its marker file."}
    requested = arguments.get("input")
    if (arguments.get("tool_name") != "Write" or not isinstance(requested, dict)
            or requested.get("file_path") != str(marker) or requested.get("content") != payload
            or (root / "request.json").exists()):
        return denied
    save(root / "request.json", {"tool": "Write", "path": str(marker)})
    deadline = time.monotonic() + 100
    decision = root / "decision.json"
    while time.monotonic() < deadline:
        if decision.is_file():
            choice = json.loads(decision.read_text(encoding="utf-8"))
            save(root / "relayed.json", choice)
            if choice == "approve":
                return {"behavior": "allow", "updatedInput": requested}
            return {"behavior": "deny", "message": "The human declined the probe write. Do not retry."}
        time.sleep(0.1)
    return {"behavior": "deny", "message": "The probe timed out waiting for a human decision."}


def serve(root, marker, payload):
    for line in sys.stdin:
        request = json.loads(line)
        if "id" not in request:
            continue
        method = request.get("method")
        params = request.get("params", {})
        response = {"jsonrpc": "2.0", "id": request["id"]}
        if method == "initialize":
            response["result"] = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                                  "serverInfo": {"name": SERVER, "version": "1.0.0"}}
        elif method == "ping":
            response["result"] = {}
        elif method == "tools/list":
            response["result"] = {"tools": [{"name": TOOL, "description": "Human approval for the disposable probe write",
                                             "inputSchema": {"type": "object"}}]}
        elif method == "tools/call" and params.get("name") == TOOL:
            decision = permission(params.get("arguments", {}), root, marker, payload)
            response["result"] = {"content": [{"type": "text", "text": json.dumps(decision)}]}
        else:
            response["error"] = {"code": -32601, "message": "Method not found"}
        print(json.dumps(response), flush=True)
    return 0


def probe(executable, required, timeout):
    with TemporaryDirectory(prefix="workbench-approval-") as temporary:
        root = Path(temporary).resolve()
        workspace = root / "workspace"
        workspace.mkdir()
        marker = workspace / "approval-marker.txt"
        payload = f"WORKBENCH_APPROVAL_{uuid.uuid4().hex}"
        config = {"mcpServers": {SERVER: {"command": sys.executable, "args": [
            str(Path(__file__).resolve()), "--server", str(root), str(marker), payload,
        ]}}}
        settings = json.dumps({"permissions": {"ask": ["Write"]}})
        prompt = (f"This is an approval test in a disposable local workspace. Use the Write tool exactly once "
                  f"to create {marker} with exactly this text, without a trailing newline: {payload}. "
                  "If the tool is denied, acknowledge the denial and end the turn. Use no other tools.")
        command = [executable, "-p", "--tools", "Write", "--output-format", "json", "--no-session-persistence",
                   "--settings", settings, "--strict-mcp-config", "--mcp-config", json.dumps(config),
                   "--permission-prompt-tool", f"mcp__{SERVER}__{TOOL}"]
        with (root / "stdout").open("w", encoding="utf-8") as output, (root / "stderr").open("w", encoding="utf-8") as errors:
            process = subprocess.Popen(command, cwd=workspace, stdin=subprocess.PIPE, stdout=output,
                                       stderr=errors, text=True)
            try:
                process.stdin.write(prompt)
                process.stdin.close()
                deadline = time.monotonic() + timeout
                while process.poll() is None and not (root / "request.json").exists():
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Claude did not request permission before the deadline")
                    time.sleep(0.1)
                if not (root / "request.json").is_file():
                    details = (root / "stderr").read_text(encoding="utf-8")
                    try:
                        result = json.loads((root / "stdout").read_text(encoding="utf-8"))
                        if result.get("is_error"):
                            details += str(result.get("result", ""))
                    except (ValueError, AttributeError):
                        pass
                    raise RuntimeError(f"Claude exited before requesting permission ({process.returncode}): {details.strip()[:500]}")
                if marker.exists() or process.poll() is not None:
                    raise RuntimeError("Claude did not wait for a decision with the marker absent")
                print(f"Waiting for approval to write {marker}", flush=True)
                print("The marker does not exist. The probe expects a human decision.", flush=True)
                choice = input(f"Type {required} to exercise this case: ").strip().lower()
                save(root / "decision.json", choice if choice == "approve" else "deny")
                if choice != required:
                    raise RuntimeError(f"expected the decision {required!r}")
                if process.wait(timeout=timeout):
                    raise RuntimeError(f"Claude failed after the decision ({process.returncode})")
                relayed = root / "relayed.json"
                if not relayed.is_file() or json.loads(relayed.read_text(encoding="utf-8")) != required:
                    raise RuntimeError("The approval host did not relay the human decision")
                if required == "approve" and (not marker.is_file() or marker.read_text(encoding="utf-8") != payload):
                    raise RuntimeError("Claude did not write the exact marker after approval")
                if required == "deny" and marker.exists():
                    raise RuntimeError("Claude wrote the marker after denial")
                print(f"PASS {required}: expected file effect verified", flush=True)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


def main():
    if sys.argv[1:2] == ["--server"]:
        root, marker, payload = sys.argv[2:]
        return serve(Path(root), Path(marker), payload)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", default="claude")
    parser.add_argument("--timeout", type=int, default=60, help="seconds to wait for Claude at each step")
    args = parser.parse_args()
    try:
        for choice in ("approve", "deny"):
            probe(args.claude, choice, args.timeout)
    except (EOFError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
