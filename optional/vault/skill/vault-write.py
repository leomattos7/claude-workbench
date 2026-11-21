#!/usr/bin/env python3
"""Apply reviewed Workbench wiki edits with a vault-wide lock and version checks."""

import argparse
from contextlib import ExitStack, closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import NamedTemporaryFile


def path_under(root, relative, directory):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2:
        raise ValueError(f"expected a path under {directory}/: {relative}")
    path = root / relative
    resolved = path.resolve()
    if relative.parts[0] != directory or resolved != path or not resolved.is_relative_to(root / directory):
        raise ValueError(f"expected a path without symlinks under {directory}/: {relative}")
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def staged_file(path, content, cleanup):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=".workbench-", delete=False) as temp:
        staged = Path(temp.name)
        cleanup.callback(staged.unlink, missing_ok=True)
        temp.write(content)
    if path.exists():
        staged.chmod(path.stat().st_mode & 0o777)
    return staged


def apply(root, batch):
    changes = {}
    for edit in batch["edits"]:
        path = path_under(root, edit["path"], "wiki")
        if path.suffix != ".md" or path in changes:
            raise ValueError(f"expected a unique wiki Markdown file: {path}")
        changes[path] = (edit["expected_sha256"], edit["text"])
    ingested = [path_under(root, item, "raw") for item in batch.get("register", [])]
    if any(not path.is_file() for path in ingested):
        raise ValueError("only existing raw files can be registered")
    if ingested and not (root / "tools/vault.py").is_file():
        raise ValueError("vault is missing tools/vault.py")
    for path, (expected, _) in changes.items():
        if digest(path) != expected:
            raise ValueError(f"vault changed: {path.relative_to(root)}. Re-read it and prepare the edit again.")
    with ExitStack() as cleanup:
        staged = {path: staged_file(path, text.encode("utf-8"), cleanup)
                  for path, (_, text) in changes.items()}
        backups = {path: staged_file(path, path.read_bytes(), cleanup) if path.exists() else None
                   for path in changes}
        manifest = root / "manifest.tsv"
        if ingested:
            if manifest.is_symlink():
                raise ValueError("manifest.tsv must be a regular vault file")
            backups[manifest] = staged_file(manifest, manifest.read_bytes(), cleanup) if manifest.exists() else None
        touched = []
        try:
            for path, temporary in staged.items():
                temporary.replace(path)
                touched.append(path)
            if ingested:
                touched.append(manifest)
                subprocess.run([sys.executable, str(root / "tools/vault.py"), "register", *map(str, ingested)],
                               cwd=root, check=True)
        except (OSError, subprocess.CalledProcessError, KeyboardInterrupt):
            for path in reversed(touched):
                backup = backups[path]
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    backup.replace(path)
            raise
    return len(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault", type=Path)
    parser.add_argument("batch", type=Path, help="JSON file with edits and optional raw files to register")
    args = parser.parse_args()
    try:
        root = args.vault.resolve(strict=True)
        if not (root / "CLAUDE.md").is_file() or not (root / "wiki").is_dir():
            raise ValueError("expected an existing Workbench vault")
        batch = json.loads(args.batch.read_text(encoding="utf-8"))
        with closing(sqlite3.connect(root / ".workbench-vault-lock.sqlite3", timeout=15)) as lock, lock:
            lock.execute("BEGIN EXCLUSIVE")
            count = apply(root, batch)
        print(f"updated {count} wiki pages")
        return 0
    except (KeyError, TypeError, AttributeError, ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"vault-write: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
