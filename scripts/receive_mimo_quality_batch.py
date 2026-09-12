#!/usr/bin/env python3
"""Fetch and validate a MiMo quality batch from its dedicated Git branch."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

if __package__:
    from scripts import mimo_handoff, validate_mimo_batch
else:  # Direct script execution keeps the scripts directory on sys.path.
    import mimo_handoff
    import validate_mimo_batch


ROOT = Path(__file__).resolve().parents[1]


def receive_batch(
    *,
    branch: str,
    trusted_manifest: Path,
    checkout_dir: Path,
    remote: str = "origin",
    require_complete: bool = False,
    root: Path = ROOT,
) -> dict:
    """Receive an untrusted batch and validate it in an isolated worktree."""
    handoff = mimo_handoff.fetch_branch(
        branch,
        trusted_manifest_path=trusted_manifest,
        remote=remote,
        checkout_dir=checkout_dir,
        root=root,
    )
    worktree = Path(handoff["checkout_dir"])
    complete = bool(handoff["tasks"]) and all(
        task["status"] in {"READY_FOR_CODEX", "DONE"}
        for task in handoff["tasks"]
    )
    validation = validate_mimo_batch.validate_batch(
        worktree / handoff["pilot_dir"],
        root=worktree,
        require_complete=require_complete or complete,
    )
    return {"handoff": handoff, "complete": complete, "validation": validation}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--trusted-manifest", required=True, type=Path)
    parser.add_argument("--checkout-dir", required=True, type=Path)
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = receive_batch(
            branch=args.branch,
            trusted_manifest=args.trusted_manifest,
            checkout_dir=args.checkout_dir,
            remote=args.remote,
            require_complete=args.require_complete,
        )
    except (mimo_handoff.HandoffError, validate_mimo_batch.BatchValidationError, OSError) as exc:
        print(f"MiMo quality batch rejected: {exc}", file=os.sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
