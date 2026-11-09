# Security policy

workbench installs hooks, skills and settings into your Claude Code config, so a bad change here runs on
the machines of everyone who installs it. Reports are welcome.

## Reporting a vulnerability

Use **Security → Report a vulnerability** on this repository (private vulnerability reporting).
Please do not open a public issue for security problems.

In scope: the installer and uninstaller, hooks, settings fragments, mods, skills that could steer an agent
into unsafe actions, and the CI workflows. Expect a first reply within a week; this is a one-person project.

## What CI checks on every change

- `scripts/check-injection.py`: invisible/bidi Unicode, piped remote execution, network calls in hooks,
  settings fragments that loosen permissions or point hooks elsewhere.
- gitleaks, zizmor and dependency review.
- Green checks prove nothing for a PR that touches `.github/` or `scripts/check-*`: on `pull_request` GitHub
  runs the workflow file from the PR itself, so such a PR can rewrite the check that judges it. Those PRs get
  a line-by-line read before approval.
- Releases ship a `SHA256SUMS` file and a build provenance attestation:
  `gh attestation verify claude-workbench-<tag>.tar.gz --repo leomattos7/claude-workbench`.
