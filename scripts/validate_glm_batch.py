#!/usr/bin/env python3
"""Validate a GLM offline-evaluation batch without changing repository data."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


EVAL_MODES = {"knowledge", "no_evidence", "general"}
TRIAGE_CLASSES = {
    "missing_source",
    "source_quality",
    "lexical_recall",
    "semantic_recall",
    "rerank",
    "routing",
    "follow_up_context",
    "citation_validation",
    "answer_prompt",
    "unknown",
}


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{number}: JSONL record must be an object")
            continue
        records.append(record)
    return records


def line_count(path: Path, cache: dict[Path, int]) -> int:
    if path not in cache:
        # Match the indexer's line-number contract in chunker.py. A trailing
        # newline deliberately creates the final empty physical line here.
        cache[path] = len(path.read_text(encoding="utf-8", errors="replace").split("\n"))
    return cache[path]


def check_file_range(
    source: object,
    start: object,
    end: object,
    label: str,
    errors: list[str],
    cache: dict[Path, int],
    *,
    allow_directory: bool = False,
) -> bool:
    if not isinstance(source, str) or not Path(source).is_absolute():
        errors.append(f"{label}: source path must be an absolute string")
        return False
    path = Path(source)
    if path.is_file():
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"{label}: file-backed evidence requires integer line bounds")
            return False
        total = line_count(path, cache)
        if start < 1 or end < start or end > total:
            errors.append(f"{label}: invalid line range {start}-{end} for {total} lines")
            return False
        return True
    if allow_directory and path.is_dir():
        if start != 1 or end != 1:
            errors.append(f"{label}: directory findings must use the 1-1 sentinel range")
            return False
        return True
    errors.append(f"{label}: source path does not exist as an allowed file")
    return False


def require(record: dict, keys: set[str], label: str, errors: list[str]) -> None:
    missing = sorted(key for key in keys if key not in record)
    if missing:
        errors.append(f"{label}: missing required fields: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path, help="path to data/glm/<batch>")
    args = parser.parse_args()
    batch = args.batch.resolve()
    errors: list[str] = []
    cache: dict[Path, int] = {}

    expected = [
        batch / "source-coverage.jsonl",
        batch / "terminology-aliases.jsonl",
        batch / "quality-findings.jsonl",
        batch / "failure-triage.jsonl",
        batch / "retrieval-samples" / "fts-sample-results.jsonl",
    ]
    eval_files = sorted((batch / "eval-candidates").glob("*.jsonl"))
    missing = [path for path in [*expected, *eval_files] if not path.is_file()]
    if not eval_files:
        missing.append(batch / "eval-candidates/*.jsonl")
    if missing:
        for path in missing:
            errors.append(f"missing required artifact: {path}")
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    evals: dict[str, dict] = {}
    row_count = 0
    for path in eval_files:
        for record in load_jsonl(path, errors):
            row_count += 1
            label = f"{path.name}:{record.get('id', '<missing id>')}"
            require(
                record,
                {
                    "id", "question", "category", "topic", "difficulty", "expected_mode",
                    "expected_source_path", "expected_start_line", "expected_end_line",
                    "expected_evidence_type", "aliases", "dialogue_context", "rationale",
                    "risk_notes", "created_from",
                },
                label,
                errors,
            )
            identifier = record.get("id")
            if not isinstance(identifier, str) or identifier in evals:
                errors.append(f"{label}: eval id must be unique")
            else:
                evals[identifier] = record
            mode = record.get("expected_mode")
            if mode not in EVAL_MODES:
                errors.append(f"{label}: unsupported expected_mode {mode!r}")
                continue
            if mode == "knowledge":
                check_file_range(
                    record.get("expected_source_path"),
                    record.get("expected_start_line"),
                    record.get("expected_end_line"),
                    label,
                    errors,
                    cache,
                )
                if not record.get("expected_evidence_type"):
                    errors.append(f"{label}: knowledge record lacks evidence type")
                if not isinstance(record.get("aliases"), list) or not record["aliases"]:
                    errors.append(f"{label}: knowledge record requires aliases")
            elif any(
                record.get(field) is not None
                for field in (
                    "expected_source_path", "expected_start_line", "expected_end_line",
                    "expected_evidence_type",
                )
            ):
                errors.append(f"{label}: non-knowledge record must not carry source evidence")
            if record.get("category") == "follow_up" and not record.get("dialogue_context"):
                errors.append(f"{label}: follow-up record lacks dialogue context")

    coverage = load_jsonl(batch / "source-coverage.jsonl", errors)
    aliases = load_jsonl(batch / "terminology-aliases.jsonl", errors)
    quality = load_jsonl(batch / "quality-findings.jsonl", errors)
    samples = load_jsonl(batch / "retrieval-samples" / "fts-sample-results.jsonl", errors)
    triage = load_jsonl(batch / "failure-triage.jsonl", errors)
    row_count += sum(map(len, (coverage, aliases, quality, samples, triage)))

    for record in coverage:
        label = f"coverage:{record.get('source_path', '<missing path>')}"
        require(record, {"source_id", "source_path", "line_count_estimate", "risk_notes"}, label, errors)
        check_file_range(record.get("source_path"), 1, record.get("line_count_estimate"), label, errors, cache)

    for record in aliases:
        label = f"alias:{record.get('id', '<missing id>')}"
        require(record, {"id", "aliases", "evidence_path", "evidence_start_line", "evidence_end_line"}, label, errors)
        source = record.get("evidence_path")
        if source is None:
            if record.get("evidence_start_line") is not None or record.get("evidence_end_line") is not None:
                errors.append(f"{label}: null evidence path requires null line bounds")
        else:
            check_file_range(source, record.get("evidence_start_line"), record.get("evidence_end_line"), label, errors, cache)

    directory_findings = 0
    for record in quality:
        label = f"quality:{record.get('id', '<missing id>')}"
        require(record, {"id", "source_path", "start_line", "end_line", "finding_type"}, label, errors)
        source = record.get("source_path")
        if isinstance(source, str) and Path(source).is_dir():
            directory_findings += 1
        check_file_range(
            source,
            record.get("start_line"),
            record.get("end_line"),
            label,
            errors,
            cache,
            allow_directory=True,
        )

    stale_observed_paths = 0
    for record in samples:
        label = f"sample:{record.get('eval_id', '<missing eval id>')}"
        require(record, {"eval_id", "observed_top_paths", "status"}, label, errors)
        if record.get("eval_id") not in evals:
            errors.append(f"{label}: referenced eval id is absent")
        if record.get("status") not in {"pass", "partial", "miss", "not_run"}:
            errors.append(f"{label}: unsupported status")
        for observed in record.get("observed_top_paths", []):
            if not Path(observed).exists():
                stale_observed_paths += 1

    for record in triage:
        label = f"triage:{record.get('id', '<missing id>')}"
        require(record, {"id", "failure_class", "case_ref"}, label, errors)
        if record.get("failure_class") not in TRIAGE_CLASSES:
            errors.append(f"{label}: unsupported failure class")
        case_ref = record.get("case_ref")
        if case_ref is not None and case_ref not in evals:
            errors.append(f"{label}: referenced eval id is absent")

    if errors:
        print(f"Validation failed with {len(errors)} error(s):")
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Validated {row_count} JSONL records from {batch.name}.")
    print(f"Eval records: {len(evals)}; directory-level quality findings: {directory_findings}.")
    print(f"Observed paths absent from disk (retained as retrieval evidence): {stale_observed_paths}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
