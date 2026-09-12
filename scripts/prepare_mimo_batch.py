#!/usr/bin/env python3
"""Prepare a deterministic, offline MiMo quality-review batch.

The generated inputs are self-contained and contain only non-sensitive metadata.
They never become evaluation cases or factual evidence automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/glm/mimo-quality-20260913"
DEFAULT_CANDIDATE_DIR = (
    ROOT / "data/glm/overnight-rag-evaluation-20260906/eval-candidates"
)
TEMPLATE_MARKER = "模板生成"
BATCH_SCHEMA = "mimo-quality-batch/v1"
INPUT_SCHEMA = "mimo-quality-input/v1"
TASK_KINDS = (
    "data_cleaning_and_dedupe",
    "query_variant_rewrite",
    "evidence_boundary_triage",
)
REVIEW_ASSETS = (
    "data/glm/semantic-review-and-golden-set-20260906/semantic-review.jsonl",
    "data/glm/golden-set-audit-r2-20260906/gold-audit.jsonl",
    "data/glm/golden-set-red-team-r3-20260906/r3-audit.jsonl",
)
GENERIC_PATTERNS = (
    ("generic_definition_wrapper", r"到底是什么|解释一下这个概念"),
    ("interview_wrapper", r"我在面试里被问到|面试里怎么答"),
    ("material_wrapper", r"根据你的资料|结合资料|资料里的内容|在你的资料里"),
    ("citation_request", r"出处行号|给出出处"),
    ("generic_mechanism_wrapper", r"请讲讲.+底层机制或工作原理"),
    ("generic_pitfall_wrapper", r"容易被忽略的边界条件|资料里有没有对应说明"),
)


class BatchPreparationError(ValueError):
    """Raised when a source batch cannot be packaged safely."""


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _json_line(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"


def _repo_relative(path: Path, root: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise BatchPreparationError(f"path must be inside repository: {path}") from exc
    if ".." in relative.parts:
        raise BatchPreparationError(f"path escapes repository: {path}")
    return relative.as_posix()


def _load_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BatchPreparationError(f"cannot read {path}: {exc}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            raise BatchPreparationError(f"{path}:{line_number}: blank JSONL line")
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BatchPreparationError(
                f"{path}:{line_number}: invalid JSON ({exc.msg})"
            ) from exc
        if not isinstance(row, dict):
            raise BatchPreparationError(f"{path}:{line_number}: row must be an object")
        rows.append((line_number, row))
    return rows


def _candidate_sources(root: Path, requested: Iterable[Path] | None) -> list[Path]:
    if requested:
        paths = [path.resolve() for path in requested]
    else:
        candidate_dir = root / DEFAULT_CANDIDATE_DIR.relative_to(ROOT)
        paths = sorted(candidate_dir.glob("batch-*.jsonl"))
    if not paths:
        raise BatchPreparationError("no candidate JSONL files found")
    for path in paths:
        relative = _repo_relative(path, root)
        if not relative.startswith("data/glm/") or path.suffix != ".jsonl":
            raise BatchPreparationError(f"candidate source must be data/glm JSONL: {path}")
    return sorted(paths)


def _template_candidate(row: dict[str, Any]) -> bool:
    risks = row.get("risk_notes", [])
    return isinstance(risks, list) and any(
        isinstance(note, str) and TEMPLATE_MARKER in note for note in risks
    )


def _template_flags(question: str) -> list[str]:
    return [name for name, pattern in GENERIC_PATTERNS if re.search(pattern, question)]


def _title_fragment(question: str, topic: object) -> str:
    quoted = re.search(r"[「『](.+?)[」』]", question)
    if quoted:
        return quoted.group(1)[:180]
    return str(topic or "未分类主题")[:180]


def _source_origin(path: Path) -> str:
    text = path.as_posix()
    if "/Obsidian/iOS/" in text:
        return "obsidian-ios"
    if "/ios-source-learning/" in text or "/iOS底层源码探索/" in text:
        return "ios-source-learning"
    if "/26暑期内容/" in text:
        return "summer2026"
    if "/apple-docs-vault/" in text:
        return "apple-docs"
    if "/apple-developer-archive-vault/" in text:
        return "apple-archive"
    return "other-reviewed-source"


def _evidence(row: dict[str, Any]) -> dict[str, Any]:
    raw_path = row.get("expected_source_path")
    start = row.get("expected_start_line")
    end = row.get("expected_end_line")
    if not isinstance(raw_path, str) or not raw_path:
        raise BatchPreparationError(f"{row.get('id')}: template candidate lacks source")
    if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
        raise BatchPreparationError(f"{row.get('id')}: invalid evidence range")
    path = Path(raw_path)
    if not path.is_file():
        raise BatchPreparationError(f"{row.get('id')}: source is unavailable: {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if end > len(lines):
        raise BatchPreparationError(
            f"{row.get('id')}: evidence range {start}-{end} exceeds {len(lines)} lines"
        )
    # Verify the original range locally, but never copy private source text or
    # filesystem paths into a Git-backed MiMo work package.
    full = "\n".join(lines[start - 1 : end]).strip()
    if not full:
        raise BatchPreparationError(f"{row.get('id')}: source range is empty")
    return {
        "source_origin": _source_origin(path),
        "evidence_type": row.get("expected_evidence_type"),
        "range_sha256": _sha_bytes(full.encode("utf-8")),
        "excerpt_available": False,
    }


def _review_refs(root: Path) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for relative in REVIEW_ASSETS:
        path = root / relative
        if not path.is_file():
            continue
        for _, row in _load_jsonl(path):
            source_id = row.get("source_eval_id")
            record_id = row.get("id")
            if isinstance(source_id, str) and isinstance(record_id, str):
                result[source_id].append(
                    {"asset_path": relative, "record_id": record_id}
                )
    return result


def _anchor_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("expected_source_path"),
        row.get("expected_start_line"),
        row.get("expected_end_line"),
    )


def _input_id(candidate_id: str) -> str:
    if not re.fullmatch(r"eval-[0-9]{6}", candidate_id):
        raise BatchPreparationError(f"unsupported candidate id: {candidate_id!r}")
    return f"mqi-{candidate_id}"


def _prepare_rows(
    sources: list[Path], root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, Any]]]:
    candidates: list[tuple[Path, int, dict[str, Any]]] = []
    source_assets: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for path in sources:
        relative = _repo_relative(path, root)
        source_assets.append({"path": relative, "sha256": _sha_file(path)})
        for line_number, row in _load_jsonl(path):
            if not _template_candidate(row):
                continue
            candidate_id = row.get("id")
            if not isinstance(candidate_id, str) or candidate_id in seen_ids:
                raise BatchPreparationError(f"duplicate or invalid candidate id: {candidate_id!r}")
            seen_ids.add(candidate_id)
            candidates.append((path, line_number, row))
    if not candidates:
        raise BatchPreparationError("no template-review candidates found")

    candidates.sort(
        key=lambda item: (
            str(item[2].get("topic", "")),
            str(item[2].get("expected_source_path", "")),
            int(item[2].get("expected_start_line") or 0),
            str(item[2]["id"]),
        )
    )
    refs = _review_refs(root)
    prior_by_anchor: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    output: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for path, line_number, row in candidates:
        candidate_id = str(row["id"])
        input_id = _input_id(candidate_id)
        try:
            evidence = _evidence(row)
        except BatchPreparationError as exc:
            # A stale source range cannot be reviewed from an invented excerpt.
            # Keep a deterministic record for Codex-side anchor repair instead.
            excluded.append(
                {
                    "source_candidate_id": candidate_id,
                    "source_asset_path": _repo_relative(path, root),
                    "source_asset_line": line_number,
                    "original_question_sha256": _sha_bytes(
                        str(row.get("question", "")).encode("utf-8")
                    ),
                    "reason": "invalid_or_stale_anchor",
                }
            )
            continue
        anchor = _anchor_key(row)
        duplicates = prior_by_anchor[anchor][-8:]
        question = str(row.get("question", "")).strip()
        if not question:
            raise BatchPreparationError(f"{candidate_id}: question is empty")
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            raise BatchPreparationError(f"{candidate_id}: aliases must be strings")
        relative = _repo_relative(path, root)
        prepared = {
            "schema_version": INPUT_SCHEMA,
            "input_id": input_id,
            "source_candidate_id": candidate_id,
            "source_asset_path": relative,
            "source_asset_line": line_number,
            "original_question_sha256": _sha_bytes(question.encode("utf-8")),
            "original_question": question,
            "original_aliases": aliases,
            "candidate_topic": row.get("topic"),
            "candidate_category": row.get("category"),
            "candidate_difficulty": row.get("difficulty"),
            "candidate_claimed_mode": row.get("expected_mode"),
            "title_fragment": _title_fragment(question, row.get("topic")),
            "template_flags": _template_flags(question),
            "evidence": evidence,
            "duplicate_candidate_ids": duplicates,
            "prior_review_refs": refs.get(candidate_id, []),
            "review_contract": {
                "independent_review_required": True,
                "prior_decisions_intentionally_omitted": True,
                "offline_only": True,
                "admission": "hold",
            },
        }
        output.append(prepared)
        prior_by_anchor[anchor].append(input_id)
    return output, source_assets, excluded


def _write_schema(path: Path) -> None:
    path.write_text(
        """# MiMo quality batch schema v1

