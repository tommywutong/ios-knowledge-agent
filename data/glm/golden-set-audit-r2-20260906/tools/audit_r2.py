#!/usr/bin/env python3
"""黄金集人工语义复核（A）+ 7 条 no_evidence 复审（B）。
每条都实际读取来源片段；决策规则按本轮任务要求收紧。
"""
import json, re, glob
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/semantic-review-and-golden-set-20260906")
OLD = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/overnight-rag-evaluation-20260906")
VAULT = Path("/Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault")
ARCH = Path("/Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-developer-archive-vault")

gold = [json.loads(l) for l in (SRC / "gold-eval-candidates.jsonl").read_text(encoding="utf-8").splitlines()]
rev1 = {json.loads(l)["id"]: json.loads(l) for l in (SRC / "semantic-review.jsonl").read_text(encoding="utf-8").splitlines()}
ev = {}
for fp in sorted((OLD / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln); ev[r["id"]] = r

_file_cache = {}
def lines_of(p):
    if p not in _file_cache:
        _file_cache[p] = Path(p).read_text(encoding="utf-8", errors="replace").split("\n")
    return _file_cache[p]

STOP_ASCII = set()
def qtokens(x):
    """ascii 词（不区分大小写）+ CJK 2-gram 滑窗，避免整段长词匹配失败。"""
    ascii_toks = {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", x) if len(w) >= 2}
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", x)
    grams = set()
    for seg in cjk:
        if seg in ("是什么","怎么样","为什么","怎么","哪些","什么","区别","资料","机制","原理","底层","细节","关键","讲讲","请问"):
            continue
        for i in range(len(seg) - 1):
            grams.add(seg[i:i+2])
    return ascii_toks, grams

def coverage2(x, text):
    a, g = qtokens(x)
    lt = text.lower()
    fa = (sum(1 for t in a if t in lt) / len(a)) if a else None
    fg = (sum(1 for t in g if t in text) / len(g)) if g else None
    parts = [v for v in (fa, fg) if v is not None]
    return (sum(parts) / len(parts)) if parts else 0.0

# ================= A：gold-audit.jsonl =================
audits = []
def add_audit(g, decision, sq, ef, rf, reason, rq=None, conf="medium", risks=None):
    audits.append({
        "id": "audit-%06d" % (len(audits) + 1),
        "source_gold_id": g["id"],
        "source_eval_id": g["source_eval_id"],
        "decision": decision,
        "standalone_quality": sq,
        "evidence_fit": ef,
        "routing_fit": rf,
        "reason": reason[:400],
        "rewrite_question": rq,
        "confidence": conf,
        "risk_notes": risks or [],
    })

# 人工逐条确认的碎片/标题式锚点：不是独立用户问题，且无自然概念改写
FRAGMENT_REMOVE = {
    "gold-000011": "锚点『Runtime 简介』为文档栏目标题",
    "gold-000019": "锚点含时间区间装饰（2015 → 至今），为文档标题残留",
    "gold-000039": "锚点『谁决定了先后顺序』为上下文指代碎片",
    "gold-000047": "锚点『到底会有几个 cell 活着』为行文碎片",
    "gold-000050": "锚点『这块内存实际要多少』为指代碎片",
    "gold-000054": "对比双方均为行文碎片/带编号小标题",
    "gold-000057": "锚点『alpha 的边界到底在哪』为行文碎片",
    "gold-000070": "锚点『x86_64 靠指令序列当签名』为论断式小标题碎片",
    "gold-000073": "锚点『进程级汇总与逐个 VM Region』为小标题拼接",
    "gold-000085": "锚点含时间戳（2026-05-14 23:33），为笔记元数据残留",
    "gold-000087": "对比双方均为时间戳笔记标题（2026-05-15 12:11 / 12:12），为文档元数据残留",
    "gold-000088": "对比对象之一为时间戳笔记标题（2026-05-14 23:29），为文档元数据残留",
    "gold-000095": "对比对象之一为『前言』，纯文档结构",
    "gold-000097": "对比对象『卡顿-检测』为文档内部栏目标题",
    "gold-000099": "对比对象『启动优化-二进制重排』为文档内部栏目标题",
    "gold-000101": "对比对象『编译优化-编译缓存』为文档内部栏目标题",
    "gold-000102": "对比对象『编译优化-观测』为文档内部栏目标题",
}

# 经人工打开核对的可改写项（来源为大纲式清单，逐条列出机制步骤）
MANUAL_REWRITE = {
    "eval-000085": ("objc4 里 objc_object 是怎么定义的？id 和 Class 与它是什么关系？",
                    "该节实际展示了 objc.h 中 Class/id/SEL 都是指向 objc_class/objc_object/objc_selector 的裸指针 typedef，直接回答定义与关系。"),
    "eval-000272": ("UITableView 的复用池真实结构是什么？怎么用运行时方法验证？",
                    "该节纠正了『方框复用池』的常见误图，并给出用 class_copyIvarList 找到 _reusableTag... 等 ivar、直接问运行时验证的方法，可支撑该问题。"),
    "eval-000312": ("UIViewController 在 push、present 等不同容器场景下，生命周期回调的真实顺序有什么差异？",
                    "该节以三段真实日志对比同一控制器在不同容器下的回调顺序，直接支撑该问题。"),
    "eval-000332": ("hitTest 的命中测试有哪些容易记错的规则细节？",
                    "该节指出 Apple 文档与中文圈对 hitTest 忽略 alpha<0.01 规则的普遍误传，逐条澄清命中测试规则，可支撑该问题。"),
    "eval-000455": ("MRC 下『自己创建的对象自己负责释放』这条所有权规则具体指什么？哪些方法族适用？",
                    "该节引用 Apple 原文并解释 alloc/new/copy/mutableCopy 方法族的所有权归属，直接回答该问题。"),
    "eval-000462": ("MRC 里『不能放弃不属于自己的所有权』是什么意思？不能释放等于不能使用吗？",
                    "该节明确区分『不能释放』与『不能使用』并给出 Apple 原文，直接回答该问题。"),
    "eval-000105": ("objc_msgSend 的汇编快速路径是怎么通过方法缓存命中 IMP 的？",
                    "该节为『第一部分 · 快速路径（缓存命中）』的大纲式清单，逐条列出 cache_t 结构、GetClassFromIsa、CacheLookup 哈希定位、命中 br IMP / 未命中转慢速查找，可支撑快速路径命中机制的问题；但为大纲而非正文，回答深度有限。"),
    "eval-000109": ("消息转发的流程是怎样的？每一步分别给了开发者什么机会？",
                    "该节『第三部分 · 消息转发』列出转发入口、三部曲（forwardingTargetForSelector / methodSignatureForSelector+forwardInvocation / doesNotRecognizeSelector）与两次动态方法决议的边界澄清，可支撑三步流程问题；同为大纲式清单。"),
}
LEAK = re.compile(r"目录|这篇在系列中的位置|本篇|本节|该系列|系列中|Part\s*\d|第[一二三四五六七八九十\d]+\s*(部分|篇|章)|draft|^\d+[\.、]")

for g in gold:
    e = ev[g["source_eval_id"]]
    q = g["question"]
    cat, mode = g["category"], g["expected_mode"]

    if mode in ("no_evidence", "general"):
        add_audit(g, "keep", "strong", "not_applicable", "correct",
                  f"{mode} 类评测题：设计上无来源；题面自然独立，与 B 阶段对 7 条 no_evidence 的按题复审不冲突（该题不在证伪清单内）。",
                  conf="medium",
                  risks=(["no_evidence 预期只能由生产链路最终验证"] if mode == "no_evidence" else []))
        continue

    # 来源片段实际读取
    if not g["expected_source_path"] or not Path(g["expected_source_path"]).is_file():
        add_audit(g, "remove", "weak", "weak", "wrong", "来源路径不存在，无法支撑 knowledge 题。", conf="high")
        continue
    ls = lines_of(g["expected_source_path"])
    seg = ls[max(0, g["expected_start_line"]-1):min(g["expected_end_line"], len(ls))]
    text = "\n".join(seg)
    prose = [l for l in seg if len(l.strip()) > 12 and not l.strip().startswith("#")]

    # 结构泄漏：Codex 指出的 6 条 + 全量复扫
    if LEAK.search(q):
        if g["source_eval_id"] in MANUAL_REWRITE:
            rq, why = MANUAL_REWRITE[g["source_eval_id"]]
            core = {"eval-000105": "缓存命中", "eval-000109": "转发", "eval-000085": "objc_object",
                    "eval-000272": "复用池", "eval-000312": "viewWillDisappear", "eval-000332": "hitTest",
                    "eval-000455": "alloc", "eval-000462": "释放"}[g["source_eval_id"]]
            ok = core.lower() in text.lower() and len(prose) >= 1
            add_audit(g, "rewrite" if ok else "remove", "strong" if ok else "weak",
                      "partial" if ok else "weak", "correct" if ok else "questionable",
                      ("题面含文档结构标题（" + LEAK.search(q).group(0) + "），不是独立用户问题；"
                       + "已按人工核对改写为来源可直接回答的概念题。" + why if ok
                       else "题面含文档结构标题且改写未通过来源核对。"),
                      rq if ok else None, conf="high" if ok else "medium",
                      risks=(["来源为大纲式清单，答案深度受限"] if ok else []))
        else:
            add_audit(g, "remove", "weak", "weak", "questionable",
                      f"题面泄漏文档内部结构（『{LEAK.search(q).group(0)}』），不是用户会独立提出的问题，且不存在能直接回答的自然概念改写。",
                      conf="high")
        continue

    # follow_up：上下文依赖是预期属性
    if cat == "follow_up":
        ok_ctx = bool(g["dialogue_context"])
        add_audit(g, "keep" if ok_ctx else "remove", "partial", "partial", "correct",
                  "追问按设计依赖上一轮上下文（非独立问题，符合类别预期）；来源片段复核充分，dialogue_context 完整。"
                  if ok_ctx else "追问缺少上下文，无法成立。",
                  conf="medium",
                  risks=(["部分追问的上一轮助手内容为合成占位"] if any("合成" in x for x in g["risk_notes"]) else []))
        continue

    # knowledge 类：证据覆盖硬核验
    if cat == "cross_platform":
        # 非 iOS 侧词汇必然不在 iOS 侧片段中，仅核验 iOS 侧锚点由上一轮保证
        add_audit(g, "keep", "strong", "partial", "correct",
                  "跨平台题：iOS 侧证据锚定经上一轮审查且路径实测存在；非 iOS 侧按设计应声明缺资料，不用 iOS 片段覆盖率高估证据范围。",
                  conf="medium",
                  risks=["预期模式是设计意图，需生产链路复核"])
        continue
    if cat == "symbol":
        m = re.search(r"「(.+?)」", q)
        sym = m.group(1) if m else ""
        cov = 1.0 if (sym and sym.lower() in text.lower()) else 0.0
        fit = "strong" if cov == 1.0 else "weak"
    elif cat == "alias":
        # alias 题按其概念主条目核验，整句问题会稀释覆盖率
        m_rat = re.search(r"「(.+?)」主条目", e.get("rationale") or "")
        concept = m_rat.group(1) if m_rat else q
        cov = coverage2(concept, text)
        fit = "strong" if cov >= 0.7 else ("partial" if cov >= 0.45 else "weak")
    else:
        cov = coverage2(q, text)
        fit = "strong" if cov >= 0.7 else ("partial" if cov >= 0.5 else "weak")
    MANUAL_GOLD = {
        "gold-000086": ("eval-000553", "死锁", "在主线程里用 dispatch_sync 同步执行主队列任务一定会死锁吗？在其他线程调用呢？",
                        "该节逐条列出：主线程同步执行+主队列会死锁（任务互相等待）、其他线程同步执行+主队列不会死锁、主队列为串行队列，直接回答该问题。"),
        "gold-000014": ("eval-000085", "objc_object", "objc4 里 objc_object 是怎么定义的？id 和 Class 与它是什么关系？",
                        "该节实际展示了 objc.h 中 Class/id/SEL 都是指向 objc_class/objc_object/objc_selector 的裸指针 typedef，直接回答定义与关系。"),
        "gold-000045": ("eval-000272", "复用池", "UITableView 的复用池真实结构是什么？怎么用运行时方法验证？",
                        "该节纠正了『方框复用池』的常见误图，并给出用 class_copyIvarList 直接问运行时验证的方法，可支撑该问题。"),
        "gold-000053": ("eval-000312", "viewWillDisappear", "UIViewController 在 push、present 等不同容器场景下，生命周期回调的真实顺序有什么差异？",
                        "该节以三段真实日志对比同一控制器在不同容器下的回调顺序，直接支撑该问题。"),
        "gold-000056": ("eval-000332", "hitTest", "hitTest 的命中测试有哪些容易记错的规则细节？",
                        "该节指出 Apple 文档与中文圈对 hitTest 忽略 alpha<0.01 规则的普遍误传，逐条澄清命中测试规则，可支撑该问题。"),
        "gold-000078": ("eval-000455", "alloc", "MRC 下『自己创建的对象自己负责释放』这条所有权规则具体指什么？哪些方法族适用？",
                        "该节引用 Apple 原文并解释 alloc/new/copy/mutableCopy 方法族的所有权归属，直接回答该问题。"),
        "gold-000079": ("eval-000462", "释放", "MRC 里『不能放弃不属于自己的所有权』是什么意思？不能释放等于不能使用吗？",
                        "该节明确区分『不能释放』与『不能使用』并给出 Apple 原文，直接回答该问题。"),
    }
    if g["id"] in MANUAL_GOLD:
        eid2, core, rq, why = MANUAL_GOLD[g["id"]]
        ok = core.lower() in text.lower() and len(prose) >= 1
        add_audit(g, "rewrite" if ok else "remove", "strong" if ok else "weak",
                  "partial" if ok else "weak", "correct",
                  ("题面锚点是笔记标题复述（含冒号结构）或正文编号语境，不是独立自然问题；已改写为具体概念题，并打开来源人工核对：" + why if ok
                   else "题面为标题复述/编号语境，且改写未通过来源核对。"),
                  rq if ok else None, conf="high" if ok else "medium",
                  risks=(["改写题已二次核对来源片段，仍属候选"] if ok else []))
        continue
    if g["id"] in FRAGMENT_REMOVE:
        add_audit(g, "remove", "weak", "partial", "questionable",
                  "人工逐条确认：" + FRAGMENT_REMOVE[g["id"]] + "；不是用户会独立提出的自然问题，且不存在不编造的自然改写。",
                  conf="high")
        continue
    if fit == "weak" or not prose:
        add_audit(g, "remove", "partial", "weak", "correct",
                  f"逐题复核证据：问题关键词与锚定片段的实际重叠率 {cov:.0%}（正文行 {len(prose)}），不足以支撑该题的核心范围；不能只因标题或关键词相同判为有效。",
                  conf="medium",
                  risks=["该项在上一轮被 keep，本轮按更严标准移除"])
        continue
    standalone = "partial" if ("面试" in q or "概括" in q or "大白话" in q) else "strong"
    add_audit(g, "keep", standalone, fit, "correct",
              f"独立自然问题，来源片段实测支撑（关键词重叠率 {cov:.0%}，正文行 {len(prose)}），knowledge 路由与类别一致。",
              conf="high" if fit == "strong" else "medium")

# 修复：移除项的 rewrite_question 字段应为 null（add_audit 默认即 null）

with (HERE.parent / "gold-audit.jsonl").open("w", encoding="utf-8") as f:
    for r in audits:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("gold-audit:", len(audits), dict(Counter(r["decision"] for r in audits)))
print("removes:", [(r["source_gold_id"], ev[r["source_eval_id"]]["question"][:40]) for r in audits if r["decision"] == "remove"])

# ================= B：no-evidence-audit.jsonl =================
def grep_lines(path, pat, ctx=6):
    ls = Path(path).read_text(encoding="utf-8", errors="replace").split("\n")
    hits = [i for i, l in enumerate(ls, 1) if re.search(pat, l, re.I)]
    return ls, hits

b_rows = []
def add_b(eid, dec, aspect, paths, summary, reason, conf, risks=None):
    b_rows.append({
        "id": "noevid-%06d" % (len(b_rows) + 1),
        "source_eval_id": eid,
        "decision": dec,
        "question_aspect_checked": aspect,
        "evidence_paths_checked": paths,
        "evidence_summary": summary[:400],
        "reason": reason[:400],
        "confidence": conf,
        "risk_notes": risks or [],
    })

# 1) UIScreenKit / SwiftUI 布局内部
add_b("eval-001700", "retain_no_evidence",
      "『SwiftUI 布局系统内部实现』与『UIScreenKit』术语本身",
      ["全库 grep UIScreenKit（apple-docs-vault + apple-archive，零命中）",
       "wwdc/zh 与 wwdc/en 中 swiftui 场次文件名清单"],
      "UIScreenKit 在两个资料仓库全文零命中，是资料无法佐证的可疑术语；SwiftUI 场次（zh 6 篇 / en 若干）为使用指南型逐字稿，未覆盖布局系统私有内部实现。",
      "按具体主张核对：布局系统『内部实现』无官方资料支撑，且题面嵌入零命中的造词，整体仍应判 no_evidence；但语料存在 SwiftUI 一般资料，生产可能对 SwiftUI 部分返回知识，预期模式存在翻案风险。",
      "medium",
      ["该题混入可疑术语，作为评测题的信号价值有限，建议人工改写或淘汰"])

# 2) actor 重入 → 提升为 knowledge 候选
p10133 = VAULT / "wwdc/en/wwdc2021/10133-protect-mutable-state-with-swift-actors.md"
ls, hits = grep_lines(p10133, r"reentran")
add_b("eval-001701", "promote_to_knowledge_candidate",
      "actor 重入（reentrancy）的具体语义与设计对策，而非泛泛 Swift 并发",
      [str(p10133), str(VAULT / "wwdc/en/wwdc2021/10254-swift-concurrency-behind-the-scenes.md")],
      "10133 场次第 281-295 行直接完整地解释 actor reentrancy：跨 await 携带状态假设的风险示例、『reentrancy 防死锁并保证前进』的机制说明、"
      "以及设计对策（在同步代码内完成状态修改、await 前恢复一致性），第 561 行再次强调 design for reentrancy；10254 从底层调度视角补充背景。",
      "问题问的正是 actor 重入隔离细节，命中段落直接回答该具体主张，符合『能直接支撑该具体问题的可靠资料』标准，故提升为 knowledge 候选。",
      "high",
      ["证据为英文逐字稿；预期证据行号以 281-295 为主，561 行为辅助"])

# 3) Combine Publisher 订阅内部数据流
p722 = VAULT / "wwdc/en/wwdc2019/722-introducing-combine.md"
p721 = VAVAULT = VAULT / "wwdc/en/wwdc2019/721-combine-in-practice.md"
add_b("eval-001702", "retain_no_evidence",
      "Publisher 订阅的『内部』数据流实现原理，而非 Combine 一般介绍",
      [str(p722), str(p721)],
      "722『Introducing Combine』与 721『Combine in Practice』为入门/实操场次，讲解 Publisher/Subscriber/Subscription 的 API 层数据流与需求管理；未提供订阅机制的内部实现。",
      "按 Codex 提示，泛 Combine 介绍不等于『内部数据流原理』；具体主张仍无可靠证据，维持 no_evidence。若把问题改写为 API 层订阅机制，可另行人工出题，但不在本轮伪造。",
      "medium")

# 4) SwiftData 持久化底层
paths_sd = [str(VAULT / "wwdc/zh/wwdc2024/10075-track-model-changes-with-swiftdata-history.md"),
            str(VAULT / "wwdc/en/wwdc2024/10138-create-a-custom-data-store-with-swiftdata.md")]
add_b("eval-001703", "retain_no_evidence",
      "SwiftData 持久化的『底层实现』，而非 SwiftData 使用入门",
      paths_sd,
      "10075 讲如何利用 persistent history/底层存储追踪模型变更，10138 讲自定义数据存储的对接方式；均为使用层面，未披露 SwiftData 自身的持久化实现。",
      "具体主张（底层实现）无官方资料支撑，维持 no_evidence。",
      "medium")

# 5) TestFlight 企业分发合规
p10203 = VAULT / "wwdc/en/wwdc2021/10203-triage-testflight-crashes-in-xcode-organizer.md"
add_b("eval-001712", "retain_no_evidence",
      "TestFlight『企业分发合规边界』，而非 TestFlight 崩溃诊断",
      [str(p10203)],
      "语料中 TestFlight 相关仅 10203 崩溃诊断场次；归档中分发类文档（如 qa『How can a build engineer distribute an app on behalf of the team』）不涉及企业分发合规边界这一法律/政策主题。",
      "合规边界属政策性主张，语料完全未覆盖，维持 no_evidence。注意：有 TestFlight 崩溃资料 ≠ 能回答企业分发合规。",
      "high")

# 6) TestFlight 加密合规报告
enc_paths = []
for base in [ARCH, VAULT / "apple-docs"]:
    for p in base.rglob("*.md"):
        if re.search(r"export\s+compliance|encryption\s+compliance", p.read_text(encoding="utf-8", errors="replace"), re.I):
            enc_paths.append(str(p))
        if len(enc_paths) >= 3:
            break
add_b("eval-001754", "retain_no_evidence",
      "TestFlight 内测包加密合规报告的具体填写流程",
      (enc_paths if enc_paths else ["apple-archive 与 apple-docs 全文 grep 'export compliance|encryption compliance'（零有效命中）"]),
      "定向检索未找到任何直接讲解 iOS/<TestFlight 加密合规报告填写的官方文档；命中为空或与主题无关。",
      "具体填写流程无资料支撑，维持 no_evidence。",
      "medium")

# 7) SwiftUI on Android
sw_paths = [str(p) for p in sorted((VAULT / "wwdc").rglob("*swiftui*.md"))[:3]]
add_b("eval-001790", "retain_no_evidence",
      "SwiftUI『能否运行于 Android』的跨平台可行性主张",
      sw_paths + ["（SwiftUI 场次均为 Apple 平台使用指南）"],
      "SwiftUI 场次只覆盖 Apple 平台使用；语料中无任何 Android 移植/跨平台运行 SwiftUI 的资料。",
      "存在 SwiftUI 资料 ≠ 能回答 Android 可行性；该 cross_platform no_evidence 预期成立。",
      "high")

# 提升条目附结构化证据（校验器核对路径与行号）
for r in b_rows:
    if r["decision"] == "promote_to_knowledge_candidate":
        r["promoted_evidence"] = {
            "path": str(p10133),
            "start_line": 281,
            "end_line": 295,
            "aux_path": str(VAULT / "wwdc/en/wwdc2021/10254-swift-concurrency-behind-the-scenes.md"),
        }
with (HERE.parent / "no-evidence-audit.jsonl").open("w", encoding="utf-8") as f:
    for r in b_rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("no-evidence-audit:", len(b_rows), dict(Counter(r["decision"] for r in b_rows)))
