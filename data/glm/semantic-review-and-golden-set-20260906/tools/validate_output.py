#!/usr/bin/env python3
"""阶段 E：校验本目录全部 JSONL 的合法性、唯一 ID、跨文件引用、字段允许值、来源存在性。"""
import json, glob, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/overnight-rag-evaluation-20260906")

errors = []
def err(msg): errors.append(msg)

def load(fp):
    rows = []
    with open(fp, encoding="utf-8") as f:
        for i, ln in enumerate(f, 1):
            ln = ln.strip()
            if not ln:
                err(f"{fp}:{i} 空行"); continue
            try:
                rows.append(json.loads(ln))
            except Exception as e:
                err(f"{fp}:{i} JSON 非法: {e}")
    return rows

def uniq(rows, fp, key="id"):
    ids = set()
    for r in rows:
        if r.get("id") in ids:
            err(f"{fp} 重复 id: {r.get('id')}")
        ids.add(r.get("id"))
    return ids

def check_lines(fp, r, path_key, s_key, e_key, allow_null=True):
    p, s, e = r.get(path_key), r.get(s_key), r.get(e_key)
    if p is None:
        if not allow_null:
            err(f"{fp} {r.get('id')} 来源路径缺失")
        return
    if not os.path.exists(p):
        err(f"{fp} {r.get('id')} 路径不存在: {p}")
        return
    if s is None or e is None or not (1 <= s <= e):
        err(f"{fp} {r.get('id')} 行号非法: {s}-{e}")
    else:
        n = len(open(p, encoding="utf-8", errors="replace").read().split("\n"))
        if e > n:
            err(f"{fp} {r.get('id')} 行号超出文件（{e} > {n}）")

# ---------- 输入 ----------
evals = {}
for fp in sorted(glob.glob(str(SRC / "eval-candidates/*.jsonl"))):
    for r in load(fp):
        evals[r["id"]] = r
alias_ids = {r["id"] for r in load(SRC / "terminology-aliases.jsonl")}
qf_ids = {r["id"] for r in load(SRC / "quality-findings.jsonl")}

# ---------- semantic-review.jsonl ----------
DEC = {"keep", "rewrite", "reject"}
FIT = {"strong", "partial", "weak", "none"}
QUAL = {"strong", "partial", "weak"}
RFIT = {"correct", "questionable", "wrong"}
CONF = {"low", "medium", "high"}
MODES = {"knowledge", "no_evidence", "general"}
rev = load(BASE / "semantic-review.jsonl")
rev_ids = uniq(rev, "semantic-review.jsonl")
rev_by_id = {}
for r in rev:
    rid = r.get("id")
    rev_by_id[rid] = r
    if r["source_eval_id"] not in evals:
        err(f"semantic-review {rid} 引用不存在的 eval {r['source_eval_id']}")
    if r["decision"] not in DEC or r["semantic_fit"] not in FIT or r["standalone_quality"] not in QUAL \
       or r["routing_fit"] not in RFIT or r["confidence"] not in CONF:
        err(f"semantic-review {rid} 枚举值非法")
    if r["decision"] == "rewrite" and not r.get("rewrite_question"):
        err(f"semantic-review {rid} rewrite 缺改写题")
    if r["decision"] in ("keep", "reject") and r.get("rewrite_question") is not None:
        err(f"semantic-review {rid} {r['decision']} 不应有改写题")
    if r.get("suggested_expected_mode") is not None and r["suggested_expected_mode"] not in MODES:
        err(f"semantic-review {rid} suggested_expected_mode 非法")
    if not r.get("reviewed_excerpt_summary") or len(r["reviewed_excerpt_summary"]) > 200:
        err(f"semantic-review {rid} reviewed_excerpt_summary 缺失或超长")
    if r["source_path"] is not None:
        check_lines("semantic-review.jsonl", r, "source_path", "source_start_line", "source_end_line")

