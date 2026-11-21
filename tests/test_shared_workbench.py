import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
import runpy
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
import uuid


REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "core/skills/workbench-sessions/workbench.py"
VAULT_WRITER = REPO / "optional/vault/skill/vault-write.py"


class SharedWorkbenchTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / "state"

    def cli(self, *args, body=None, env=None, check=True):
        result = subprocess.run([sys.executable, str(CLI), "--state", str(self.state), *args],
                                input=body, encoding="utf-8", capture_output=True, env=env, check=check)
        return json.loads(result.stdout) if result.returncode == 0 else result

    def register(self, agent, name):
        native = str(uuid.uuid4())
        self.cli("attach", "feature", name, agent, native, "--cwd", str(self.root))
        return native

    def test_roundtrips_restart_routing_and_retries(self):
        for agent in ("claude", "codex", "cursor"):
            self.register(agent, agent)
            self.register(agent, agent + "-other")
        self.assertEqual(len(self.cli("sessions", "feature")), 6)
        for sender, recipient in (("claude", "codex"), ("codex", "claude"),
                                  ("cursor", "claude"), ("claude", "cursor")):
            sent, replied = str(uuid.uuid4()), str(uuid.uuid4())
            command = ("send", "feature", sender, recipient, "--id", sent)
            self.cli(*command, body="Please review")
            self.cli(*command, body="Please review")
            # Every invocation is a fresh process reading the same database.
            self.assertEqual([m["id"] for m in self.cli("inbox", "feature", recipient)], [sent])
            self.assertEqual(self.cli("inbox", "feature", recipient + "-other"), [])
            self.assertNotEqual(self.cli("ack", "feature", recipient + "-other", sent, check=False).returncode, 0)
            reply = ("reply", "feature", recipient, sent, "--id", replied)
            self.cli(*reply, body="Reviewed")
            self.cli(*reply, body="Reviewed")
            self.assertNotEqual(self.cli(*reply[:-1], str(uuid.uuid4()), body="Another", check=False).returncode, 0)
            self.assertEqual(self.cli("inbox", "feature", recipient), [])
            response, = self.cli("inbox", "feature", sender)
            self.assertEqual((response["id"], response["reply_to"], response["body"]), (replied, sent, "Reviewed"))
            self.cli("ack", "feature", sender, replied)

    @unittest.skipIf(os.name == "nt", "native command stubs use a POSIX shebang")
    def test_resume_preserves_native_id_worktree_and_mailbox_identity(self):
        commands = {"claude": ("claude", "--resume"), "codex": ("codex", "resume"),
                    "cursor": ("cursor-agent", "--resume")}
        command_dir = self.root / "bin"
        command_dir.mkdir()
        vault = self.root / "Shared Vault"
        (vault / "wiki").mkdir(parents=True)
        (vault / "CLAUDE.md").touch()
        for agent, (binary, flag) in commands.items():
            native = self.register(agent, agent)
            stub = command_dir / binary
            stub.write_text(f"#!{sys.executable}\n"
                            "import json, os, sys\n"
                            "print(json.dumps([sys.argv[1:], os.getcwd(), os.environ['WORKBENCH_TASK'], "
                            "os.environ['WORKBENCH_SESSION'], os.environ['WORKBENCH_STATE']]))\n", encoding="utf-8")
            stub.chmod(0o700)
            env = {**os.environ, "PATH": str(command_dir)}
            env.pop("WORKBENCH_STATE", None)
            actual = self.cli("resume", "feature", agent, "--vault", str(vault), env=env)
            self.assertEqual(actual, [[flag, native, "--add-dir", str(vault)], str(self.root), "feature", agent, str(self.state)])

    def test_claude_channel_wakes_only_for_the_registered_inbox(self):
        self.register("claude", "claude")
        self.register("claude", "other")
        self.register("codex", "codex")
        channel = CLI.with_name("claude-channel.py")
        with subprocess.Popen([sys.executable, str(channel), str(self.state), "feature", "claude"],
                              text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            output = Queue()

            def collect():
                for line in process.stdout:
                    output.put(json.loads(line))

            reader = Thread(target=collect, daemon=True)
            reader.start()
            try:
                handshake = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2026-07-28"}}
                print(json.dumps(handshake), file=process.stdin, flush=True)
                init = output.get(timeout=3)["result"]
                self.assertEqual(init["protocolVersion"], "2025-11-25")
                self.assertIn("claude/channel", init["capabilities"]["experimental"])
                self.assertIn("inbox feature claude", init["instructions"])
                self.cli("send", "feature", "codex", "other", "--id", str(uuid.uuid4()), body="Different session")
                pending = str(uuid.uuid4())
                self.cli("send", "feature", "codex", "claude", "--id", pending, body="Already queued")
                print(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                      file=process.stdin, flush=True)
                event = output.get(timeout=3)
                self.assertEqual(event["method"], "notifications/claude/channel")
                self.assertEqual(event["params"]["meta"]["message_id"], pending)
                self.cli("ack", "feature", "claude", pending)
                another = str(uuid.uuid4())
                self.cli("send", "feature", "codex", "claude", "--id", another, body="Next request")
                self.assertEqual(output.get(timeout=3)["params"]["meta"]["message_id"], another)
            finally:
                process.stdin.close()
                process.wait(timeout=3)
                reader.join(timeout=3)

    def test_claude_approval_probe_permission_tool_protocol(self):
        script = REPO / "tests/claude_approval_probe.py"
        for choice in ("approve", "deny"):
            root = self.root / choice
            root.mkdir()
            marker = root / "probe.txt"
            (root / "decision.json").write_text(json.dumps(choice), encoding="utf-8")
            def call(request_id, path):
                return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {
                    "name": "approve", "arguments": {"tool_name": "Write",
                    "input": {"file_path": str(path), "content": "probe"}},
                }}
            requests = [call(1, root / "unrelated.txt"), call(2, marker), call(3, marker)]
            result = subprocess.run([sys.executable, str(script), "--server", str(root), str(marker), "probe"],
                                    input="\n".join(map(json.dumps, requests)), capture_output=True, text=True, check=True)
            decisions = [json.loads(json.loads(line)["result"]["content"][0]["text"])
                         for line in result.stdout.splitlines()]
            self.assertEqual([d["behavior"] for d in decisions], ["deny", "allow" if choice == "approve" else "deny", "deny"])
            if choice == "approve":
                self.assertEqual(decisions[1]["updatedInput"], {"file_path": str(marker), "content": "probe"})
            self.assertEqual(json.loads((root / "relayed.json").read_text(encoding="utf-8")), choice)
            self.assertFalse(marker.exists())

    def test_claude_approval_probe_rejects_wrong_or_expired_input(self):
        probe = runpy.run_path(str(REPO / "tests/claude_approval_probe.py"))
        submit = probe["submit_decision"]
        with self.assertRaisesRegex(RuntimeError, "no decision was sent"):
            submit(self.root, "deny", "approve", time.monotonic() + 10)
        with self.assertRaisesRegex(RuntimeError, "approval window expired"):
            submit(self.root, "approve", "approve", time.monotonic() - 1)
        self.assertFalse((self.root / "decision.json").exists())
        submit(self.root, "deny", "deny", time.monotonic() + 10)
        self.assertEqual(json.loads((self.root / "decision.json").read_text(encoding="utf-8")), "deny")

    def test_claude_approval_probe_requires_matching_denial_and_acknowledgment(self):
        probe = runpy.run_path(str(REPO / "tests/claude_approval_probe.py"))
        verify = probe["verify_result"]
        marker = self.root / "marker"
        request = {"tool_use_id": "toolu_probe"}
        denial = {"tool_name": "Write", "tool_use_id": "toolu_probe", "tool_input": {"file_path": str(marker)}}
        result = {"is_error": False, "result": probe["DENIED_MARKER"], "permission_denials": [denial]}
        self.assertEqual(verify(result, "deny", marker, request), probe["DENIED_MARKER"])
        for change in ({"result": "Done"}, {"permission_denials": []}, {"is_error": True},
                       {"permission_denials": [{**denial, "tool_use_id": "wrong"}]}):
            with self.assertRaises(RuntimeError):
                verify({**result, **change}, "deny", marker, request)

    def test_concurrent_vault_writes_require_merging_stale_index(self):
        vault = self.root / "Vault with spaces"
        shutil.copytree(REPO / "optional/vault/scaffold", vault)
        index = vault / "wiki/index.md"
        original = index.read_text(encoding="utf-8")
        expected = hashlib.sha256(index.read_bytes()).hexdigest()

        def submit(name, version, content):
            batch = self.root / f"{name}.json"
            raw = f"raw/notes/{name}.md"
            (vault / raw).write_text(name, encoding="utf-8")
            batch.write_text(json.dumps({"edits": [
                {"path": f"wiki/sources/{name}.md", "expected_sha256": None, "text": name},
                {"path": "wiki/index.md", "expected_sha256": version, "text": content + f"\n[[{name}]]\n"},
            ], "register": [raw]}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(VAULT_WRITER), str(vault), str(batch)],
                                    capture_output=True, text=True)
            return name, result

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(submit, name, expected, original) for name in ("alpha", "beta")]
            outcomes = [future.result() for future in results]
        successes = [name for name, result in outcomes if result.returncode == 0]
        self.assertEqual(len(successes), 1)
        loser = ({"alpha", "beta"} - set(successes)).pop()
        self.assertFalse((vault / f"wiki/sources/{loser}.md").exists())
        _, retry = submit(loser, hashlib.sha256(index.read_bytes()).hexdigest(), index.read_text(encoding="utf-8"))
        self.assertEqual(retry.returncode, 0, retry.stderr)
        for name in ("alpha", "beta"):
            self.assertIn(f"[[{name}]]", index.read_text(encoding="utf-8"))
            self.assertIn(f"raw/notes/{name}.md", (vault / "manifest.tsv").read_text(encoding="utf-8"))


    def test_vault_registration_failure_restores_wiki_and_manifest(self):
        vault = self.root / "vault"
        shutil.copytree(REPO / "optional/vault/scaffold", vault)
        raw = vault / "raw/notes/source.md"
        raw.touch()
        manifest = vault / "manifest.tsv"
        original = manifest.read_bytes()
        (vault / "tools/vault.py").write_text(
            "from pathlib import Path\nPath('manifest.tsv').write_text('partial')\nraise SystemExit(1)\n",
            encoding="utf-8",
        )
        batch = self.root / "batch.json"
        batch.write_text(json.dumps({"edits": [
            {"path": "wiki/sources/new.md", "expected_sha256": None, "text": "draft"},
        ], "register": ["raw/notes/source.md"]}), encoding="utf-8")
        result = subprocess.run([sys.executable, str(VAULT_WRITER), str(vault), str(batch)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(manifest.read_bytes(), original)
        self.assertFalse((vault / "wiki/sources/new.md").exists())


if __name__ == "__main__":
    unittest.main()
