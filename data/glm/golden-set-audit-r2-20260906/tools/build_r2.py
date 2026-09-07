#!/usr/bin/env python3
"""阶段 C：构建修正版黄金集 r2（仅收录 A 的 keep/rewrite + B 的 promote）。"""
import json
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/semantic-review-and-golden-set-20260906")
gold1 = {json.loads(l)["id"]: json.loads(l) for l in (SRC / "gold-eval-candidates.jsonl").read_text(encoding="utf-8").splitlines()}
audits = [json.loads(l) for l in (HERE.parent / "gold-audit.jsonl").read_text(encoding="utf-8").splitlines()]
bev = {json.loads(l)["source_eval_id"]: json.loads(l) for l in (HERE.parent / "no-evidence-audit.jsonl").read_text(encoding="utf-8").splitlines()}

rows = []
for a in audits:
    g = gold1[a["source_gold_id"]]
    if a["decision"] == "keep":
        rows.append({
            "id": None,
            "source_gold_id": g["id"],
            "source_eval_id": g["source_eval_id"],
            "question": g["question"],
            "category": g["category"],
            "topic": g["topic"],
            "difficulty": g["difficulty"],
            "expected_mode": g["expected_mode"],
            "expected_source_path": g["expected_source_path"],
            "expected_start_line": g["expected_start_line"],
            "expected_end_line": g["expected_end_line"],
            "expected_evidence_type": g["expected_evidence_type"],
            "aliases": g["aliases"],
            "dialogue_context": g["dialogue_context"],
            "selection_reason": "第二轮逐题人工复核保留（" + a["reason"][:80] + "）",
            "semantic_review_id": a["id"],
            "no_evidence_audit_id": None,
            "diagnostic_value": g["diagnostic_value"],
            "risk_notes": list(g["risk_notes"]) + list(a["risk_notes"]),
        })
    elif a["decision"] == "rewrite":
        rows.append({
            "id": None,
            "source_gold_id": g["id"],
            "source_eval_id": g["source_eval_id"],
            "question": a["rewrite_question"],
            "category": g["category"],
            "topic": g["topic"],
            "difficulty": g["difficulty"],
            "expected_mode": g["expected_mode"],
            "expected_source_path": g["expected_source_path"],
            "expected_start_line": g["expected_start_line"],
            "expected_end_line": g["expected_end_line"],
            "expected_evidence_type": g["expected_evidence_type"],
            "aliases": g["aliases"] + ([a["rewrite_question"][:24] + "…"] if a["rewrite_question"] else []),
            "dialogue_context": g["dialogue_context"],
            "selection_reason": "第二轮人工改写并重新打开来源核对通过（" + a["reason"][:80] + "）",
            "semantic_review_id": a["id"],
            "no_evidence_audit_id": None,
            "diagnostic_value": g["diagnostic_value"],
            "risk_notes": list(g["risk_notes"]) + list(a["risk_notes"]) + ["改写题：已二次核对来源片段，语义适配仍属候选"],
        })

# B 阶段 promote 的 knowledge 候选
pb = bev.get("eval-001701")
if pb and pb["decision"] == "promote_to_knowledge_candidate":
    pe = pb["promoted_evidence"]
    rows.append({
        "id": None,
        "source_gold_id": None,
        "source_eval_id": "eval-001701",
        "question": "Swift Concurrency 里 actor 的重入隔离细节能帮我讲讲吗？",
        "category": "answerable",
        "topic": "swift-interop",
        "difficulty": "medium",
        "expected_mode": "knowledge",
        "expected_source_path": pe["path"],
        "expected_start_line": pe["start_line"],
        "expected_end_line": pe["end_line"],
        "expected_evidence_type": "wwdc",
        "aliases": ["actor 重入", "actor reentrancy", "重入隔离", "await 后状态假设"],
        "dialogue_context": [],
        "selection_reason": "B 阶段按具体主张复核：10133 场次第 281-295 行直接解释 actor reentrancy 的成因与设计对策，可支撑该题（" + pb["evidence_summary"][:60] + "…）",
        "semantic_review_id": None,
        "no_evidence_audit_id": pb["id"],
        "diagnostic_value": "可暴露语义召回与生产查询规划问题：中文『重入隔离』与英文 reentrancy 的跨语言映射，以及 no_evidence 误判风险",
        "risk_notes": ["证据为英文逐字稿；561 行为辅助定位", "由 no_evidence 提升而来，生产判定需复核"],
    })

rows.sort(key=lambda r: (r["source_gold_id"] or "zzz-" + r["source_eval_id"]))
for i, r in enumerate(rows, 1):
    r["id"] = "gold-r2-%06d" % i
out = HERE.parent / "gold-eval-candidates-r2.jsonl"
with out.open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("r2 gold:", len(rows))
print("category:", dict(Counter(r["category"] for r in rows)))
print("mode:", dict(Counter(r["expected_mode"] for r in rows)))
print("topic:", dict(Counter(r["topic"] for r in rows)))
print("difficulty:", dict(Counter(r["difficulty"] for r in rows)))
print("etype:", dict(Counter(str(r["expected_evidence_type"]) for r in rows)))
print("from rewrite:", sum(1 for r in rows if "人工改写" in r["selection_reason"]))
