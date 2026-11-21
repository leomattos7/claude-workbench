#!/usr/bin/env python3
"""Local Workbench session registry and mailbox. Python standard library only."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    task TEXT NOT NULL,
    name TEXT NOT NULL,
    agent TEXT NOT NULL,
    native_id TEXT NOT NULL,
    cwd TEXT NOT NULL,
    UNIQUE(agent, native_id),
    PRIMARY KEY(task, name)
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    body TEXT NOT NULL,
    reply_to TEXT REFERENCES messages(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TEXT,
    FOREIGN KEY(task, sender) REFERENCES sessions(task, name),
    FOREIGN KEY(task, recipient) REFERENCES sessions(task, name)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_reply_per_message ON messages(reply_to);
CREATE INDEX IF NOT EXISTS mailbox ON messages(task, recipient, acknowledged_at);
"""


def label(value):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", value):
        raise argparse.ArgumentTypeError("expected 1–80 letters, digits, dots, underscores or hyphens")
    return value


def native_id(value):
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a native session UUID") from exc


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--state", type=Path, default=os.environ.get("WORKBENCH_STATE", Path.home() / ".local/state/workbench"))
    commands = cli.add_subparsers(dest="command", required=True)
    harness = commands.add_parser("harness", help="show the shared rules version, state and vault")
    harness.add_argument("--agent", choices=("claude", "codex", "cursor"), help="verify the installed rules for this agent")
    attach = commands.add_parser("attach", help="register an existing native session")
    attach.add_argument("task", type=label)
    attach.add_argument("session", type=label)
    attach.add_argument("agent", choices=("claude", "codex", "cursor"))
    attach.add_argument("native_id", type=native_id)
    attach.add_argument("--cwd", type=Path, default=Path.cwd())
    listing = commands.add_parser("sessions", help="list sessions registered for a task")
    listing.add_argument("task", type=label)
    for name, help_text in (
        ("send", "enqueue a message"), ("inbox", "list unacknowledged messages"),
        ("ack", "acknowledge a message"), ("reply", "reply and acknowledge atomically"),
    ):
        cmd = commands.add_parser(name, help=help_text)
        cmd.add_argument("task", type=label)
        cmd.add_argument("session", type=label)
        if name == "send":
            cmd.add_argument("recipient", type=label)
        if name in ("ack", "reply"):
            cmd.add_argument("message_id", type=native_id)
        if name in ("send", "reply"):
            cmd.add_argument("--id", type=native_id, required=True, help="reuse this UUID on retry")
    resume = commands.add_parser("resume", help="open a registered session in its native CLI")
    resume.add_argument("task", type=label)
    resume.add_argument("session", type=label)
    vault_options = resume.add_mutually_exclusive_group()
    vault_options.add_argument("--vault", type=Path, help="add a specific vault to the native workspace")
    vault_options.add_argument("--with-vault", action="store_true", help="add the configured vault to the native workspace")
    resume.add_argument("--listen", action="store_true", help="connect the Claude Code preview channel")
    return cli


def harness_status(state, agent=None):
    config = state / "harness.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{config}: expected a JSON object")
    vault = data.get("vault")
    if vault is not None and (not isinstance(vault, str) or not Path(vault).is_absolute()):
        raise ValueError(f"{config}: vault must be an absolute path")
    status = {"config": str(config), "state": str(state / "sessions.sqlite3"), "vault": vault,
              "rules_sha256": data["rules_sha256"]}
    if agent is None:
        return status
    home = Path.home()
    paths = {
        "claude": Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")) / "CLAUDE.md",
        "codex": Path(os.environ.get("CODEX_HOME", home / ".codex")) / "AGENTS.md",
        "cursor": home / ".local/share/workbench/rules/AGENTS.md",
    }
    rules_file = paths[agent]
    text = rules_file.read_text(encoding="utf-8")
    if agent != "cursor":
        blocks = re.findall(r"<!-- WORKBENCH:CORE:START(?: eof-nonl)? -->\n(.*?)<!-- WORKBENCH:CORE:END -->", text, re.S)
        if len(blocks) != 1:
            raise ValueError(f"expected one Workbench rules block in {rules_file}")
        text = blocks[0]
    digest = hashlib.sha256(text.strip("\r\n").encode("utf-8")).hexdigest()
    return {**status, "agent": agent, "rules_file": str(rules_file), "installed_rules_sha256": digest,
            "matches": digest == status["rules_sha256"]}


def session(db, task, name):
    row = db.execute("SELECT * FROM sessions WHERE task=? AND name=?", (task, name)).fetchone()
    if row is None:
        raise ValueError(f"unknown session {task}/{name}")
    return row