# ---------- gold-eval-candidates.jsonl ----------
gold = load(BASE / "gold-eval-candidates.jsonl")
gold_ids = uniq(gold, "gold-eval-candidates.jsonl")
CATS = {"answerable", "symbol", "alias", "comparison", "follow_up", "no_evidence", "general", "cross_platform"}
for g in gold:
    gid = g["id"]
    if g["source_eval_id"] not in evals:
        err(f"gold {gid} 引用不存在的 eval")
    rv = rev_by_id.get(g.get("semantic_review_id"))
    if rv is None:
        err(f"gold {gid} 引用不存在的 review {g.get('semantic_review_id')}")
        continue
    if rv["decision"] == "reject":
        err(f"gold {gid} 引用了 reject 的审查结论 {rv['id']}")
    if rv["decision"] == "rewrite":
        if g["question"] != rv["rewrite_question"]:
            err(f"gold {gid} 改写题与审查记录不一致")
    elif g["question"] != evals[g["source_eval_id"]]["question"]:
        err(f"gold {gid} keep 条目题面被改动")
    if g["category"] not in CATS or g["difficulty"] not in {"easy", "medium", "hard"} or g["expected_mode"] not in MODES:
        err(f"gold {gid} 枚举非法")
    if not g.get("selection_reason") or not g.get("diagnostic_value"):
        err(f"gold {gid} 缺 selection_reason/diagnostic_value")
    if g["expected_mode"] == "knowledge":
        check_lines("gold-eval-candidates.jsonl", g, "expected_source_path", "expected_start_line", "expected_end_line", allow_null=False)
        if g.get("expected_evidence_type") not in {"note", "doc", "wwdc", "blog", "source_code"}:
            err(f"gold {gid} evidence_type 非法")
    else:
        if g.get("expected_source_path") is not None or g.get("expected_start_line") is not None \
           or g.get("expected_end_line") is not None or g.get("expected_evidence_type") is not None:
            err(f"gold {gid} 非知识条目不得携带来源")
    if g["category"] == "follow_up" and not g.get("dialogue_context"):
        err(f"gold {gid} 追问缺 dialogue_context")
    if len(gold) < 160 or len(gold) > 220:
        pass

if not (160 <= len(gold) <= 220):
    err(f"黄金集规模 {len(gold)} 超出 160-220")

# ---------- query-gap-report.jsonl ----------
LAYERS = {"alias", "query_planning", "fts_lexical_recall", "semantic_recall", "rerank", "source_coverage", "routing", "unknown"}
gaps = load(BASE / "query-gap-report.jsonl")
uniq(gaps, "query-gap-report.jsonl")
for r in gaps:
    if r["likely_layer"] not in LAYERS or r["priority"] not in {"P0", "P1", "P2"}:
        err(f"gap {r['id']} 枚举非法")
    if not r.get("evidence_refs"):
        err(f"gap {r['id']} 缺 evidence_refs")
    for ref in r["evidence_refs"]:
        m = re.match(r"^(eval|alias|quality|gold|review|gap|qfollow)-\d+$", ref)
        if m:
            kind = m.group(1)
            ok = {"eval": evals, "alias": {i: 1 for i in alias_ids}, "quality": {i: 1 for i in qf_ids},
                  "gold": gold_ids, "review": rev_ids, "gap": {r2["id"] for r2 in gaps},
                  "qfollow": {1: 1}}.get(kind)
            if ok is not None and ref not in ok:
                err(f"gap {r['id']} 引用不存在的 {ref}")

# ---------- quality-followup.jsonl ----------
acts = {"review_only", "exclude_candidate", "add_alias", "split_chunk_candidate", "manual_source_review"}
qfol = load(BASE / "quality-followup.jsonl")
uniq(qfol, "quality-followup.jsonl")
for r in qfol:
    if r["recommended_action"] not in acts or r["confidence"] not in CONF:
        err(f"qfollow {r['id']} 枚举非法")
    if not os.path.exists(r["source_path"]):
        err(f"qfollow {r['id']} 路径不存在: {r['source_path']}")
    elif not (1 <= r["start_line"] <= r["end_line"]):
        err(f"qfollow {r['id']} 行号非法")
    for rid in r.get("related_eval_ids", []):
        if rid not in evals:
            err(f"qfollow {r['id']} 引用不存在的 eval {rid}")

print(f"semantic-review: {len(rev)} | gold: {len(gold)} | gaps: {len(gaps)} | quality-followup: {len(qfol)}")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors[:40]:
        print(" -", e)
    sys.exit(1)
print("ALL CHECKS PASSED")
