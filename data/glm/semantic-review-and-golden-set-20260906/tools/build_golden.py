#!/usr/bin/env python3
"""阶段 B：从 keep/verified-rewrite 审查结论构建小而硬的黄金评测候选集。"""
import json, re, glob
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/overnight-rag-evaluation-20260906")
OUT = HERE.parent / "gold-eval-candidates.jsonl"

ev = {}
for fp in sorted((SRC / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln); ev[r["id"]] = r
rev = {}
for ln in (HERE.parent / "semantic-review.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(ln); rev[r["source_eval_id"]] = r

_file_cache = {}
def lines_of(p):
    if p not in _file_cache:
        _file_cache[p] = Path(p).read_text(encoding="utf-8", errors="replace").split("\n")
    return _file_cache[p]

def tokens(x):
    t = [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", x) if len(w) >= 2]
    t += re.findall(r"[\u4e00-\u9fff]{2,}", x)
    return t

def coverage(toks, text):
    return (sum(1 for t in toks if t in text) / len(toks)) if toks else 0.0

DIAG = {
    "answerable": "可暴露召回与重排问题：检索是否命中预期小节、引用能否定位到该行区间",
    "comparison": "可暴露多主题证据合并与重排多样性问题：两个概念的证据能否同时进入 top-k",
    "symbol": "可暴露精确符号的 FTS/查询规划能力与源码块排序问题",
    "alias": "可暴露口语/别名/错拼改写下的词法召回缺口",
    "follow_up": "可暴露追问上下文继承与路由状态机问题",
    "no_evidence": "可暴露无证据判定的误答风险（是否被通用回答冒充）",
    "general": "可暴露 iOS 检索被闲聊误触发的路由风险",
    "cross_platform": "可暴露跨平台干扰下的路由边界与证据声明能力",
}
SEL_REASON = {
    "answerable": "语义审查确认锚定小节正文充分且题面自然独立，是知识召回与引用定位的硬校验样本",
    "comparison": "对比双方或单方内容在小节中有实测覆盖，保留为对比类硬样本",
    "symbol": "符号在源码/资料锚定区间实测存在，可硬校验符号级检索",
    "alias": "口语改写自然且概念锚点实测命中，考察别名维度",
    "follow_up": "追问依赖上一轮上下文（预期属性），锚定片段充分，考察追问路由",
    "no_evidence": "语料中无该主题可靠证据（人工策展），考察无证据判定",
    "general": "明显非 iOS 闲聊题，考察路由边界",
    "cross_platform": "iOS 侧证据锚定、非 iOS 侧按设计应声明缺失，考察跨平台干扰",
}

# 候选池
pool = []
for rid, rv in rev.items():
    e = ev[rid]
    if rv["decision"] == "keep":
        q = e["question"]
        verified = True
    elif rv["decision"] == "rewrite" and rv["rewrite_question"]:
        q = rv["rewrite_question"]
        # 再次核对：改写主语词在锚定区间中的覆盖
        text = "\n".join(lines_of(rv["source_path"])[rv["source_start_line"]-1:rv["source_end_line"]])
        verified = coverage(tokens(q), text) >= 0.5
    else:
        continue
    if not verified:
        continue
    score = {"high": 2, "medium": 1, "low": 0}[rv["confidence"]] + \
            {"strong": 2, "partial": 1, "weak": 0, "none": 0}[rv["semantic_fit"]] + \
            {"strong": 2, "partial": 1, "weak": 0}[rv["standalone_quality"]] + \
            (1 if e["difficulty"] == "hard" else 0)
    pool.append({"rid": rid, "rv": rv, "e": e, "q": q, "score": score})

# 配额与多样性
QUOTA = {"answerable": 78, "comparison": 24, "symbol": 28, "alias": 18,
         "follow_up": 16, "no_evidence": 16, "general": 8, "cross_platform": 8}
TOPIC_CAP = 22
pool.sort(key=lambda x: (-x["score"], x["rid"]))
cat_cnt, topic_cnt = Counter(), Counter()
chosen = []
for item in pool:
    e = item["e"]
    c = e["category"]
    if cat_cnt[c] >= QUOTA.get(c, 0):
        continue
    if topic_cnt[e["topic"]] >= TOPIC_CAP:
        continue
    chosen.append(item)
    cat_cnt[c] += 1
    topic_cnt[e["topic"]] += 1
    if len(chosen) >= 210:
        break

chosen.sort(key=lambda x: x["rid"])
gold = []
for i, item in enumerate(chosen, 1):
    rv, e, q = item["rv"], item["e"], item["q"]
    is_rewrite = rv["decision"] == "rewrite"
    gold.append({
        "id": "gold-%06d" % i,
        "source_eval_id": e["id"],
        "question": q,
        "category": e["category"],
        "topic": e["topic"],
        "difficulty": e["difficulty"],
        "expected_mode": rv["suggested_expected_mode"] or e["expected_mode"],
        "expected_source_path": rv["source_path"],
        "expected_start_line": rv["source_start_line"],
        "expected_end_line": rv["source_end_line"],
        "expected_evidence_type": e["expected_evidence_type"] if e["expected_mode"] == "knowledge" else None,
        "aliases": e["aliases"],
        "dialogue_context": e["dialogue_context"],
        "selection_reason": SEL_REASON.get(e["category"], "") + ("；题面为审查改写版" if is_rewrite else "；题面为原题"),
        "semantic_review_id": rv["id"],
        "diagnostic_value": DIAG.get(e["category"], ""),
        "risk_notes": list(rv["risk_notes"]) + (["改写题：改写后是否被该节完整回答需人工终审"] if is_rewrite else []),
    })

with OUT.open("w", encoding="utf-8") as f:
    for g in gold:
        f.write(json.dumps(g, ensure_ascii=False) + "\n")
print("gold:", len(gold))
print("category:", dict(Counter(g["category"] for g in gold)))
print("topic:", dict(Counter(g["topic"] for g in gold)))
print("mode:", dict(Counter(g["expected_mode"] for g in gold)))
print("difficulty:", dict(Counter(g["difficulty"] for g in gold)))
print("etype:", dict(Counter(str(g["expected_evidence_type"]) for g in gold)))
print("rewrite-based:", sum(1 for g in gold if "改写版" in g["selection_reason"]))
