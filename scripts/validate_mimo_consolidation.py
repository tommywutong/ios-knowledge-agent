#!/usr/bin/env python3
"""Validate MiMo same-anchor candidate consolidation outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"schema_version", "task_id", "cluster_id", "member_input_ids", "decision", "representative_input_ids", "reason", "keep_distinctions", "recommended_next_step", "confidence", "offline_only", "admission"}
FORBIDDEN = re.compile(r"(?:/Users/|/var/|/tmp/|[A-Za-z]:\\|(?:token|secret|api[_-]?key|cookie|authorization)\s*[:=]|第\s*\d+\s*[-~至]\s*\d+\s*行)", re.I)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _queue_status(text: str, task_id: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(task_id)}\s*$.*?^- status: `([^`]+)`", text)
    if not match:
        raise ValueError(f"missing status for {task_id}")
    return match.group(1)


def validate(batch: Path, task_ids: list[str] | None = None, mark_ready: bool = False) -> dict:
    manifest = json.loads((batch / "BATCH_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "mimo-candidate-consolidation/v1" or manifest.get("admission") != "hold":
        raise ValueError("invalid batch manifest")
    queue_path = batch / "TASK_QUEUE.md"
    queue = queue_path.read_text(encoding="utf-8")
    selected = [task for task in manifest["tasks"] if not task_ids or task["task_id"] in task_ids]
    if task_ids and len(selected) != len(set(task_ids)):
        raise ValueError("unknown or duplicate task ID")
    summaries = []
    for task in selected:
        inputs = _rows(batch / task["input"])
        if len(inputs) != task["input_count"] or _sha(batch / task["input"]) != task["input_sha256"]:
            raise ValueError(f"{task['task_id']}: frozen input mismatch")
        output_path = batch / task["output"]
        if not output_path.exists():
            summaries.append({"task_id": task["task_id"], "output": "missing"})
            continue
        outputs = _rows(output_path)
        if len(outputs) != len(inputs):
            raise ValueError(f"{task['task_id']}: output count mismatch")
        for source, output in zip(inputs, outputs):
            if set(output) != FIELDS or output["schema_version"] != "mimo-candidate-consolidation/v1":
                raise ValueError(f"{task['task_id']}: output schema mismatch")
            for field in ("task_id", "cluster_id", "member_input_ids"):
                if output[field] != source[field]:
                    raise ValueError(f"{task['task_id']}: {field} does not copy input")
            if output["decision"] not in {"keep_one", "keep_multiple", "hold_for_human"}:
                raise ValueError(f"{task['task_id']}: invalid decision")
            representatives = output["representative_input_ids"]
            if not isinstance(representatives, list) or any(item not in source["member_input_ids"] for item in representatives):
                raise ValueError(f"{task['task_id']}: invalid representatives")
            if output["decision"] == "keep_one" and len(representatives) != 1:
                raise ValueError(f"{task['task_id']}: keep_one needs exactly one representative")
            if output["decision"] == "keep_multiple" and len(representatives) < 2:
                raise ValueError(f"{task['task_id']}: keep_multiple needs at least two representatives")
            if output["offline_only"] is not True or output["admission"] != "hold" or output["confidence"] not in {"low", "medium", "high"}:
                raise ValueError(f"{task['task_id']}: invalid safety fields")
            if not isinstance(output["reason"], str) or not 20 <= len(output["reason"].strip()) <= 600 or FORBIDDEN.search(json.dumps(output, ensure_ascii=False)):
                raise ValueError(f"{task['task_id']}: unsafe or missing reason")
            if not isinstance(output["keep_distinctions"], list) or not isinstance(output["recommended_next_step"], str):
                raise ValueError(f"{task['task_id']}: invalid explanation fields")
        summaries.append({"task_id": task["task_id"], "output": "valid", "rows": len(outputs), "sha256": _sha(output_path)})
        if mark_ready:
            if len(selected) != 1:
                raise ValueError("--mark-ready needs exactly one task")
            queue = re.sub(rf"(?ms)(^## {re.escape(task['task_id'])}\s*$.*?^- status: )`[^`]+`", r"\1`READY_FOR_CODEX`", queue, count=1)
            queue = re.sub(rf"(?ms)(^## {re.escape(task['task_id'])}\s*$.*?^- output_sha256:) .*?$", rf"\1 {_sha(output_path)}", queue, count=1)
            queue_path.write_text(queue, encoding="utf-8")
    return {"batch_id": manifest["batch_id"], "offline_only": True, "admission": "hold", "valid_output_count": sum(item["output"] == "valid" for item in summaries), "missing_output_count": sum(item["output"] == "missing" for item in summaries), "tasks": summaries}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--task", action="append")
    parser.add_argument("--mark-ready", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.batch, args.task, args.mark_ready), ensure_ascii=False, indent=2))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"MiMo consolidation batch rejected: {exc}")
