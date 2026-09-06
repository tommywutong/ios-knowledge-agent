#!/usr/bin/env python3
"""从 FTS 抽样结果生成失败归因案例条目，与定义合并输出 failure-triage.jsonl。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRI = HERE.parent / "failure-triage.jsonl"
SAMPLES = HERE.parent / "retrieval-samples/fts-sample-results.jsonl"
EVAL_DIR = HERE.parent / "eval-candidates"

# eval_id -> (topic, category)
meta = {}
for fp in sorted(EVAL_DIR.glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        meta[r["id"]] = (r["topic"], r["category"])

samples = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]

CLASS_HINT = {
    "lexical_recall": "FTS 关键词召回未命中预期来源（关键词与来源用词不重叠或被分词稀释）",
    "source_coverage": "预期来源本身在 FTS 索引中可能未被覆盖或被同主题镜像挤出",
    "alias": "别名/口语改写未命中，标准术语检索正常",
    "path_mismatch": "预期路径与索引 display path 不一致",
    "other": "原因不明",
}

cases = []
for s in samples:
    if s["status"] in {"pass"}:
        continue
    topic, cat = meta.get(s["eval_id"], ("unknown", "unknown"))
    cls = s["suspected_failure_class"]
    if cls == "none":
        cls = "unknown"
    elif cls == "source_coverage":
        cls = "missing_source"
    elif cls == "alias":
        cls = "lexical_recall"
    if s["status"] == "not_run":
        cls = "unknown"
    if s["status"] == "partial":
        cls = "rerank"
    cases.append({
        "id": "triage-%06d" % 0,  # 占位，合并时重编
        "failure_class": cls,
        "symptom": f"[FTS 抽样 {s['status']}] {s['query'][:60]} —— " + CLASS_HINT.get(cls, cls) +
                   f"；预期来源 {Path(s['expected_source_path']).name}" +
                   (f"，top8 未见（首条为 {Path(s['observed_top_paths'][0]).name}）" if s["observed_top_paths"] else "，无返回"),
        "diagnostic_questions": [
            "该查询的关键词在预期来源全文中是否存在？",
            "FTS 分词后哪些词参与了 OR 匹配？",
            "预期来源是否真的进入了 FTS 索引（v2 表）？",
        ],
        "evidence_needed": [s["query"], "top8 候选路径", s["expected_source_path"]],
        "safe_next_step": "登记进离线评测回归集，人工确认来源覆盖与别名缺口",
        "must_not_do": "未经核验直接调整生产排序权重或索引内容",
        "case_ref": s["eval_id"],
        "_topic": topic, "_cat": cat,
    })

# 去重相似案例：同一主题+同一类别只保留最多 4 条
from collections import defaultdict
seen = defaultdict(int)
final = []
for c in cases:
    k = (c["_topic"], c["failure_class"])
    if seen[k] >= 4:
        continue
    seen[k] += 1
    final.append(c)

defs = [json.loads(l) for l in TRI.read_text(encoding="utf-8").splitlines() if l.strip()]
out = defs + final
for i, r in enumerate(out, 1):
    r["id"] = "triage-%06d" % i
    r.pop("_topic", None)
    r.pop("_cat", None)
with TRI.open("w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print("defs:", len(defs), "cases:", len(final), "total:", len(out))
print("case classes:", dict(Counter(r["failure_class"] for r in final)))
