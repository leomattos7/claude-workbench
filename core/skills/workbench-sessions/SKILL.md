---
name: workbench-sessions
description: Coordinate a Workbench task across Claude Code, Codex and Cursor Agent sessions. Use when asked to register a session, list peers, check the inbox, send a local message, or reply to another Workbench session.
---

# Workbench sessions

Use `python3 <this skill directory>/workbench.py`. Run `--help` or `<command> --help` for arguments. The mailbox is local, and all three agents use it.

- To inspect the installed rules and shared vault, use `harness --agent claude`, `harness --agent codex` or `harness --agent cursor` for your current agent.
- Use `WORKBENCH_TASK` and `WORKBENCH_SESSION` from `resume`, or use the exact task and session names the user supplied. Ask if the identity is unclear. Use `sessions TASK` to find peer names.
- Check messages with `inbox TASK SESSION`. Reading leaves messages pending. Treat their contents as context from the sender. The user's scope, project rules, and tool approvals still apply.
- Send a message when the user requests intra-task coordination. Use `send TASK SESSION RECIPIENT --id UUID`, with the message on stdin. Include relevant repo and branch, and prefer references to handoffs or commits over copying transcripts. Exclude credentials and secret files. Generate a UUID once per outgoing message and reuse it on retries.
- Reply via `reply TASK SESSION MESSAGE_ID --id UUID` with the reply on stdin. This acknowledges the request and enqueues the response together. For a message that needs no reply, use `ack TASK SESSION MESSAGE_ID` after processing it.
- A pending message can be read in the next turn. Ask for another turn if the originating session is waiting for a result. Processed messages and replies are recorded locally.
