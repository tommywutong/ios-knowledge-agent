#!/usr/bin/env python3
"""校验种子池输出：JSON/唯一 ID/真实路径/行号/题目-来源映射/每小节≤2题/topic 配额/结构残留。"""
import json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
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

CATS = {"answerable", "symbol", "alias", "comparison", "follow_up"}
TOPICS = {"network", "persistence", "build-startup", "swift-interop"}
QUOTA = {"network": (20, 30), "persistence": (15, 25), "build-startup": (20, 30), "swift-interop": (15, 25)}
FORBIDDEN = re.compile(r"「目录」|『目录』|目录」|这篇在系列中的位置|本篇|本节|该系列|系列中|Part\s*\d|第[一二三四五六七八九十\d]+\s*(部分|篇|章)|draft:|\d{4}-\d{2}(-\d{2})?|\d{2}:\d{2}|根据你的资料|资料里有哪些关键细节|概述」")

seeds = load(BASE / "seed-eval-candidates.jsonl")
smap = load(BASE / "source-map.jsonl")
rej = load(BASE / "rejected-seed-ideas.jsonl")

# 唯一 ID
for name, rows in [("seeds", seeds), ("source-map", smap), ("rejected", rej)]:
    ids = set()
    for r in rows:
        if r.get("id") in ids: err(f"{name} 重复 id {r.get('id')}")
        ids.add(r.get("id"))

# seeds
sec_count = {}
sec_keys = {(s["source_path"], s["start_line"], s["end_line"]): s for s in smap}
tc = Counter()
for g in seeds:
    gid = g["id"]
    if g["category"] not in CATS: err(f"{gid} category 非法")
    if g["topic"] not in TOPICS: err(f"{gid} topic 非法")
    tc[g["topic"]] += 1
    if g["expected_mode"] != "knowledge": err(f"{gid} 种子题必须为 knowledge")
    p = g["expected_source_path"]
    if not p or not Path(p).is_file(): err(f"{gid} 路径不存在"); continue
    n = len(Path(p).read_text(encoding='utf-8', errors='replace').split('\n'))
    if not (1 <= g["expected_start_line"] <= g["expected_end_line"] <= n): err(f"{gid} 行号非法")
    if g["category"] == "follow_up" and not g.get("dialogue_context"): err(f"{gid} follow_up 缺上下文")
    if g["category"] != "follow_up" and g.get("dialogue_context"): err(f"{gid} 非 follow_up 不得有上下文")
    for f in ("normalized_subject", "answer_boundary", "source_support_summary",
              "why_this_is_a_real_user_question", "diagnostic_value", "question"):
        if not g.get(f): err(f"{gid} 缺 {f}")
    if FORBIDDEN.search(g["question"]): err(f"{gid} 题面含结构残留/模板句: {FORBIDDEN.search(g['question']).group(0)}")
    key = (p, g["expected_start_line"], g["expected_end_line"])
    sec_count[key] = sec_count.get(key, 0) + 1
    if sec_count[key] > 2: err(f"{gid} 来源小节超过 2 题")
    sm = sec_keys.get(key)
    if sm is None: err(f"{gid} 无对应 source-map 记录")
    elif gid not in sm["question_ids"]: err(f"{gid} 未登记进 source-map.question_ids")
    if not g.get("aliases"): err(f"{gid} 缺 aliases")

for topic, (lo, hi) in QUOTA.items():
    if not (lo <= tc.get(topic, 0) <= hi):
        err(f"topic {topic} 题数 {tc.get(topic,0)} 超出配额 {lo}-{hi}")

# source-map
for s in smap:
    p = Path(s["source_path"])
    if not p.is_file(): err(f"{s['id']} 路径不存在"); continue
    n = len(p.read_text(encoding='utf-8', errors='replace').split('\n'))
    if not (1 <= s["start_line"] <= s["end_line"] <= n): err(f"{s['id']} 行号非法")
    if not s.get("actual_concepts") or not s.get("why_selected"): err(f"{s['id']} 缺概念/选入理由")
    for qid in s["question_ids"]:
        if qid not in {g["id"] for g in seeds}: err(f"{s['id']} 引用不存在的题目 {qid}")

# rejected
KINDS = {"document_structure", "insufficient_evidence", "concept_duplicate", "unnatural_question",
         "anchor_missing", "thin_section", "section_quota"}
for r in rej:
    if r.get("kind") not in KINDS: err(f"rejected {r.get('id')} kind 非法")
    if not r.get("detail") or not r.get("idea"): err(f"rejected 缺 idea/detail")

print(f"seeds: {len(seeds)} | source-map: {len(smap)} | rejected: {len(rej)} | topics: {dict(tc)}")
if errors:
    print(f"ERRORS: {len(errors)}")
    for e in errors[:20]: print(" -", e)
    sys.exit(1)
print("ALL CHECKS PASSED")
