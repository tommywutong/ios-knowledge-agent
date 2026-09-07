#!/usr/bin/env python3
"""r4 校验器：清单与审计的合法性、真实性、跨文件回溯、反例黑名单。"""
import json, re, sys
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R3D = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-red-team-r3-20260906")
SD = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/undercovered-topic-seeds-20260906")

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
r3 = {r["id"]: r for r in load(R3D / "gold-eval-candidates-r3.jsonl")}
seeds = {r["id"]: r for r in load(SD / "seed-eval-candidates.jsonl")}
sba = {r["source_seed_id"]: r for r in load(BASE / "seed-boundary-audit.jsonl")}
nev3 = {r["id"]: r for r in load(R3D.parent / "golden-set-red-team-r3-20260906/no-evidence-audit-r3.jsonl")} if False else {}
nev3 = {r["id"]: r for r in load(R3D / "no-evidence-audit-r3.jsonl")}
nev3_by_r2 = {r["source_r2_id"]: r for r in nev3.values()}

# ---------- seed-boundary-audit.jsonl ----------
DEC = {"keep", "rewrite", "remove"}
SCOPES = {"Apple_source", "iOS_public_api", "macOS_observation", "personal_experiment", "mixed_evidence", "unclear"}
a_by_seed = {}
for r in load(BASE / "seed-boundary-audit.jsonl"):
    rid = r["id"]
    if rid in a_by_seed: err(f"seed-boundary-audit 重复 id {rid}")
    a_by_seed[r["source_seed_id"]] = r
    if r["source_seed_id"] not in seeds: err(f"{rid} source_seed_id 不存在")
    if r["decision"] not in DEC: err(f"{rid} decision 非法")
    if r["evidence_scope"] not in SCOPES: err(f"{rid} evidence_scope 非法")
    if r["natural_query_test"] not in {"pass", "fail"}: err(f"{rid} natural_query_test 非法")
    if not isinstance(r.get("must_state_limitations"), bool): err(f"{rid} must_state_limitations 非布尔")
    if r["decision"] == "rewrite" and not r.get("rewrite_question"): err(f"{rid} rewrite 缺改写题")
    if r["decision"] != "rewrite" and r.get("rewrite_question") is not None: err(f"{rid} 非 rewrite 不得有改写题")
    if r["decision"] in ("keep", "rewrite"):
        for f in ("normalized_subject", "answer_boundary", "reason"):
            if not r.get(f): err(f"{rid} 缺 {f}")
    if r["must_state_limitations"] and not r.get("required_answer_constraints"):
        err(f"{rid} must_state=True 但无 required_answer_constraints")
if len(a_by_seed) != len(seeds): err(f"seed-boundary-audit 覆盖 {len(a_by_seed)} != seeds {len(seeds)}")

# ---------- production-eval-manifest-candidates.jsonl ----------
FORBIDDEN = re.compile(r"「目录」|『目录』|目录」|这篇在系列中的位置|本篇|本节|Part\s*\d|第[一二三四五六七八九十\d]+\s*(部分|篇|章)|draft:|\d{4}-\d{2}")
LAYER = {"routing", "query_planning", "lexical_recall", "semantic_recall", "rerank_diversity", "citation_validation", "follow_up_context"}
qnorm = set()
rows = load(BASE / "production-eval-manifest-candidates.jsonl")
for g in rows:
    gid = g["id"]
    if g["origin"] not in {"r3_gold", "undercovered_seed"}: err(f"{gid} origin 非法")
    if g["diagnostic_layer"] not in LAYER: err(f"{gid} diagnostic_layer 非法")
    if g["priority"] not in {"P0", "P1", "P2"}: err(f"{gid} priority 非法")
    k = re.sub(r"\s", "", g["question"])[:50]
    if k in qnorm: err(f"{gid} 题意重复: {g['question'][:40]}")
    qnorm.add(k)
    if FORBIDDEN.search(g["question"]): err(f"{gid} 题面结构残留")
    # 跨文件回溯
    if g["origin"] == "r3_gold":
        src = r3.get(g["origin_id"])
        if src is None: err(f"{gid} origin_id 不在 r3 强集"); continue
        if g["question"] != src["question"]: err(f"{gid} 题面与 r3 强集不一致")
        if g["category"] != src["category"] or g["expected_mode"] != src["expected_mode"]:
            err(f"{gid} 类别/模式与 r3 不一致")
    else:
        src = seeds.get(g["origin_id"])
        if src is None: err(f"{gid} origin_id 不在种子池"); continue
        a = a_by_seed.get(g["origin_id"])
        if a is None: err(f"{gid} 缺 seed-boundary-audit 记录"); continue
        if a["decision"] == "remove": err(f"{gid} 引用了 remove 的种子")
        expect_q = a.get("rewrite_question") or src["question"]
        if g["question"] != expect_q: err(f"{gid} 题面与种子/改写不一致")
        if a["must_state_limitations"] and not g.get("answer_constraints"):
            err(f"{gid} 平台/实验局限题缺 answer_constraints")
    # 来源与行号
    if g["expected_mode"] == "knowledge":
        p = g.get("expected_source_path")
        if not p or not Path(p).is_file(): err(f"{gid} knowledge 路径不存在"); continue
        n = len(Path(p).read_text(encoding='utf-8', errors='replace').split('\n'))
        if not (1 <= g["expected_start_line"] <= g["expected_end_line"] <= n): err(f"{gid} 行号非法")
        if not g.get("evaluation_assertions"): err(f"{gid} 缺 evaluation_assertions")
    else:
        if g.get("expected_source_path") is not None: err(f"{gid} 非知识条目不得携带来源")
    # no_evidence 审查依据
    if g["expected_mode"] == "no_evidence":
        ref = g.get("no_evidence_audit_ref")
        if not ref or ref not in nev3: err(f"{gid} no_evidence 缺有效审查引用")
        elif nev3[ref]["decision"] != "retain_no_evidence": err(f"{gid} 审查结论非 retain")
        elif not any("同主题泛资料" in x for x in g.get("evaluation_assertions", [])):
            err(f"{gid} no_evidence 断言缺少『不得用同主题泛资料冒充』")

# P0 覆盖检查
p0 = [g for g in rows if g["priority"] == "P0"]
def has(pred): return any(pred(g) for g in p0)
checks = {
    "actor reentrancy": has(lambda g: "重入" in g["question"]),
    "精确符号": has(lambda g: g["diagnostic_layer"] == "query_planning" and g["category"] == "symbol"),
    "no-evidence": has(lambda g: g["expected_mode"] == "no_evidence"),
    "追问": has(lambda g: g["category"] == "follow_up"),
    "跨平台干扰": has(lambda g: g["category"] == "cross_platform"),
    "SQLite/WAL": has(lambda g: "WAL" in g["question"] or "900 倍" in g["question"]),
    "dyld 平台边界": has(lambda g: "dyld" in g["question"].lower()),
}
for k, ok in checks.items():
    if not ok: err(f"P0 未覆盖: {k}")

print(f"seed-boundary-audit: {len(a_by_seed)} | manifest: {len(rows)} | P0: {len(p0)}")
print("manifest priority:", dict(Counter(g["priority"] for g in rows)),
      "| origin:", dict(Counter(g["origin"] for g in rows)),
      "| mode:", dict(Counter(g["expected_mode"] for g in rows)))
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors[:25]: print(" -", e)
    sys.exit(1)
print("ALL CHECKS PASSED")
