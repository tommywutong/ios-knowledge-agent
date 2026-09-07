#!/usr/bin/env python3
"""任务 C：构建 r3 强集（仅 keep + 已验证 rewrite）。"""
import json
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
R2D = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-audit-r2-20260906")
r2 = {g["id"]: g for g in (json.loads(l) for l in (R2D / "gold-eval-candidates-r2.jsonl").read_text(encoding="utf-8").splitlines())}
audits = [json.loads(l) for l in (HERE.parent / "r3-audit.jsonl").read_text(encoding="utf-8").splitlines()]
bev = {r["source_r2_id"]: r for r in (json.loads(l) for l in (HERE.parent / "no-evidence-audit-r3.jsonl").read_text(encoding="utf-8").splitlines())}

rows = []
for a in sorted(audits, key=lambda x: x["source_r2_id"]):
    if a["decision"] not in ("keep", "rewrite"):
        continue
    g = r2[a["source_r2_id"]]
    cat = g["category"]
    # 改写消解了对比关系的题，类别随题面改为 answerable
    if a["decision"] == "rewrite" and cat == "comparison" and a["comparison_validity"] == "not_applicable":
        cat = "answerable"
    rows.append({
        "id": "gold-r3-%06d" % (len(rows) + 1),
        "source_r2_id": g["id"],
        "source_eval_id": g["source_eval_id"],
        "question": a["rewrite_question"] if a["decision"] == "rewrite" else g["question"],
        "category": cat,
        "topic": g["topic"],
        "difficulty": g["difficulty"],
        "expected_mode": g["expected_mode"],
        "expected_source_path": g["expected_source_path"],
        "expected_start_line": g["expected_start_line"],
        "expected_end_line": g["expected_end_line"],
        "expected_evidence_type": g["expected_evidence_type"],
        "aliases": g["aliases"] + ([a["rewrite_question"][:20] + "…"] if a["decision"] == "rewrite" else []),
        "dialogue_context": g["dialogue_context"],
        "normalized_subject": a["normalized_subject"],
        "answer_boundary": a["answer_boundary"],
        "source_support_summary": a["source_support_summary"],
        "selection_reason": ("r3 红队改写（来源二次核对通过）" if a["decision"] == "rewrite" else "r3 红队保留"),
        "semantic_review_id": a["id"],
        "no_evidence_audit_id": bev[g["id"]]["id"] if g["expected_mode"] == "no_evidence" and g["id"] in bev else None,
        "diagnostic_value": g["diagnostic_value"],
        "risk_notes": list(g["risk_notes"]) + list(a["risk_notes"]),
    })
out = HERE.parent / "gold-eval-candidates-r3.jsonl"
with out.open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("r3 gold:", len(rows))
print("decision-origin:", dict(Counter("rewrite" if "改写" in r["selection_reason"] else "keep" for r in rows)))
print("category:", dict(Counter(r["category"] for r in rows)))
print("mode:", dict(Counter(r["expected_mode"] for r in rows)))
print("difficulty:", dict(Counter(r["difficulty"] for r in rows)))
print("etype:", dict(Counter(str(r["expected_evidence_type"]) for r in rows)))
print("topic:", dict(Counter(r["topic"] for r in rows)))
