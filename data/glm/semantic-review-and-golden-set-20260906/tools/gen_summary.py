#!/usr/bin/env python3
"""生成 semantic-review-summary.md：统计 + 代表性案例索引。"""
import json, random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/overnight-rag-evaluation-20260906")
rows = [json.loads(l) for l in (HERE.parent / "semantic-review.jsonl").read_text(encoding="utf-8").splitlines()]
ev = {}
for fp in sorted((SRC / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln); ev[r["id"]] = r

def q(rid): return ev[rid]["question"]
def cat(rid): return ev[rid]["category"]
def topic(rid): return ev[rid]["topic"]
def mode(rid): return ev[rid]["expected_mode"]

tmpl = [r for r in rows if any("模板生成" in x for x in ev[r["source_eval_id"]]["risk_notes"])]
non_tmpl = [r for r in rows if r not in tmpl]

def dist(items, key):
    return dict(Counter(key(r) for r in items))

def table(title, items, key):
    c = Counter(key(r) for r in items)
    lines = [f"### {title}", "", "| 值 | keep | rewrite | reject | 合计 |", "|---|---|---|---|---|"]
    for k in sorted(c):
        per = Counter(r["decision"] for r in items if key(r) == k)
        lines.append(f"| {k} | {per.get('keep',0)} | {per.get('rewrite',0)} | {per.get('reject',0)} | {sum(per.values())} |")
    lines.append(f"| **合计** | {sum(1 for r in items if r['decision']=='keep')} | {sum(1 for r in items if r['decision']=='rewrite')} | {sum(1 for r in items if r['decision']=='reject')} | {len(items)} |")
    return "\n".join(lines) + "\n"

# 拒绝原因聚类
def rej_bucket(r):
    if "正文过薄" in r["reason"]: return "锚定小节正文过薄"
    if "重叠不足" in r["reason"] or "锚点词与片段" in r["reason"]: return "锚点词与片段文本重叠不足"
    if "对比对象" in r["reason"]: return "对比对象缺席/改写主语不自然"
    if "文档局部结构词" in r["reason"]: return "文档局部语境依赖且改写失败"
    if "概念未在来源片段中命中" in r["reason"]: return "别名题概念未命中来源"
    if "来源路径" in r["reason"]: return "来源路径不可用"
    return "其他"
rej = Counter(rej_bucket(r) for r in rows if r["decision"] == "reject")

# 改写模式聚类
def rw_bucket(r):
    if "元问句" in r["reason"]: return "boundary 元问句改写为直接提问"
    if "对比对象" in r["reason"]: return "对比题降级为单概念机制题"
    if "文档局部结构词" in r["reason"]: return "剥离 Part/编号等文档局部语境"
    if "学习咨询式" in r["reason"]: return "学习咨询式改写为直接概念提问"
    if "中等偏薄" in r["reason"] or "片段较薄" in r["reason"]: return "薄片段收窄问题范围"
    if "片段中等厚度" in r["reason"]: return "trouble 场景改为直接机制提问"
    return "其他"
rw = Counter(rw_bucket(r) for r in rows if r["decision"] == "rewrite")

# 代表性案例：每类改写/拒绝模式取前几条 + 高置信 keep 样例
random.seed(42)
cases = []
for bucket in ["boundary 元问句改写为直接提问", "对比题降级为单概念机制题",
               "剥离 Part/编号等文档局部语境", "学习咨询式改写为直接概念提问", "其他"]:
    items = [r for r in rows if r["decision"] == "rewrite" and rw_bucket(r) == bucket and r["rewrite_question"]]
    for r in items[:4]:
        cases.append(("rewrite", r, bucket))
for bucket in ["锚定小节正文过薄", "锚点词与片段文本重叠不足", "对比对象缺席/改写主语不自然",
               "文档局部语境依赖且改写失败", "别名题概念未命中来源"]:
    items = [r for r in rows if r["decision"] == "reject" and rej_bucket(r) == bucket]
    for r in items[:4]:
        cases.append(("reject", r, bucket))
keeps = [r for r in rows if r["decision"] == "keep" and r["confidence"] == "high" and r["semantic_fit"] == "strong"]
for r in random.sample(keeps, 6):
    cases.append(("keep", r, "高置信保留样例"))

md = []
md.append("# semantic-review-summary —— 语义审查汇总\n")
md.append("审查对象：上一批全部 1,866 条评测候选（其中强制要求覆盖的 1,381 条模板题已 100% 覆盖，"
          "另含 485 条非模板题以保证黄金集能覆盖追问/路由/无证据等类型）。\n")
md.append("## 1. 总数与决策\n")
md.append(f"- 审查总数：**{len(rows)}**（模板题 {len(tmpl)}，非模板题 {len(non_tmpl)}）")
c = Counter(r["decision"] for r in rows)
md.append(f"- keep **{c['keep']}** / rewrite **{c['rewrite']}** / reject **{c['reject']}**")
ct = Counter(r["decision"] for r in tmpl)
md.append(f"- 其中 1,381 条模板题内部：keep {ct['keep']} / rewrite {ct['rewrite']} / reject {ct['reject']}")
cn = Counter(r["decision"] for r in non_tmpl)
md.append(f"- 非模板题内部：keep {cn['keep']} / rewrite {cn['rewrite']} / reject {cn['reject']}\n")
md.append("## 2. 分布表\n")
md.append(table("按 category", rows, lambda r: cat(r["source_eval_id"])))
md.append(table("按 topic", rows, lambda r: topic(r["source_eval_id"])))
md.append(table("按 expected_mode", rows, lambda r: mode(r["source_eval_id"])))
md.append("\n## 3. 最常见的拒绝原因\n")
for k, v in rej.most_common():
    md.append(f"- {k}：{v}")
md.append("\n## 4. 最常见的改写模式\n")
for k, v in rw.most_common():
    md.append(f"- {k}：{v}")
md.append("\n改写示例（原题 → 改写）：")
for d, r, bucket in cases[:8]:
    if d == "rewrite" and r["rewrite_question"]:
        md.append(f"- `{r['source_eval_id']}`（{bucket}）：{q(r['source_eval_id'])[:48]}… → {r['rewrite_question'][:60]}")
md.append("\n## 5. 代表性案例索引（30 条）\n")
md.append("| # | review_id | eval_id | 决策 | 模式 | 题目（截断） | 判断依据（截断） |")
md.append("|---|---|---|---|---|---|---|")
for i, (d, r, bucket) in enumerate(cases[:30], 1):
    md.append(f"| {i} | {r['id']} | {r['source_eval_id']} | {d}（{bucket}） | {r['semantic_fit']} | {q(r['source_eval_id'])[:40]} | {r['reason'][:60]} |")
md.append("\n## 6. 方法与局限\n")
md.append("- 审查由确定性规则管道完成（tools/review_pipeline.py），每条都实际读取了锚定区间的原文，"
          "统计正文行数、链接密度、锚点词覆盖率、误区关键词、文档局部结构词等信号后按类别规则判定。")
md.append("- 规则能可靠发现：薄片段、对比对象缺席、Part/编号类文档局部依赖、元问句、叙述性小标题锚点。"
          "规则不能替代人对内容的完整理解，所有 keep 条目在投入生产前仍应抽查。")
md.append("- rewrite 的改写题已按锚点词覆盖率复核，但『改写后的题是否能被该节回答』仍是候选判断，不是已证事实。")
(HERE.parent / "semantic-review-summary.md").write_text("\n".join(md), encoding="utf-8")
print("summary written; cases:", len(cases))
print(Counter(r["decision"] for r in tmpl), Counter(r["decision"] for r in non_tmpl))