This is an offline candidate-cleaning batch. Nothing in `inputs/` or `outputs/`
is factual evidence, a production evaluation case, or approved training data.

Each output JSONL row must contain exactly these fields:

`schema_version`, `task_id`, `task_kind`, `input_id`, `source_candidate_id`,
`original_question_sha256`, `quality_action`, `quality_reason`,
`rewrite_question`, `duplicate_of_input_ids`, `query_variants`,
`evidence_scope`, `scope_reason`, `unsupported_request_parts`,
`recommended_action`, `confidence`, `admission`, `offline_only`.

Allowed values:

- `schema_version`: `mimo-quality-output/v1`
- `quality_action`: `keep`, `rewrite`, `remove_duplicate`, `remove_unnatural`, `hold_for_human`
- `query_variants[].variant_type`: `colloquial`, `concise`, `english_chinese`, `abbreviation`, `symbol`, `error_tolerant`
- `evidence_scope`: always `insufficient_excerpt`, because original material is not
  copied into this Git-backed work package
- `recommended_action`: `human_review`, `rewrite_then_human_review`, `dedupe_then_human_review`, `source_check_then_review`, `remove_candidate`
- `confidence`: `low`, `medium`, `high`
- `admission`: always `hold`
- `offline_only`: always `true`

`query_variants` contains 1-4 objects with exactly `text`, `variant_type`, and
`purpose`. Reasons must be independent judgments grounded in the supplied
candidate text and non-sensitive metadata. Do not infer source facts, write a
final answer, make an Apple implementation claim, or change source files.
""",
        encoding="utf-8",
    )


def _write_prompt(path: Path, batch_relative: str) -> None:
    path.write_text(
        f"""你正在执行一个可以持续数小时的 MiMo 离线质量审查任务。批次目录是 `{batch_relative}`。