def attach(db, args):
    cwd = args.cwd.resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("--cwd must be a directory")
    values = (args.task, args.session, args.agent, args.native_id, str(cwd))
    db.execute("INSERT INTO sessions VALUES (?,?,?,?,?) ON CONFLICT(task,name) DO NOTHING", values)
    existing = session(db, args.task, args.session)
    if tuple(existing) != values:
        raise ValueError("session name is already bound to a different native session or checkout")
    return dict(existing)


def acknowledge(db, args):
    row = db.execute(
        "SELECT * FROM messages WHERE task=? AND recipient=? AND id=?",
        (args.task, args.session, args.message_id),
    ).fetchone()
    if row is None:
        raise ValueError("message is not in this session's inbox")
    db.execute(
        "UPDATE messages SET acknowledged_at=CURRENT_TIMESTAMP WHERE id=? AND acknowledged_at IS NULL",
        (args.message_id,),
    )
    return row


def send(db, args, body, recipient, reply_to=None):
    session(db, args.task, recipient)
    values = (args.id, args.task, args.session, recipient, body, reply_to)
    db.execute(
        "INSERT INTO messages (id,task,sender,recipient,body,reply_to) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(id) DO NOTHING", values,
    )
    row = db.execute("SELECT id,task,sender,recipient,body,reply_to FROM messages WHERE id=?", (args.id,)).fetchone()
    if tuple(row) != values:
        raise ValueError("message ID is already in use with different content or routing")
    return dict(row)


def execute(db, args, body):
    if args.command == "attach":
        return attach(db, args)
    if args.command == "sessions":
        return [dict(row) for row in db.execute("SELECT * FROM sessions WHERE task=? ORDER BY name", (args.task,))]
    current = session(db, args.task, args.session)
    if args.command == "resume":
        return dict(current)
    if args.command == "inbox":
        rows = db.execute(
            "SELECT * FROM messages WHERE task=? AND recipient=? AND acknowledged_at IS NULL ORDER BY rowid",
            (args.task, args.session),
        )
        return [dict(row) for row in rows]
    if args.command == "send":
        return send(db, args, body, args.recipient)
    original = acknowledge(db, args)
    if args.command == "reply":
        return send(db, args, body, original["sender"], original["id"])
    return {"acknowledged": original["id"]}


def resume(record, state, vault, listen):
    session_id = record["native_id"]
    commands = {
        "claude": ["claude", "--resume", session_id],
        "codex": ["codex", "resume", session_id],
        "cursor": ["cursor-agent", "--resume", session_id],
    }
    command = commands[record["agent"]]
    if record["agent"] == "cursor" and not shutil.which(command[0]):
        command[0] = "agent"
    if vault is not None:
        vault = vault.resolve(strict=True)
        if not (vault / "CLAUDE.md").is_file() or not (vault / "wiki").is_dir():
            raise ValueError("--vault must name an existing Workbench vault")
        command.extend(("--add-dir", str(vault)))
    if listen:
        if record["agent"] != "claude":
            raise ValueError("--listen currently requires a Claude Code session")
        server = Path(__file__).resolve().with_name("claude-channel.py")
        config = {"mcpServers": {"workbench-inbox": {"command": sys.executable,
                   "args": [str(server), str(state), record["task"], record["name"]]}}}
        command.extend(("--mcp-config", json.dumps(config), "--dangerously-load-development-channels",
                        "server:workbench-inbox"))
    env = dict(os.environ, WORKBENCH_TASK=record["task"], WORKBENCH_SESSION=record["name"],
               WORKBENCH_STATE=str(state))
    return subprocess.run(command, cwd=record["cwd"], env=env, check=False).returncode


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        body = None
        if args.command in ("send", "reply"):
            body = sys.stdin.read(65537)
            if not body.strip() or len(body.encode("utf-8")) > 65536:
                raise ValueError("provide a nonempty UTF-8 message of at most 64 KiB on stdin")
        args.state = args.state.resolve()
        if args.command == "harness":
            status = harness_status(args.state, args.agent)
            print(json.dumps(status, ensure_ascii=True))
            return 0 if status.get("matches", True) else 1
        old_umask = os.umask(0o077)
        try:
            args.state.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(args.state / "sessions.sqlite3", timeout=10)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA foreign_keys=ON")
                db.executescript(SCHEMA)
                with db:
                    if args.command in ("attach", "send", "reply", "ack"):
                        db.execute("BEGIN IMMEDIATE")
                    result = execute(db, args, body)
        finally:
            os.umask(old_umask)
        if args.command == "resume":
            vault = args.vault
            if args.with_vault:
                configured = harness_status(args.state)["vault"]
                if configured is None:
                    raise ValueError("the Workbench has no configured vault")
                vault = Path(configured)
            return resume(result, args.state, vault, args.listen)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, sqlite3.Error, KeyError, ValueError) as exc:
        print(f"workbench: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
