#!/usr/bin/env python3
"""Build an offline MiMo task that consolidates same-anchor eval candidates."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/glm/mimo-quality-20260913"
OUTPUT = ROOT / "data/glm/mimo-candidate-consolidation-20260913"
SCHEMA = "mimo-candidate-consolidation/v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, list):
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value), encoding="utf-8")
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def prepare() -> dict:
    if OUTPUT.exists():
        raise ValueError(f"output already exists: {OUTPUT}")
    source_manifest = json.loads((SOURCE / "BATCH_MANIFEST.json").read_text(encoding="utf-8"))
    inputs: dict[str, dict] = {}
    outputs: dict[str, dict] = {}
    for task in source_manifest["tasks"]:
        for row in _read_jsonl(SOURCE / task["input"]):
            inputs[row["input_id"]] = row
        for row in _read_jsonl(SOURCE / task["output"]):
            outputs[row["input_id"]] = row
    if set(inputs) != set(outputs):
        raise ValueError("source quality inputs and outputs differ")

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for input_id, source in inputs.items():
        result = outputs[input_id]
        key = (str(source["candidate_topic"]), source["evidence"]["range_sha256"])
        grouped[key].append(
            {
                "input_id": input_id,
                "source_candidate_id": source["source_candidate_id"],
                "category": source["candidate_category"],
                "difficulty": source["candidate_difficulty"],
                "title_fragment": source["title_fragment"],
                "rewritten_question": result["rewrite_question"],
                "query_variants": [variant["text"] for variant in result["query_variants"]],
                "quality_action": result["quality_action"],
                "recommended_action": result["recommended_action"],
            }
        )
    clusters: list[dict] = []
    for index, ((topic, anchor), members) in enumerate(sorted(grouped.items()), 1):
        if len(members) < 2:
            continue
        members.sort(key=lambda item: item["input_id"])
        clusters.append(
            {
                "schema_version": SCHEMA,
                "cluster_id": f"cluster-{index:04d}",
                "topic": topic,
                "anchor_sha256": anchor,
                "member_input_ids": [member["input_id"] for member in members],
                "members": members,
                "offline_only": True,
                "admission": "hold",
            }
        )
    if not clusters:
        raise ValueError("no same-anchor candidate clusters found")

    OUTPUT.mkdir(parents=True)
    chunk_size = 20
    tasks: list[dict] = []
    for index in range(math.ceil(len(clusters) / chunk_size)):
        task_id = f"task-{index + 1:03d}"
        rows = clusters[index * chunk_size : (index + 1) * chunk_size]
        for row in rows:
            row["task_id"] = task_id
        input_name = f"inputs/{task_id}.jsonl"
        output_name = f"outputs/{task_id}.jsonl"
        _write(OUTPUT / input_name, rows)
        tasks.append({"task_id": task_id, "input": input_name, "output": output_name, "input_count": len(rows), "input_sha256": _sha(OUTPUT / input_name)})
    manifest = {
        "schema_version": SCHEMA,
        "batch_id": OUTPUT.name,
        "offline_only": True,
        "admission": "hold",
        "source_batch": "data/glm/mimo-quality-20260913",
        "source_commit": "f58a5410d3fb55ce395f82321d0a9788840111e3",
        "source_manifest_sha256": _sha(SOURCE / "BATCH_MANIFEST.json"),
        "cluster_count": len(clusters),
        "single_candidate_count": sum(len(rows) == 1 for rows in grouped.values()),
        "task_count": len(tasks),
        "tasks": tasks,
    }
    _write(OUTPUT / "BATCH_MANIFEST.json", manifest)
    queue = ["# MiMo candidate consolidation queue", "", "All outputs remain offline candidates with admission=hold.", ""]
    for task in tasks:
        queue.extend([f"## {task['task_id']}", "- status: `READY_FOR_MIMO`", f"- input: `data/glm/{OUTPUT.name}/{task['input']}`", f"- input_count: {task['input_count']}", f"- output: `{task['output']}`", "- output_sha256:", "- note:", ""])
    (OUTPUT / "TASK_QUEUE.md").write_text("\n".join(queue), encoding="utf-8")
    (OUTPUT / "SCHEMA.md").write_text("""# Candidate consolidation output schema

Each output row contains exactly: `schema_version`, `task_id`, `cluster_id`,
`member_input_ids`, `decision`, `representative_input_ids`, `reason`,
`keep_distinctions`, `recommended_next_step`, `confidence`, `offline_only`, `admission`.

Allowed decisions: `keep_one`, `keep_multiple`, `hold_for_human`.
All outputs must copy the task, cluster and member IDs exactly. `representative_input_ids`
must be a non-empty subset of the members, except `hold_for_human` may leave it empty.
Use `keep_one` only when the supplied rewritten questions test the same learning intent.
Do not infer whether source material supports the questions. No paths, source excerpts,
line numbers, final answers, API keys, production claims, or index changes are allowed.
""", encoding="utf-8")
    (OUTPUT / "MIMO_PROMPT.txt").write_text(f"""你正在执行一个可持续数小时的离线候选压缩任务。批次目录：`data/glm/{OUTPUT.name}`。

目标：对同一主题且同一匿名证据锚点的候选问题簇做语义去重，产出更小、更可人工审查的正式评测候选池。你只能判断题面和测试意图，不能阅读原始资料，不能判断任何 iOS 事实是否成立。

1. 先读 `SCHEMA.md`、`BATCH_MANIFEST.json`、`TASK_QUEUE.md`。
2. 只处理 `READY_FOR_MIMO` 或 `NEEDS_REWRITE` 的任务。每个 cluster 输出一行 JSON，严格保持输入 cluster 顺序。
3. `keep_one`：同簇只保留一个能代表同一测试意图的候选；`keep_multiple`：问题确实测试不同角度时保留多个，并写清差异；不确定用 `hold_for_human`。
4. 不得因“问题看起来合理”就声称资料支持或检索成功。所有输出固定 `offline_only=true`、`admission=hold`。
5. 不得写原始资料路径、摘录、行号、最终答案、密钥、生产结论；不修改原始资料、索引、配置、评测 manifest 或生产。
6. 每完成一个 task，运行：
   `uv run python scripts/validate_mimo_consolidation.py data/glm/{OUTPUT.name} --task task-XXX --mark-ready`
   再运行：
   `uv run python scripts/mimo_handoff.py checkpoint data/glm/{OUTPUT.name}/RUN_MANIFEST.json --state PARTIAL`
7. 每 3-5 个任务提交并推送一次。只提交本批次 `outputs/*.jsonl`、`TASK_QUEUE.md`、`RUN_MANIFEST.json`、`RUN_MANIFEST.sha256`。不得 force push。
8. 全部完成后运行全批校验，再 checkpoint 为 `READY_FOR_CODEX`，提交并推送。最后只报告分支、commit、完成/阻塞数、校验结果。
""", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    manifest = prepare()
    print(f"Prepared {manifest['cluster_count']} clusters in {manifest['task_count']} tasks")