目标是审查由标题模板生成的候选题。你必须逐条重新判断题面是否自然、是否与同锚点候选重复，以及怎样改写或生成检索变体。旧审核只以引用 ID 提供，旧结论故意没有放进输入，禁止凭旧标签机械复制。原始资料不在此批次中，不能判断事实是否被它支持。

执行规则：

1. 先完整阅读 `SCHEMA.md`、`BATCH_MANIFEST.json` 和 `TASK_QUEUE.md`。
2. 只处理状态为 `READY_FOR_MIMO` 或 `NEEDS_REWRITE` 的任务，严格按 task 编号和输入行顺序执行。已完成任务不要重做。
3. 每次只完成一个任务，输出到队列指定的相对路径。每条输入恰好输出一行 JSON，字段只能使用 schema 允许的字段。
4. `quality_reason` 和 `scope_reason` 必须是你对原题和候选范围的独立判断。固定填写 `evidence_scope=insufficient_excerpt`，并说明需要本地 source check；改写应像真实用户问题，去掉“根据你的资料”“给出处行号”等模板壳。
5. `duplicate_of_input_ids` 只能引用该输入提供的 `duplicate_candidate_ids`。不确定时留空并使用 `hold_for_human`，不可猜测未提供的候选。
6. 不生成问题的答案，不把摘录改写成事实卡片，不宣称线上/本地检索成功，不修改原始资料、索引、配置、评测 manifest 或生产。
7. 所有行固定 `admission=hold`、`offline_only=true`。完成质量审查不代表准入。
8. 完成一个任务后运行：
   `uv run python scripts/validate_mimo_batch.py {batch_relative} --task task-XXX --require-complete --mark-ready`
   校验失败就只修该任务输出，再重跑。随后运行：
   `uv run python scripts/mimo_handoff.py checkpoint {batch_relative}/RUN_MANIFEST.json --state PARTIAL`
9. 每完成 3-5 个任务，在专用分支 `mimo/mimo-quality-20260913` 上提交并推送一次进度。只能提交本批次的 `outputs/*.jsonl`、`TASK_QUEUE.md`、`RUN_MANIFEST.json`、`RUN_MANIFEST.sha256`；不得 force push，不得修改 inputs、prompt、schema 或仓库其他文件。
10. 可以在所有有用工作做完后提前结束，不要为了耗时生成额外内容。若受阻，将当前任务状态改为 `BLOCKED`，写清简短 `note`，checkpoint、提交并推送已有有效进度。

