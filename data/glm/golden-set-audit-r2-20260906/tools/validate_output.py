#!/usr/bin/env python3
"""校验本批次全部输出：JSON 合法、唯一 ID、跨文件引用、来源真实性、禁用结构残留、
r2 黄金集可回溯性、promote 证据行号。"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R1 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/semantic-review-and-golden-set-20260906")

errors = []
def err(m): errors.append(m)

def load(fp):
    rows = []
    for i, ln in enumerate(open(fp, encoding="utf-8"), 1):
        ln = ln.strip()
        if not ln:
            err(f"{fp}:{i} 空行"); continue
        try:
            rows.append(json.loads(ln))
        except Exception as e:
            err(f"{fp}:{i} JSON 非法: {e}")
    return rows

# 旧黄金集（只读输入）
gold1 = {r["id"]: r for r in load(R1 / "gold-eval-candidates.jsonl")}

# ---------- gold-audit.jsonl ----------
DEC = {"keep", "rewrite", "remove"}
FIT = {"strong", "partial", "weak", "not_applicable"}
QUAL = {"strong", "partial", "weak"}
RFIT = {"correct", "questionable", "wrong"}
CONF = {"low", "medium", "high"}
audits = load(BASE / "gold-audit.jsonl")
audit_ids = set()
for r in audits:
    rid = r["id"]
    if rid in audit_ids: err(f"gold-audit 重复 id {rid}")
    audit_ids.add(rid)
    if r["source_gold_id"] not in gold1: err(f"{rid} source_gold_id 不存在")
    elif gold1[r["source_gold_id"]]["source_eval_id"] != r["source_eval_id"]:
        err(f"{rid} eval id 与旧黄金集不一致")
    if r["decision"] not in DEC or r["standalone_quality"] not in QUAL or \
       r["evidence_fit"] not in FIT or r["routing_fit"] not in RFIT or r["confidence"] not in CONF:
        err(f"{rid} 枚举非法")
    if r["decision"] == "rewrite" and not r.get("rewrite_question"): err(f"{rid} rewrite 缺改写题")
    if r["decision"] != "rewrite" and r.get("rewrite_question") is not None: err(f"{rid} 非 rewrite 不得有改写题")
    if not r.get("reason"): err(f"{rid} 缺 reason")
audit_by_gold = {r["source_gold_id"]: r for r in audits}
if len(audits) != len(gold1):
    err(f"gold-audit 覆盖数 {len(audits)} != 旧黄金集 {len(gold1)}")

# ---------- no-evidence-audit.jsonl ----------
EXPECT_7 = {"eval-001700","eval-001701","eval-001702","eval-001703","eval-001712","eval-001754","eval-001790"}
b_rows = load(BASE / "no-evidence-audit.jsonl")
b_ids = set()
if {r["source_eval_id"] for r in b_rows} != EXPECT_7:
    err("no-evidence-audit 未覆盖指定的 7 条候选")
for r in b_rows:
    if r["id"] in b_ids: err(f"no-evidence-audit 重复 id {r['id']}")
    b_ids.add(r["id"])
    if r["decision"] not in {"retain_no_evidence", "promote_to_knowledge_candidate", "remove"}:
        err(f"{r['id']} decision 非法")
    if not r.get("question_aspect_checked") or not r.get("evidence_paths_checked") or not r.get("reason"):
        err(f"{r['id']} 缺必填字段")
    if r["decision"] == "promote_to_knowledge_candidate":
        pe = r.get("promoted_evidence")
        if not pe: err(f"{r['id']} promote 缺 promoted_evidence")
        else:
            p = Path(pe["path"])
            if not p.is_file(): err(f"{r['id']} promote 证据路径不存在")
            elif not (1 <= pe["start_line"] <= pe["end_line"] <= len(p.read_text(encoding='utf-8', errors='replace').split('\n'))):
                err(f"{r['id']} promote 证据行号非法")

# ---------- gold-eval-candidates-r2.jsonl ----------
FORBIDDEN = re.compile(r"目录|这篇在系列中的位置|本篇|本节|该系列|系列中|Part\s*\d|第[一二三四五六七八九十\d]+\s*(部分|篇|章)|draft:|（\d{4}）|\d{4}-\d{2}-\d{2}")
r2 = load(BASE / "gold-eval-candidates-r2.jsonl")
r2_ids = set()
if not (160 <= len(r2) <= 220):
    err(f"r2 黄金集规模 {len(r2)} 超出 160-220")
audit_by_id = {r["id"]: r for r in audits}
b_by_id = {r["id"]: r for r in b_rows}
for g in r2:
    gid = g["id"]
    if gid in r2_ids: err(f"r2 重复 id {gid}")
    r2_ids.add(gid)
    if g["source_gold_id"] is not None:
        a = audit_by_id.get(g.get("semantic_review_id"))
        if a is None: err(f"{gid} 缺可回溯的审查记录")
        else:
            if a["source_gold_id"] != g["source_gold_id"]: err(f"{gid} source_gold_id 与审查记录不一致")
            if a["decision"] == "remove": err(f"{gid} 引用了 remove 的审查结论")
            if a["decision"] == "keep" and g["question"] != gold1[g["source_gold_id"]]["question"]:
                err(f"{gid} keep 题面被改动")
            if a["decision"] == "rewrite" and g["question"] != a["rewrite_question"]:
                err(f"{gid} 改写题与审查记录不一致")
    else:
        b = b_by_id.get(g.get("no_evidence_audit_id"))
        if b is None or b["decision"] != "promote_to_knowledge_candidate":
            err(f"{gid} 无 source_gold_id 的条目必须引用 promote 审查记录")
    if g["expected_mode"] == "knowledge":
        p = g.get("expected_source_path")
        if not p or not Path(p).is_file(): err(f"{gid} knowledge 路径不存在")
        else:
            n = len(Path(p).read_text(encoding='utf-8', errors='replace').split('\n'))
            if not (1 <= g["expected_start_line"] <= g["expected_end_line"] <= n):
                err(f"{gid} 行号非法")
        if g.get("expected_evidence_type") not in {"note","doc","wwdc","blog","source_code"}:
            err(f"{gid} evidence_type 非法")
    else:
        if g.get("expected_source_path") is not None or g.get("expected_evidence_type") is not None:
            err(f"{gid} 非知识条目不得携带来源")
    if FORBIDDEN.search(g["question"]):
        err(f"{gid} 题面含文档结构残留: {FORBIDDEN.search(g['question']).group(0)}")
    if g["category"] in ("no_evidence",):
        if g["source_eval_id"] in EXPECT_7:
            b = next((x for x in b_rows if x["source_eval_id"] == g["source_eval_id"]), None)
            if not b or b["decision"] != "retain_no_evidence":
                err(f"{gid} no_evidence 条目未按 B 阶段结论处理")
    if not g.get("diagnostic_value") or not g.get("selection_reason"):
        err(f"{gid} 缺 selection_reason/diagnostic_value")

print(f"gold-audit: {len(audits)} | no-evidence-audit: {len(b_rows)} | r2 gold: {len(r2)}")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors[:30]: print(" -", e)
    sys.exit(1)
print("ALL CHECKS PASSED")
