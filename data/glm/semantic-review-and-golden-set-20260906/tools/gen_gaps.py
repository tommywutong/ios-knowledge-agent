#!/usr/bin/env python3
"""阶段 C：查询与别名缺口报告（只记录高价值问题与可验证的下一步实验）。"""
import json, glob, random
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/overnight-rag-evaluation-20260906")
OUT = HERE.parent / "query-gap-report.jsonl"

gaps = []
def add(term, cat, signal, layer, refs, why, exp, pri, risks=None):
    gaps.append({
        "id": "gap-%06d" % (len(gaps) + 1),
        "canonical_term_or_query": term,
        "category": cat,
        "observed_signal": signal,
        "likely_layer": layer,
        "evidence_refs": refs,
        "why_not_conclusive": why,
        "safe_followup_experiment": exp,
        "priority": pri,
        "risk_notes": risks or [],
    })

# ---------- 1. FTS 抽样的主题级 miss 信号 ----------
fts = [json.loads(l) for l in (SRC / "retrieval-samples/fts-sample-results.jsonl").read_text(encoding="utf-8").splitlines()]
ev = {}
for fp in sorted((SRC / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln); ev[r["id"]] = r
by_topic = defaultdict(Counter)
for s in fts:
    t = ev[s["eval_id"]]["topic"]
    by_topic[t][s["status"]] += 1

LAYER = {
    "source-symbol": ("query_planning", "P0",
        "生产链路有查询规划（最多 4 路），本地脚本把长自然语言问题直接喂给 FTS；CODEX_REVIEW 已实测 objc_msgSend/class_addMethod/attachCategories 裸符号查询均能返回权威候选（attachCategories 源码候选在第 3 名），说明缺口在『问题→符号查询』的规划层而非符号不可召回"),
    "swift-interop": ("fts_lexical_recall", "P1", "Swift 互操作类中文笔记标题与常见问法差异大"),
    "build-startup": ("fts_lexical_recall", "P1", "启动/链接/Mach-O 中文笔记用词与用户问法差异大，且别名缺口在术语库中已有记录"),
    "foundation": ("fts_lexical_recall", "P2", "类簇/集合类笔记标题抽象、问法具体"),
    "memory": ("fts_lexical_recall", "P2", "内存主题小节锚点与问法部分重叠"),
    "runtime": ("fts_lexical_recall", "P2", "runtime 笔记厚但小节命名偏教程化"),
    "persistence": ("fts_lexical_recall", "P2", "持久化综述型笔记小节粒度粗"),
    "block": ("fts_lexical_recall", "P2", "Block 主题混合中英术语"),
    "routing": ("routing", "P2", "跨平台 knowledge 题在 FTS 路径几乎必然 miss，需确认生产意图探测兜底"),
    "network": ("fts_lexical_recall", "P2", "网络主题表现中等"),
    "persistence2": ("fts_lexical_recall", "P2", ""),
}
for t, c in sorted(by_topic.items(), key=lambda kv: -(kv[1]["miss"] / max(1, sum(kv[1].values())))):
    tot = sum(c.values())
    if tot == 0:
        continue
    rate = c["miss"] / tot
    if rate < 0.4 and t not in ("source-symbol",):
        continue
    layer, pri, note = LAYER.get(t, ("fts_lexical_recall", "P2", ""))
    sample_ids = [s["eval_id"] for s in fts if ev[s["eval_id"]]["topic"] == t and s["status"] == "miss"][:4]
    add(
        f"{t} 主题问题（FTS miss 率 {rate:.0%}，n={tot}）",
        "topic_recall",
        f"上一批 FTS-only 抽样中该主题 {c['miss']}/{tot} 条 miss；预期来源在 top8 未出现" + (f"；{note}" if note else ""),
        layer,
        sample_ids + ["fts-sample-results.jsonl（抽样记录）"],
        "本地 --no-vector 无查询规划、无向量召回、无 rerank，miss 不能归因于任何单一层，更不能外推到生产",
        "对同一批 miss 问题做三组对照：(a) 裸符号/短关键词直接查 FTS；(b) 本地带向量混合检索（不写库）；(c) 生产 Retrieval v2 复测，比较各层命中差异",
        pri,
        ["上一批 31 条 observed path 属陈旧索引（已由 Codex 清理并验证 freshness clean），引用 miss 案例时须剔除这些 eval_id"],
    )

# ---------- 2. 术语库无证据条目（别名缺口候选） ----------
aliases = [json.loads(l) for l in (SRC / "terminology-aliases.jsonl").read_text(encoding="utf-8").splitlines()]
nulls = [a for a in aliases if a["evidence_path"] is None]
random.seed(20260907)
for a in random.sample(nulls, 22):
    add(
        a["canonical_term"],
        "terminology_alias",
        f"术语及其全部别名（{('、'.join(a['aliases'][:3]))}…）在上一批 137 个覆盖文件中零命中，无法建立中英文/符号-笔记映射",
        "alias",
        [a["id"], "terminology-aliases.jsonl（该条目 evidence_* = null）"],
        "零命中可能因为术语确实不在语料、或写法差异未被字面匹配捕获；不排除术语本身表述有误",
        "人工在 Obsidian/tips 全文中 grep 该术语的各别名变体；确认后补别名候选并加入离线评测，不直接改生产",
        "P1" if a["category"] in ("runtime", "memory", "runloop-gcd") else "P2",
    )

# ---------- 3. 术语映射缺口（质量发现） ----------
qfind = [json.loads(l) for l in (SRC / "quality-findings.jsonl").read_text(encoding="utf-8").splitlines()]
for qf in [x for x in qfind if x["finding_type"] == "terminology_gap"][:4]:
    add(
        Path(qf["source_path"]).stem + " 的中英术语映射",
        "terminology_alias",
        qf["evidence_summary"][:120],
        "alias",
        [qf["id"]],
        "发现来自规则扫描，具体哪个别名缺失需人工逐个确认",
        "按文件人工列出中英术语对照，补入离线别名候选并设计对照查询实验",
        "P1",
    )

# ---------- 4. 语料缺失主题（no_evidence 依据） ----------
add(
    "WidgetKit / App Intents / StoreKit 2 / Metal / Core ML / ARKit / Vision / visionOS / Xcode Cloud 等主题的语料判定",
    "corpus_missing",
    "阶段 D 巡检：SwiftUI/Combine/Swift Concurrency/SwiftData/TestFlight 五个主题的『语料缺失』假设已被 WWDC 场次文件证伪；其余主题在 wwdc/zh+en 文件名中零命中，但未做全文穷尽检索",
    "source_coverage",
    ["quality-followup.jsonl（falsified 条目）", "batch-006-routing-no-evidence.jsonl"],
    "文件名零命中不等于语料缺失（可能以别名或正文出现）；全库 122 万块未穷尽",
    "对每个主题先做全库 FTS 关键词试查并人工判读，再决定是否引入官方文档或改写 no_evidence 候选",
    "P1",
)

# ---------- 5. 生产与本地状态差异 ----------
add(
    "生产 Vectorize/D1 快照落后于本地已清理索引",
    "index_freshness",
    "CODEX_REVIEW：本地 32 个陈旧 summer2026 文件（1,521 块）已用 sync --no-embed 清理且 freshness clean；生产 55,635 向量快照早于该清理，尚未重新发布",
    "source_coverage",
    ["CODEX_REVIEW.md", "retrieval-samples/fts-sample-results.jsonl 中 observed path 缺失的样本"],
    "生产实际行为未知：本地证据不能证明生产仍返回陈旧路径，也不排除生产按稳定 ID 已自洽",
    "在生产只读核验若干已知被删文件的稳定 ID 是否仍可召回；如需同步，走 HANDOFF 的稳定 ID 发布流程，由人工执行",
    "P0",
    ["严禁把本地 FTS 复测冒充生产验证", "发布操作不在本任务边界内"],
)

# ---------- 6. 对比题的重排多样性 ----------
add(
    "对比类问题需要两个主题的证据同时进入 top-k",
    "comparison_multi_evidence",
    "黄金集中 24 条对比题的预期证据常分散在两处小节；本地 FTS 抽样显示对比题 miss 率偏高",
    "rerank",
    ["gold-eval-candidates.jsonl 中 category=comparison 的条目"],
    "本地 FTS 无 RRF/reranker；生产重排行为未知",
    "在生产 Retrieval v2 上复测对比题，观察两个概念的证据是否同入最终 top8 及引用是否完整",
    "P2",
)

# ---------- 7. 追问继承 ----------
add(
    "追问是否继承上一轮检索意图与相关历史",
    "followup_routing",
    "上一批 81 条追问题为模板构造，其中 41 条上一轮助手内容为合成占位；本地无法验证路由状态机",
    "routing",
    ["batch-008-follow-up.jsonl", "semantic-review.jsonl 中 follow_up 类条目"],
    "路由状态机在生产 Pages Function 内，本地评测集无法触发真实路由",
    "用生产自测入口（IOS_SELF_TEST_CASES 定向）或人工在站点上验证追问场景；先人工确认合成上下文的衔接自然性",
    "P2",
)

# ---------- 8. 补充缺口 ----------
add(
    "Swift 互操作独立评测题缺失",
    "corpus_missing",
    "评测池中 swift-interop 仅 19 条且审查通过率低，黄金集该主题为 0；本地存在 Swift 方法调用/Existential Container/struct-class 等 tips 资料",
    "source_coverage",
    ["semantic-review-summary.md 的 topic 分布", "tips-master/sources/Swift方法调用.md"],
    "资料存在但评测题未成规模是审查/出题问题，不是资料缺失；两者不能混为一谈",
    "人工从这 3 篇 tips 资料中按小节手写 10-15 条独立问题并入离线评测",
    "P1",
)
add(
    "WWDC 中英双语逐字稿重复（107 对）",
    "corpus_duplicate",
    "上一批质量发现：同一 session 的 zh/en 两份逐字稿均入索引，关键词检索同屏双份",
    "rerank",
    ["quality-findings.jsonl 中 duplicate 类 WWDC 条目"],
    "重复对生产 top-k 多样性的实际影响未经生产链路量化",
    "在生产 Retrieval v2 上观察同一 session 的 zh/en 是否同时进入最终 top8，再决定治理方案",
    "P2",
)
add(
    "min_keyword_coverage=0.55 对长自然语言问题的过滤影响",
    "keyword_coverage",
    "上一批 FTS miss 案例中，长问题分词后有效词多，可能被关键词覆盖率阈值整批过滤；未验证",
    "fts_lexical_recall",
    ["HANDOFF/config.yaml 检索参数", "failure-triage.jsonl 的 lexical_recall 案例"],
    "该参数同时防误召回；只能观察不能直接归因",
    "用 db 只读复现 fts_search 的分词与覆盖计算，比较不同阈值下的命中集合变化（纯离线实验，不改配置）",
    "P2",
)
add(
    "compare 模板题的『预期对比小节』粒度",
    "comparison_multi_evidence",
    "阶段 A 中 283 条对比题大量因『对比对象未在该小节出现』被拒/改写：对比内容常分散在不同小节甚至不同文件",
    "query_planning",
    ["semantic-review-summary.md 的拒绝原因分布"],
    "这是评测预期设计的局限，不等于检索故障",
    "人工为幸存的对比题确认两个概念的真实出处行号，必要时拆成两条单概念题",
    "P2",
)
nulls2 = [a for a in nulls if a["id"] not in {g["evidence_refs"][0] for g in gaps if g["evidence_refs"] and g["evidence_refs"][0].startswith("alias-")}]
for a in random.sample(nulls2, 3):
    add(
        a["canonical_term"],
        "terminology_alias",
        f"术语及别名（{('、'.join(a['aliases'][:3]))}…）在覆盖文件中零命中",
        "alias",
        [a["id"]],
        "同上：不能区分资料缺失与写法差异",
        "人工 grep 各别名变体后补别名候选",
        "P2",
    )

with OUT.open("w", encoding="utf-8") as f:
    for g in gaps:
        f.write(json.dumps(g, ensure_ascii=False) + "\n")
print("gaps:", len(gaps))
print("layer:", dict(Counter(g["likely_layer"] for g in gaps)))
print("priority:", dict(Counter(g["priority"] for g in gaps)))