全部任务结束后运行全批次校验：
`uv run python scripts/validate_mimo_batch.py {batch_relative} --require-complete`
然后运行 handoff checkpoint（状态应变为 `READY_FOR_CODEX`），做最后一次普通提交并推送。最后只报告分支名、最新 commit、完成/阻塞任务数和全批校验结果。
""",
        encoding="utf-8",
    )


def _queue_text(tasks: list[dict[str, Any]], batch_relative: str) -> str:
    lines = [
        "# MiMo quality task queue",
        "",
        "All tasks are offline candidate review. Every output remains `admission=hold`.",
        "",
    ]
    for task in tasks:
        lines.extend(
            [
                f"## {task['task_id']}",
                "- status: `READY_FOR_MIMO`",
                f"- kind: `{task['task_kind']}`",
                f"- input: `{batch_relative}/{task['input']}`",
                f"- input_count: {task['input_count']}",
                f"- output: `{task['output']}`",
                "- output_sha256:",
                "- note:",
                "",
            ]
        )
    return "\n".join(lines)


def prepare_batch(
    output_dir: Path,
    *,
    root: Path = ROOT,
    source_paths: Iterable[Path] | None = None,
    chunk_size: int = 50,
) -> dict[str, Any]:
    if not 40 <= chunk_size <= 80:
        raise BatchPreparationError("chunk_size must be between 40 and 80")
    output_dir = output_dir.resolve()
    relative_output = _repo_relative(output_dir, root)
    if not relative_output.startswith("data/glm/"):
        raise BatchPreparationError("output_dir must be under data/glm/")
    if output_dir.exists():
        raise BatchPreparationError(f"output directory already exists: {output_dir}")

    sources = _candidate_sources(root, source_paths)
    rows, source_assets, excluded = _prepare_rows(sources, root)
    output_dir.mkdir(parents=True)
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir()
    excluded_payload = "".join(_json_line(row) for row in excluded)
    excluded_path = output_dir / "EXCLUDED_INPUTS.jsonl"
    excluded_path.write_text(excluded_payload, encoding="utf-8")
    tasks: list[dict[str, Any]] = []
    task_count = math.ceil(len(rows) / chunk_size)
    for index in range(task_count):
        task_id = f"task-{index + 1:03d}"
        task_kind = TASK_KINDS[index % len(TASK_KINDS)]
        shard = rows[index * chunk_size : (index + 1) * chunk_size]
        input_name = f"inputs/{task_id}.jsonl"
        output_name = f"outputs/{task_id}.jsonl"
        for row in shard:
            row["task_id"] = task_id
            row["task_kind"] = task_kind
        payload = "".join(_json_line(row) for row in shard)
        input_path = output_dir / input_name
        input_path.write_text(payload, encoding="utf-8")
        tasks.append(
            {
                "task_id": task_id,
                "task_kind": task_kind,
                "input": input_name,
                "input_count": len(shard),
                "input_sha256": _sha_bytes(payload.encode("utf-8")),
                "output": output_name,
            }
        )

    manifest = {
        "schema_version": BATCH_SCHEMA,
        "batch_id": output_dir.name,
        "offline_only": True,
        "admission": "hold",
        "candidate_filter": TEMPLATE_MARKER,
        "input_count": len(rows),
        "excluded_input_count": len(excluded),
        "excluded_inputs_file": "EXCLUDED_INPUTS.jsonl",
        "excluded_inputs_sha256": _sha_bytes(excluded_payload.encode("utf-8")),
        "task_count": len(tasks),
        "chunk_size": chunk_size,
        "source_assets": source_assets,
        "review_reference_assets": [
            {"path": path, "sha256": _sha_file(root / path)}
            for path in REVIEW_ASSETS
            if (root / path).is_file()
        ],
        "tasks": tasks,
    }
    (output_dir / "BATCH_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "TASK_QUEUE.md").write_text(
        _queue_text(tasks, relative_output), encoding="utf-8"
    )
    _write_schema(output_dir / "SCHEMA.md")
    _write_prompt(output_dir / "MIMO_PROMPT.txt", relative_output)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunk-size", type=int, default=50)
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        help="candidate JSONL; repeat to override the default batch directory",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = prepare_batch(
            args.output_dir,
            source_paths=args.source,
            chunk_size=args.chunk_size,
        )
    except (BatchPreparationError, OSError) as exc:
        print(f"MiMo batch preparation failed: {exc}")
        return 2
    print(
        f"Prepared offline MiMo batch: {manifest['input_count']} inputs, "
        f"{manifest['task_count']} tasks, admission=hold"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
