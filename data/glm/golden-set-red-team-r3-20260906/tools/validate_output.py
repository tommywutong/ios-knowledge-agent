#!/usr/bin/env python3
"""r3 校验器：JSON/唯一 ID/路径/行号/跨文件引用 + 任务 D 的全部强制项。
特别地：内置 5 条已知反例的黑名单；不使用词汇重叠率作为任何保留依据。
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R2D = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-audit-r2-20260906")

errors = []
def err(m): errors.append(m)

def load(fp):
    rows = []
    for i, ln in enumerate(open(fp, encoding="utf-8"), 1):
        ln = ln.strip()
        if not ln: err(f"{fp}:{i} 空行"); continue
        try: rows.append(json.loads(ln))
        except Exception as e: err(f"{fp}:{i} JSON 非法: {e}")
    return rows

# ---------- 输入 ----------
r2 = {r["id"]: r for r in load(R2D / "gold-eval-candidates-r2.jsonl")}
BANNED_R2 = {"gold-r2-000036","gold-r2-000067","gold-r2-000068","gold-r2-000069","gold-r2-000071"}
BANNED_FRAGMENTS = ["到底会有几个 cell 活着", "两种格式，四点六倍", "什么是DRY原则", "概述」和「SOLID原则", "构建系统组成」和「编译优化-Xcode构建系统"]

# ---------- r3-audit.jsonl ----------
DEC = {"keep", "rewrite", "remove"}
audits = load(BASE / "r3-audit.jsonl")
a_by_r2 = {}
for r in audits:
    rid = r["id"]
    if rid in a_by_r2: err(f"r3-audit 重复 id {rid}")
    if r["source_r2_id"] not in r2: err(f"{rid} source_r2_id 不存在")
    if r["source_eval_id"] != r2[r["source_r2_id"]]["source_eval_id"]: err(f"{rid} eval id 与 r2 不一致")
    if r["decision"] not in DEC: err(f"{rid} decision 非法")
    if r["natural_query_test"] not in {"pass","fail"}: err(f"{rid} natural_query_test 非法")
    if r["comparison_validity"] not in {"not_applicable","valid","invalid"}: err(f"{rid} comparison_validity 非法")
    if r["source_sufficiency"] not in {"strong","partial","weak","not_applicable"}: err(f"{rid} source_sufficiency 非法")
    if r["decision"] == "rewrite" and not r.get("rewrite_question"): err(f"{rid} rewrite 缺改写题")
    if r["decision"] != "rewrite" and r.get("rewrite_question") is not None: err(f"{rid} 非 rewrite 不得有改写题")
    if r["decision"] in ("keep","rewrite"):
        for f in ("normalized_subject","answer_boundary","source_support_summary","technical_intent"):
            if not r.get(f): err(f"{rid} keep/rewrite 缺 {f}")
    if r["decision"] == "remove" and not r.get("reason"): err(f"{rid} remove 缺 reason")
    if r["comparison_validity"] == "invalid" and r["decision"] in ("keep","rewrite"):
        err(f"{rid} comparison_invalid 却被保留")
    a_by_r2[r["source_r2_id"]] = r
if len(audits) != len(r2): err(f"r3-audit 覆盖 {len(audits)} != r2 {len(r2)}")
audit_by_id = {r["id"]: r for r in audits}

# ---------- no-evidence-audit-r3.jsonl ----------
nev = load(BASE / "no-evidence-audit-r3.jsonl")
nev_by_r2 = {}
for r in nev:
    if r["id"] in nev_by_r2: err(f"no-evidence-audit-r3 重复 id {r['id']}")
    nev_by_r2[r["source_r2_id"]] = r
    if r["decision"] not in {"retain_no_evidence","promote_to_knowledge_candidate","remove"}:
        err(f"{r['id']} decision 非法")
    if not r.get("specific_claim_checked") or not r.get("evidence_search_scope") or not r.get("reason"):
        err(f"{r['id']} 缺必填字段")
    if r["decision"] == "promote_to_knowledge_candidate":
        pe = r.get("promoted_evidence")
        if not pe or not Path(pe["path"]).is_file(): err(f"{r['id']} promote 证据缺失")
# r2 的 20 条 no_evidence 必须全部有 r3 审计
r2_noev = {g["id"] for g in r2.values() if g["expected_mode"] == "no_evidence"}
if set(nev_by_r2) != r2_noev:
    err(f"no-evidence-audit-r3 覆盖不符: 缺 {r2_noev - set(nev_by_r2)} 多 {set(nev_by_r2) - r2_noev}")

# ---------- gold-eval-candidates-r3.jsonl ----------
FORBIDDEN = re.compile(r"目录|这篇在系列中的位置|本篇|本节|该系列|系列中|Part\s*\d|第[一二三四五六七八九十\d]+\s*(部分|篇|章)|draft:|\d{4}-\d{2}-\d{2}|到底会有几个|是什么？」和「|」和「概述」")
r3 = load(BASE / "gold-eval-candidates-r3.jsonl")
r3_ids = set()
for g in r3:
    gid = g["id"]
    if gid in r3_ids: err(f"r3 重复 id {gid}")
    r3_ids.add(gid)
    a = audit_by_id.get(g.get("semantic_review_id"))
    if a is None: err(f"{gid} 缺 r3 审查记录"); continue
    if a["source_r2_id"] != g["source_r2_id"]: err(f"{gid} source_r2_id 与审查记录不一致")
    if a["decision"] == "remove": err(f"{gid} 引用了 remove 结论")
    if a["decision"] == "keep" and g["question"] != r2[g["source_r2_id"]]["question"]: err(f"{gid} keep 题面被改动")
    if a["decision"] == "rewrite" and g["question"] != a["rewrite_question"]: err(f"{gid} 改写题与审查记录不一致")
    # 5 条已知反例绝不进入 r3
    if g["source_r2_id"] in BANNED_R2: err(f"{gid} 收录了已知反例 {g['source_r2_id']}")
    for frag in BANNED_FRAGMENTS:
        if frag in g["question"]: err(f"{gid} 题面含已知反例碎片: {frag}")
    if FORBIDDEN.search(g["question"]): err(f"{gid} 题面含文档结构残留: {FORBIDDEN.search(g['question']).group(0)}")
    if g["expected_mode"] == "knowledge":
        p = g.get("expected_source_path")
        if not p or not Path(p).is_file(): err(f"{gid} knowledge 路径不存在")
        else:
            n = len(Path(p).read_text(encoding='utf-8', errors='replace').split('\n'))
            if not (1 <= g["expected_start_line"] <= g["expected_end_line"] <= n): err(f"{gid} 行号非法")
    else:
        if g.get("expected_source_path") is not None: err(f"{gid} 非知识条目不得携带来源")
    if g["category"] == "comparison" and a["comparison_validity"] != "valid":
        err(f"{gid} comparison 题未通过有效性校验")
    if g["expected_mode"] == "no_evidence":
        if not g.get("no_evidence_audit_id") or g["no_evidence_audit_id"] not in {x["id"] for x in nev}:
            err(f"{gid} no_evidence 缺 r3 无证据审查关联")
    if not all(g.get(f) for f in ("normalized_subject","answer_boundary","source_support_summary","technical_intent" if "technical_intent" in g else "selection_reason")):
        err(f"{gid} 缺红队必要字段")

print(f"r3-audit: {len(audits)} | no-evidence-audit-r3: {len(nev)} | r3 gold: {len(r3)}")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors[:30]: print(" -", e)
    sys.exit(1)
print("ALL CHECKS PASSED")
