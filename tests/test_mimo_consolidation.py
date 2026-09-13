import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts import validate_mimo_consolidation


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class MimoConsolidationTests(unittest.TestCase):
    def test_accepts_a_valid_cluster_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            batch = Path(directory)
            source = {
                "schema_version": "mimo-candidate-consolidation/v1",
                "task_id": "task-001",
                "cluster_id": "cluster-0001",
                "member_input_ids": ["mqi-eval-000001", "mqi-eval-000002"],
                "members": [],
                "offline_only": True,
                "admission": "hold",
            }
            input_path = batch / "inputs/task-001.jsonl"
            _write_jsonl(input_path, [source])
            digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
            manifest = {
                "schema_version": "mimo-candidate-consolidation/v1",
                "batch_id": "batch",
                "offline_only": True,
                "admission": "hold",
                "tasks": [{"task_id": "task-001", "input": "inputs/task-001.jsonl", "output": "outputs/task-001.jsonl", "input_count": 1, "input_sha256": digest}],
            }
            (batch / "BATCH_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            (batch / "TASK_QUEUE.md").write_text("## task-001\n- status: `READY_FOR_MIMO`\n", encoding="utf-8")
            _write_jsonl(batch / "outputs/task-001.jsonl", [{
                "schema_version": "mimo-candidate-consolidation/v1",
                "task_id": "task-001",
                "cluster_id": "cluster-0001",
                "member_input_ids": source["member_input_ids"],
                "decision": "keep_one",
                "representative_input_ids": ["mqi-eval-000001"],
                "reason": "两条题目都围绕同一概念的定义，测试意图重叠，保留一个即可覆盖。",
                "keep_distinctions": [],
                "recommended_next_step": "human_review",
                "confidence": "high",
                "offline_only": True,
                "admission": "hold",
            }])
            summary = validate_mimo_consolidation.validate(batch)
            self.assertEqual(1, summary["valid_output_count"])

if __name__ == "__main__":
    unittest.main()
