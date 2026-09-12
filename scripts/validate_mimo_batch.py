#!/usr/bin/env python3
"""Validate an offline MiMo quality batch and its per-task JSONL outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_SCHEMA = "mimo-quality-batch/v1"
INPUT_SCHEMA = "mimo-quality-input/v1"
OUTPUT_SCHEMA = "mimo-quality-output/v1"
TASK_KINDS = {
    "data_cleaning_and_dedupe",
    "query_variant_rewrite",
    "evidence_boundary_triage",
}
QUALITY_ACTIONS = {
    "keep",
    "rewrite",
    "remove_duplicate",
    "remove_unnatural",
    "hold_for_human",
}
VARIANT_TYPES = {
    "colloquial",
    "concise",
    "english_chinese",
    "abbreviation",
    "symbol",
    "error_tolerant",
}
EVIDENCE_SCOPES = {"supported", "partial", "mismatch", "insufficient_excerpt"}
RECOMMENDED_ACTIONS = {
    "human_review",
    "rewrite_then_human_review",
    "dedupe_then_human_review",
    "source_check_then_review",
    "remove_candidate",
}
CONFIDENCE = {"low", "medium", "high"}
TASK_STATES = {"READY_FOR_MIMO", "READY_FOR_CODEX", "DONE", "NEEDS_REWRITE", "BLOCKED"}
GENERIC_REWRITE = re.compile(
    r"根据你的资料|结合资料|资料里的内容|在你的资料里|给出出处|出处行号|"
    r"解释一下这个概念|我在面试里被问到"
)
FORBIDDEN_OUTPUT = re.compile(
    r"(?:/Users/|/var/|/tmp/|[A-Za-z]:\\|"
    r"(?:api[_-]?key|authorization|bearer|cookie|token|secret)\s*[:=]|"
    r"第\s*\d+\s*[-~至]\s*\d+\s*行)",
    re.I,
)
SHA256 = re.compile(r"[0-9a-f]{64}")
TASK_ID = re.compile(r"task-[0-9]{3}")

MANIFEST_FIELDS = {
    "schema_version",
    "batch_id",
    "offline_only",
    "admission",
    "candidate_filter",
    "input_count",
    "excluded_input_count",
    "excluded_inputs_file",
    "excluded_inputs_sha256",
    "task_count",
    "chunk_size",
    "source_assets",
    "review_reference_assets",
    "tasks",
}
TASK_FIELDS = {
    "task_id",
    "task_kind",
    "input",
    "input_count",
    "input_sha256",
    "output",
}
INPUT_FIELDS = {
    "schema_version",
    "task_id",
    "task_kind",
    "input_id",
    "source_candidate_id",
    "source_asset_path",
    "source_asset_line",
    "original_question_sha256",
    "original_question",
    "original_aliases",
    "candidate_topic",
    "candidate_category",
    "candidate_difficulty",
    "candidate_claimed_mode",
    "title_fragment",
    "template_flags",
    "evidence",
    "duplicate_candidate_ids",
    "prior_review_refs",
    "review_contract",
}
EVIDENCE_FIELDS = {
    "source_origin",
    "evidence_type",
    "range_sha256",
    "excerpt_available",
}
OUTPUT_FIELDS = {
    "schema_version",
    "task_id",
    "task_kind",
    "input_id",
    "source_candidate_id",
    "original_question_sha256",
    "quality_action",
    "quality_reason",
    "rewrite_question",
    "duplicate_of_input_ids",
    "query_variants",
    "evidence_scope",
    "scope_reason",
    "unsupported_request_parts",
    "recommended_action",
    "confidence",
    "admission",
    "offline_only",
}


class BatchValidationError(ValueError):
    """Raised when an offline batch violates its frozen contract."""


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_relative(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BatchValidationError(f"{field} must be a repository-relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("~"):
        raise BatchValidationError(f"{field} must be a repository-relative path")
    return path.as_posix()


def _batch_relative(value: object, *, field: str) -> str:
    relative = _safe_relative(value, field=field)
    if relative.startswith("data/glm/"):
        raise BatchValidationError(f"{field} must be relative to the batch directory")
    return relative


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BatchValidationError(f"missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise BatchValidationError(f"{path}: invalid JSON ({exc.msg})") from exc
    if not isinstance(value, dict):
        raise BatchValidationError(f"{path} must contain a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise BatchValidationError(f"missing {path}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise BatchValidationError(f"{path}:{line_number}: blank JSONL line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BatchValidationError(
                f"{path}:{line_number}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(row, dict):
            raise BatchValidationError(f"{path}:{line_number}: row must be an object")
        rows.append(row)
    return rows


def _exact_fields(row: dict[str, Any], expected: set[str], context: str) -> None:
    missing = expected - set(row)
    extra = set(row) - expected
    if missing or extra:
        raise BatchValidationError(
            f"{context}: fields mismatch (missing={sorted(missing)}, extra={sorted(extra)})"
        )


def _queue_sections(text: str) -> dict[str, str]:
    pieces = re.split(r"(?m)^## (task-[0-9]{3})\s*$", text)
    sections: dict[str, str] = {}
    for index in range(1, len(pieces), 2):
        task_id = pieces[index]
        if task_id in sections:
            raise BatchValidationError(f"duplicate queue task: {task_id}")
        sections[task_id] = pieces[index + 1]
    return sections


def _queue_value(section: str, name: str, *, required: bool = True) -> str:
    # Do not let whitespace consume the following queue line when a value is empty.
    matches = re.findall(rf"(?m)^- {re.escape(name)}:[ \t]*`?([^`\n]*)`?[ \t]*$", section)
    if len(matches) != 1:
        if not required and not matches:
            return ""
        raise BatchValidationError(f"queue must contain exactly one {name} field")
    return matches[0].strip()


def _validate_manifest(batch_dir: Path, root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest = _load_object(batch_dir / "BATCH_MANIFEST.json")
    _exact_fields(manifest, MANIFEST_FIELDS, "BATCH_MANIFEST.json")
    if manifest["schema_version"] != BATCH_SCHEMA:
        raise BatchValidationError("unsupported batch schema")
    if manifest["batch_id"] != batch_dir.name:
        raise BatchValidationError("batch_id must match the batch directory")
    if manifest["offline_only"] is not True or manifest["admission"] != "hold":
        raise BatchValidationError("batch must remain offline_only with admission=hold")
    excluded_file = _batch_relative(manifest["excluded_inputs_file"], field="excluded_inputs_file")
    if excluded_file != "EXCLUDED_INPUTS.jsonl":
        raise BatchValidationError("excluded_inputs_file must be EXCLUDED_INPUTS.jsonl")
    if not isinstance(manifest["excluded_input_count"], int) or manifest["excluded_input_count"] < 0:
        raise BatchValidationError("excluded_input_count must be a non-negative integer")
    if not SHA256.fullmatch(str(manifest["excluded_inputs_sha256"])):
        raise BatchValidationError("invalid excluded_inputs_sha256")
    excluded_rows = _load_jsonl(batch_dir / excluded_file)
    if len(excluded_rows) != manifest["excluded_input_count"]:
        raise BatchValidationError("excluded input count mismatch")
    if _sha_file(batch_dir / excluded_file) != manifest["excluded_inputs_sha256"]:
        raise BatchValidationError("excluded input SHA mismatch")
    excluded_ids: set[str] = set()
    for index, row in enumerate(excluded_rows, 1):
        _exact_fields(
            row,
            {"source_candidate_id", "source_asset_path", "source_asset_line", "original_question_sha256", "reason"},
            f"excluded input line {index}",
        )
        if not re.fullmatch(r"eval-[0-9]{6}", str(row["source_candidate_id"])):
            raise BatchValidationError(f"excluded input line {index}: invalid candidate ID")
        if row["source_candidate_id"] in excluded_ids:
            raise BatchValidationError(f"excluded input line {index}: duplicate candidate ID")
        excluded_ids.add(row["source_candidate_id"])
        _safe_relative(row["source_asset_path"], field=f"excluded input line {index}.source_asset_path")
        if not isinstance(row["source_asset_line"], int) or row["source_asset_line"] < 1:
            raise BatchValidationError(f"excluded input line {index}: invalid source asset line")
        if not SHA256.fullmatch(str(row["original_question_sha256"])):
            raise BatchValidationError(f"excluded input line {index}: invalid question SHA")
        if not isinstance(row["reason"], str) or not row["reason"].strip():
            raise BatchValidationError(f"excluded input line {index}: missing reason")
    if not isinstance(manifest["chunk_size"], int) or not 40 <= manifest["chunk_size"] <= 80:
        raise BatchValidationError("chunk_size must be between 40 and 80")
    tasks = manifest["tasks"]
    if not isinstance(tasks, list) or not 20 <= len(tasks) <= 40:
        raise BatchValidationError("batch must contain 20-40 resumable tasks")
    if manifest["task_count"] != len(tasks):
        raise BatchValidationError("task_count mismatch")
    expected_task_ids = [f"task-{index:03d}" for index in range(1, len(tasks) + 1)]
    actual_task_ids: list[str] = []
    kinds: set[str] = set()
    total_inputs = 0
    for index, task in enumerate(tasks, 1):
        if not isinstance(task, dict):
            raise BatchValidationError(f"task {index} must be an object")
        _exact_fields(task, TASK_FIELDS, f"task {index}")
        task_id = task["task_id"]
        actual_task_ids.append(task_id)
        if task_id != expected_task_ids[index - 1]:
            raise BatchValidationError("task IDs must be complete and ordered")
        if task["task_kind"] not in TASK_KINDS:
            raise BatchValidationError(f"{task_id}: invalid task_kind")
        kinds.add(task["task_kind"])
        input_name = _batch_relative(task["input"], field=f"{task_id}.input")
        output_name = _batch_relative(task["output"], field=f"{task_id}.output")
        if input_name != f"inputs/{task_id}.jsonl":
            raise BatchValidationError(f"{task_id}: unexpected input path")
        if output_name != f"outputs/{task_id}.jsonl":
            raise BatchValidationError(f"{task_id}: unexpected output path")
        if not isinstance(task["input_count"], int) or not 1 <= task["input_count"] <= 80:
            raise BatchValidationError(f"{task_id}: invalid input_count")
        total_inputs += task["input_count"]
        input_path = batch_dir / input_name
        if not input_path.is_file() or _sha_file(input_path) != task["input_sha256"]:
            raise BatchValidationError(f"{task_id}: input SHA mismatch")
    if actual_task_ids != expected_task_ids or kinds != TASK_KINDS:
        raise BatchValidationError("batch must contain all task kinds")
    if manifest["input_count"] != total_inputs:
        raise BatchValidationError("input_count mismatch")

    for field in ("source_assets", "review_reference_assets"):
        assets = manifest[field]
        if not isinstance(assets, list):
            raise BatchValidationError(f"{field} must be an array")
        for asset in assets:
            if not isinstance(asset, dict) or set(asset) != {"path", "sha256"}:
                raise BatchValidationError(f"{field} entry must contain path and sha256")
            relative = _safe_relative(asset["path"], field=f"{field}.path")
            if not relative.startswith("data/glm/"):
                raise BatchValidationError(f"{field}.path must be under data/glm/")
            path = root / relative
            if not path.is_file() or _sha_file(path) != asset["sha256"]:
                raise BatchValidationError(f"{field} SHA mismatch: {relative}")

    queue_path = batch_dir / "TASK_QUEUE.md"
    try:
        queue_text = queue_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BatchValidationError(f"missing {queue_path}") from exc
    sections = _queue_sections(queue_text)
    if list(sections) != expected_task_ids:
        raise BatchValidationError("queue task IDs differ from batch manifest")
    statuses: dict[str, str] = {}
    batch_relative = batch_dir.resolve().relative_to(root.resolve()).as_posix()
    for task, task_id in zip(tasks, expected_task_ids):
        section = sections[task_id]
        status = _queue_value(section, "status")
        if status not in TASK_STATES:
            raise BatchValidationError(f"{task_id}: invalid status {status!r}")
        statuses[task_id] = status
        if _queue_value(section, "kind") != task["task_kind"]:
            raise BatchValidationError(f"{task_id}: queue task_kind mismatch")
        if _queue_value(section, "input") != f"{batch_relative}/{task['input']}":
            raise BatchValidationError(f"{task_id}: queue input path mismatch")
        if _queue_value(section, "output") != task["output"]:
            raise BatchValidationError(f"{task_id}: queue output path mismatch")
        if _queue_value(section, "input_count") != str(task["input_count"]):
            raise BatchValidationError(f"{task_id}: queue input_count mismatch")
        declared_sha = _queue_value(section, "output_sha256", required=False)
        if declared_sha and not SHA256.fullmatch(declared_sha):
            raise BatchValidationError(f"{task_id}: invalid output_sha256")
    return manifest, statuses


def _validate_input_row(row: dict[str, Any], task: dict[str, Any], line: int) -> None:
    context = f"{task['task_id']} input line {line}"
    _exact_fields(row, INPUT_FIELDS, context)
    if row["schema_version"] != INPUT_SCHEMA:
        raise BatchValidationError(f"{context}: wrong schema_version")
    if row["task_id"] != task["task_id"] or row["task_kind"] != task["task_kind"]:
        raise BatchValidationError(f"{context}: task identity mismatch")
    if not re.fullmatch(r"mqi-eval-[0-9]{6}", str(row["input_id"])):
        raise BatchValidationError(f"{context}: invalid input_id")
    if not re.fullmatch(r"eval-[0-9]{6}", str(row["source_candidate_id"])):
        raise BatchValidationError(f"{context}: invalid source_candidate_id")
    if row["input_id"] != f"mqi-{row['source_candidate_id']}":
        raise BatchValidationError(f"{context}: unstable input_id mapping")
    source_asset = _safe_relative(row["source_asset_path"], field=f"{context}.source_asset_path")
    if not source_asset.startswith("data/glm/"):
        raise BatchValidationError(f"{context}: source_asset_path must be under data/glm/")
    if not isinstance(row["source_asset_line"], int) or row["source_asset_line"] < 1:
        raise BatchValidationError(f"{context}: invalid source_asset_line")
    question = row["original_question"]
    if not isinstance(question, str) or not question.strip():
        raise BatchValidationError(f"{context}: empty original_question")
    actual_question_sha = hashlib.sha256(question.encode("utf-8")).hexdigest()
    if row["original_question_sha256"] != actual_question_sha:
        raise BatchValidationError(f"{context}: question SHA mismatch")
    evidence = row["evidence"]
    if not isinstance(evidence, dict):
        raise BatchValidationError(f"{context}: evidence must be an object")
    _exact_fields(evidence, EVIDENCE_FIELDS, f"{context}.evidence")
    if not SHA256.fullmatch(str(evidence["range_sha256"])):
        raise BatchValidationError(f"{context}: invalid evidence range SHA")
    if evidence["excerpt_available"] is not False:
        raise BatchValidationError(f"{context}: source excerpts must not be copied into the batch")
    if not isinstance(row["duplicate_candidate_ids"], list):
        raise BatchValidationError(f"{context}: duplicate candidates must be an array")
    if any(not re.fullmatch(r"mqi-eval-[0-9]{6}", str(value)) for value in row["duplicate_candidate_ids"]):
        raise BatchValidationError(f"{context}: invalid duplicate candidate reference")
    if not isinstance(row["prior_review_refs"], list):
        raise BatchValidationError(f"{context}: prior_review_refs must be an array")
    for ref in row["prior_review_refs"]:
        if not isinstance(ref, dict) or set(ref) != {"asset_path", "record_id"}:
            raise BatchValidationError(f"{context}: invalid prior review reference")
        asset = _safe_relative(ref["asset_path"], field=f"{context}.prior_review_ref")
        if not asset.startswith("data/glm/"):
            raise BatchValidationError(f"{context}: review reference must be under data/glm/")
    if row["review_contract"] != {
        "independent_review_required": True,
        "prior_decisions_intentionally_omitted": True,
        "offline_only": True,
        "admission": "hold",
    }:
        raise BatchValidationError(f"{context}: review contract changed")


def _bounded_string(value: object, *, field: str, low: int, high: int) -> str:
    if not isinstance(value, str):
        raise BatchValidationError(f"{field} must be a string")
    text = value.strip()
    if not low <= len(text) <= high:
        raise BatchValidationError(f"{field} must contain {low}-{high} characters")
    if "```" in text or re.search(r"\[[0-9]+\]", text):
        raise BatchValidationError(f"{field} must not contain an answer or citation block")
    if FORBIDDEN_OUTPUT.search(text):
        raise BatchValidationError(f"{field} must not contain paths, credentials, or invented line ranges")
    return text


def _validate_output_row(
    row: dict[str, Any], source: dict[str, Any], task: dict[str, Any], line: int
) -> None:
    context = f"{task['task_id']} output line {line}"
    _exact_fields(row, OUTPUT_FIELDS, context)
    if FORBIDDEN_OUTPUT.search(json.dumps(row, ensure_ascii=False)):
        raise BatchValidationError(
            f"{context}: output must not contain paths, credentials, or invented line ranges"
        )
    copied = {
        "schema_version": OUTPUT_SCHEMA,
        "task_id": task["task_id"],
        "task_kind": task["task_kind"],
        "input_id": source["input_id"],
        "source_candidate_id": source["source_candidate_id"],
        "original_question_sha256": source["original_question_sha256"],
        "admission": "hold",
        "offline_only": True,
    }
    for field, expected in copied.items():
        if row[field] != expected:
            raise BatchValidationError(f"{context}: {field} must copy the frozen value")
    action = row["quality_action"]
    if action not in QUALITY_ACTIONS:
        raise BatchValidationError(f"{context}: invalid quality_action")
    quality_reason = _bounded_string(
        row["quality_reason"], field=f"{context}.quality_reason", low=20, high=600
    )
    scope_reason = _bounded_string(
        row["scope_reason"], field=f"{context}.scope_reason", low=20, high=600
    )
    if quality_reason == source["original_question"]:
        raise BatchValidationError(f"{context}: reason copies source text instead of reviewing it")
    if scope_reason == quality_reason:
        raise BatchValidationError(f"{context}: quality and scope reasons must be independent")

    rewrite = row["rewrite_question"]
    if action == "rewrite":
        rewrite = _bounded_string(
            rewrite, field=f"{context}.rewrite_question", low=6, high=240
        )
        if rewrite == source["original_question"] or GENERIC_REWRITE.search(rewrite):
            raise BatchValidationError(f"{context}: rewrite must remove the template wrapper")
    elif rewrite is not None:
        raise BatchValidationError(f"{context}: rewrite_question is only allowed for rewrite")

    duplicate_refs = row["duplicate_of_input_ids"]
    if not isinstance(duplicate_refs, list) or len(set(duplicate_refs)) != len(duplicate_refs):
        raise BatchValidationError(f"{context}: duplicate references must be a unique array")
    if any(ref not in source["duplicate_candidate_ids"] for ref in duplicate_refs):
        raise BatchValidationError(f"{context}: duplicate reference was not supplied in the input")
    if action == "remove_duplicate" and not duplicate_refs:
        raise BatchValidationError(f"{context}: remove_duplicate requires a concrete input reference")
    if duplicate_refs and action != "remove_duplicate":
        raise BatchValidationError(f"{context}: duplicate references require remove_duplicate")

    variants = row["query_variants"]
    if not isinstance(variants, list) or not 1 <= len(variants) <= 4:
        raise BatchValidationError(f"{context}: query_variants must contain 1-4 entries")
    variant_texts: list[str] = []
    for variant_index, variant in enumerate(variants, 1):
        if not isinstance(variant, dict) or set(variant) != {"text", "variant_type", "purpose"}:
            raise BatchValidationError(f"{context}: invalid query variant fields")
        text = _bounded_string(
            variant["text"], field=f"{context}.query_variants[{variant_index}].text", low=3, high=180
        )
        _bounded_string(
            variant["purpose"], field=f"{context}.query_variants[{variant_index}].purpose", low=6, high=180
        )
        if variant["variant_type"] not in VARIANT_TYPES:
            raise BatchValidationError(f"{context}: invalid variant_type")
        if text == source["original_question"] or GENERIC_REWRITE.search(text):
            raise BatchValidationError(f"{context}: query variant copies the template wrapper")
        variant_texts.append(text)
    if len(set(variant_texts)) != len(variant_texts):
        raise BatchValidationError(f"{context}: query variants must be unique")

    evidence_scope = row["evidence_scope"]
    if evidence_scope not in EVIDENCE_SCOPES:
        raise BatchValidationError(f"{context}: invalid evidence_scope")
    if evidence_scope != "insufficient_excerpt":
        raise BatchValidationError(f"{context}: source evidence is intentionally unavailable in this batch")
    unsupported = row["unsupported_request_parts"]
    if not isinstance(unsupported, list) or len(unsupported) > 6:
        raise BatchValidationError(f"{context}: unsupported_request_parts must be an array")
    for index, part in enumerate(unsupported, 1):
        _bounded_string(part, field=f"{context}.unsupported[{index}]", low=2, high=240)
    recommended = row["recommended_action"]
    if recommended not in RECOMMENDED_ACTIONS:
        raise BatchValidationError(f"{context}: invalid recommended_action")
    if row["confidence"] not in CONFIDENCE:
        raise BatchValidationError(f"{context}: invalid confidence")
    if action == "rewrite" and recommended != "rewrite_then_human_review":
        raise BatchValidationError(f"{context}: rewrite must return to human review")
    if action == "remove_duplicate" and recommended != "dedupe_then_human_review":
        raise BatchValidationError(f"{context}: duplicate removal must return to dedupe review")
    if action == "remove_unnatural" and recommended != "remove_candidate":
        raise BatchValidationError(f"{context}: unnatural removal must recommend remove_candidate")
    if evidence_scope in {"mismatch", "insufficient_excerpt"} and recommended not in {
        "source_check_then_review",
        "rewrite_then_human_review",
        "remove_candidate",
    }:
        raise BatchValidationError(f"{context}: uncertain evidence requires another review step")
    if action == "keep" and evidence_scope in {"mismatch", "insufficient_excerpt"}:
        raise BatchValidationError(f"{context}: keep conflicts with uncertain evidence")


def _validate_task(
    batch_dir: Path,
    task: dict[str, Any],
    status: str,
    *,
    require_complete: bool,
) -> dict[str, Any]:
    input_rows = _load_jsonl(batch_dir / task["input"])
    if len(input_rows) != task["input_count"]:
        raise BatchValidationError(f"{task['task_id']}: input row count mismatch")
    for line, row in enumerate(input_rows, 1):
        _validate_input_row(row, task, line)
    ids = [row["input_id"] for row in input_rows]
    if len(ids) != len(set(ids)):
        raise BatchValidationError(f"{task['task_id']}: duplicate input IDs")

    output_path = batch_dir / task["output"]
    completed_status = status in {"READY_FOR_CODEX", "DONE"}
    if not output_path.is_file():
        if require_complete or completed_status:
            raise BatchValidationError(f"{task['task_id']}: output is required")
        return {"task_id": task["task_id"], "status": status, "output": "missing", "rows": 0}
    output_rows = _load_jsonl(output_path)
    if len(output_rows) != len(input_rows):
        raise BatchValidationError(f"{task['task_id']}: output must cover every input exactly once")
    if [row.get("input_id") for row in output_rows] != ids:
        raise BatchValidationError(f"{task['task_id']}: output IDs must preserve exact input order")
    combined_reasons: list[tuple[str, str]] = []
    for line, (output, source) in enumerate(zip(output_rows, input_rows), 1):
        _validate_output_row(output, source, task, line)
        combined_reasons.append((output["quality_reason"], output["scope_reason"]))
    duplicates = [pair for pair, count in Counter(combined_reasons).items() if count > 1]
    if duplicates:
        raise BatchValidationError(
            f"{task['task_id']}: repeated quality/scope reasoning suggests mechanical copying"
        )
    return {
        "task_id": task["task_id"],
        "status": status,
        "output": "valid",
        "rows": len(output_rows),
        "sha256": _sha_file(output_path),
    }


def _mark_ready(batch_dir: Path, task_id: str, output_sha: str) -> None:
    queue_path = batch_dir / "TASK_QUEUE.md"
    text = queue_path.read_text(encoding="utf-8")
    heading = rf"(?ms)(^## {re.escape(task_id)}\s*$)(.*?)(?=^## |\Z)"
    match = re.search(heading, text)
    if not match:
        raise BatchValidationError(f"{task_id}: missing queue section")
    section = match.group(2)
    status = _queue_value(section, "status")
    if status not in {"READY_FOR_MIMO", "NEEDS_REWRITE", "READY_FOR_CODEX"}:
        raise BatchValidationError(f"{task_id}: status {status} cannot be marked ready")
    section = re.sub(
        r"(?m)^- status: `[^`]+`\s*$", "- status: `READY_FOR_CODEX`", section, count=1
    )
    section = re.sub(
        r"(?m)^- output_sha256:.*$", f"- output_sha256: {output_sha}", section, count=1
    )
    updated = text[: match.start(2)] + section + text[match.end(2) :]
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=queue_path.parent, delete=False
    ) as handle:
        handle.write(updated)
        temporary = Path(handle.name)
    os.replace(temporary, queue_path)


def validate_batch(
    batch_dir: Path,
    *,
    root: Path = ROOT,
    task_ids: list[str] | None = None,
    require_complete: bool = False,
    mark_ready: bool = False,
) -> dict[str, Any]:
    batch_dir = batch_dir.resolve()
    try:
        batch_dir.relative_to(root.resolve())
    except ValueError as exc:
        raise BatchValidationError("batch directory must be inside repository") from exc
    manifest, statuses = _validate_manifest(batch_dir, root)
    tasks_by_id = {task["task_id"]: task for task in manifest["tasks"]}
    selected_ids = task_ids or list(tasks_by_id)
    if len(set(selected_ids)) != len(selected_ids):
        raise BatchValidationError("task IDs must not repeat")
    unknown = set(selected_ids) - set(tasks_by_id)
    if unknown:
        raise BatchValidationError(f"unknown task IDs: {sorted(unknown)}")
    if mark_ready and len(selected_ids) != 1:
        raise BatchValidationError("--mark-ready requires exactly one --task")
    results = [
        _validate_task(
            batch_dir,
            tasks_by_id[task_id],
            statuses[task_id],
            require_complete=require_complete,
        )
        for task_id in selected_ids
    ]
    if mark_ready:
        result = results[0]
        if result["output"] != "valid":
            raise BatchValidationError("cannot mark a missing output ready")
        _mark_ready(batch_dir, selected_ids[0], result["sha256"])
        result["status"] = "READY_FOR_CODEX"
    return {
        "schema_version": BATCH_SCHEMA,
        "offline_only": True,
        "admission": "hold",
        "batch_id": manifest["batch_id"],
        "selected_task_count": len(results),
        "valid_output_count": sum(result["output"] == "valid" for result in results),
        "missing_output_count": sum(result["output"] == "missing" for result in results),
        "tasks": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("--task", dest="tasks", action="append")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--mark-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = validate_batch(
            args.batch_dir,
            task_ids=args.tasks,
            require_complete=args.require_complete,
            mark_ready=args.mark_ready,
        )
    except (BatchValidationError, OSError) as exc:
        print(f"Offline MiMo batch rejected: {exc}")
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
