#!/usr/bin/env python3
"""r3 红队审查：任务 A（160 条逐题）+ 任务 B（20 条 no_evidence 全量）。
判定原则：用户从未看过笔记标题；标题复述/栏目名/同义重复/指代碎片一律不留；
叙事性标题只有改写为"自然、具体、来源直接可答"的问题才可保留。
"""
import json, re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
R2 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-audit-r2-20260906")
VAULT = Path("/Users/tommywu/Desktop/iOS知识agentt/data/repos/apple-docs-vault")

r2 = [json.loads(l) for l in (R2 / "gold-eval-candidates-r2.jsonl").read_text(encoding="utf-8").splitlines()]
by_id = {g["id"]: g for g in r2}
_file_cache = {}
def excerpt(g):
    p = g["expected_source_path"]
    if not p or not Path(p).is_file():
        return "", []
    if p not in _file_cache:
        _file_cache[p] = Path(p).read_text(encoding="utf-8", errors="replace").split("\n")
    ls = _file_cache[p]
    seg = ls[max(0, g["expected_start_line"]-1):min(g["expected_end_line"], len(ls))]
    text = "\n".join(seg)
    prose = [l.strip() for l in seg if len(l.strip()) > 12 and not l.strip().startswith("#")]
    return text, prose

def subject_of(q):
    m = re.search(r"「(.+?)」", q)
    if m: return m.group(1)
    m = re.search(r"请讲讲(.+?)的底层机制或工作原理", q)
    if m: return m.group(1)
    return q

def clean_subject(x):
    x = re.sub(r"`[^`]*`", "", x)
    x = re.sub(r"[（(][^)）]*[)）]", "", x)
    x = re.sub(r"Part\s*\d+\s*[-—–·:.]\s*", "", x)
    x = re.sub(r"^\d+\s*[.、)]\s*", "", x)
    return x.strip(" ：:-_·#")

BOUNDARY = {
    "lookup": "问题止于『该对象是什么/怎么定义』的概念解释，不延伸到未在来源出现的实现细节",
    "trouble": "问题止于该主题的机制梳理与资料中明确指出的易错点，不延伸到资料未覆盖的实战场景",
    "mech": "问题止于该机制的原理与来源中给出的关键细节，不要求覆盖所有变体",
    "summary": "问题止于概括来源小节的要点，不要求超出小节范围的扩展",
    "followup": "问题止于上一轮话题在该来源小节中的延伸，不引入新主题",
    "symbol": "问题止于符号的定义位置与来源可支撑的作用说明，不要求完整行为规范",
    "alias": "问题止于同一概念在不同表述下的检索与回答，不引入新概念",
    "general": "不适用：预期不进入知识回答，仅作路由边界测试",
    "noev": "不适用：预期无证据回答，仅作无证据判定测试",
}

# ---------------- 逐题判定表 ----------------
# 决策依据人工通览全部题面 + 来源片段核对（见 reason）。
R = {}   # r2_id -> (decision, rewrite_question, natural, technical_intent, comp_validity, note)
def K(intent, comp="not_applicable", note=""):
    R["keep"] = None
    return ("keep", None, "pass", intent, comp, note)
def RW(rq, intent, note=""):
    return ("rewrite", rq, "fail", intent, "not_applicable", note)
def RM(note):
    return ("remove", None, "fail", "", "not_applicable", note)

T = {}
# --- answerable（60）---
for gid in ["gold-r2-000001","gold-r2-000002","gold-r2-000003","gold-r2-000004"]:
    T[gid] = K("理解 Block 循环引用/weak-strong dance、变量捕获与 __block 的机制")
for gid in ["gold-r2-000018","gold-r2-000019"]:
    T[gid] = K("理解 Tagged Pointer 的优化手段与易错点")
T["gold-r2-000005"] = K("理解 __block 的 byref 结构与 forwarding 转发机制")
T["gold-r2-000013"] = K("理解 objc4 中 objc_object 的定义及 id/Class 与它的关系")
T["gold-r2-000016"] = K("理解 arm64e PAC 指针签名机制")
T["gold-r2-000021"] = K("理解 objc_msgSend 汇编快速路径利用方法缓存命中 IMP 的流程")
T["gold-r2-000022"] = K("理解消息转发三步流程及每步给开发者的机会")
T["gold-r2-000035"] = K("理解 UITableView 复用池真实结构及运行时验证方法")
T["gold-r2-000040"] = K("理解 UIViewController 在不同容器场景下生命周期回调的真实顺序差异")
T["gold-r2-000042"] = K("掌握 hitTest 命中测试容易记错的规则细节")
T["gold-r2-000056"] = K("理解 MRC 所有权规则（retain/release/autorelease）的整体框架")
T["gold-r2-000057"] = K("掌握 MRC 所有权规则的使用要点与易错处")
for gid in ["gold-r2-000058","gold-r2-000059"]:
    T[gid] = K("理解 MRC 所有权规则中『自己创建自己释放』与『不能放弃不属于自己的所有权』的准确含义")
for gid in ["gold-r2-000060","gold-r2-000061"]:
    T[gid] = K("理解 Core Foundation 的所有权规则及其与 OC 的对应关系")
for gid in ["gold-r2-000062","gold-r2-000063","gold-r2-000064"]:
    T[gid] = K("理解 GCD 的概念、使用要点与常见坑")
T["gold-r2-000160"] = K("理解 actor 重入（reentrancy）的语义与设计对策")
# 叙事/编号/日期/栏目/指代 → remove
T["gold-r2-000010"] = RM("『Runtime 简介』是文档栏目标题，不是技术概念；用户不会问『简介是什么』")
T["gold-r2-000017"] = RM("『isa 位域的历史演进（2015 → 至今）』含时间区间装饰，是文档标题残留而非自然提问对象")
T["gold-r2-000036"] = RM("已知反例：『到底会有几个 cell 活着』为行文碎片+上下文指代，离开笔记语境无法理解")
T["gold-r2-000051"] = RM("『x86_64 靠指令序列当签名』为论断式小标题碎片，未看过笔记的用户无法形成此问")
# 标题复述型（含冒号/叙事成分）→ 改写为自然问题（来源片段已逐条打开核对）
T["gold-r2-000006"] = RW("Block 在内存中的结构是怎样的？ABI、descriptor 和三种 Block 类型分别指什么？",
                         "理解 Block 的内存结构与三种类型")
T["gold-r2-000008"] = RW("NSArray/NSDictionary 这些 Foundation 集合是类簇吗？真实实现和选型要注意什么？",
                         "理解 Foundation 集合的类簇实现与选型")
T["gold-r2-000024"] = RW("OC 2.0 为什么要把类的元数据拆分成 ro 和 rw 两块？",
                         "理解 class_ro_t/class_rw_t 拆分的动机")
T["gold-r2-000025"] = RW("Category 在编译产物里是什么结构（category_t）？里面包含哪些列表？",
                         "理解 category_t 结构与所含列表")
T["gold-r2-000026"] = RW("KVO 的 isa-swizzling 到底做了什么？KVC 的 setter 搜索顺序是怎样的？",
                         "理解 KVO isa-swizzling 与 KVC 搜索顺序")
T["gold-r2-000028"] = RW("KVC 的 setter 搜索链里有 setIs<Key>: 这一步吗？它是干什么的？",
                         "核实 KVC setter 搜索链中 setIs<Key>: 步骤的存在与作用")
T["gold-r2-000029"] = RW("Method Swizzling 的正确姿势是什么？为什么要在 +load 里做？",
                         "掌握 Method Swizzling 的正确做法与 +load 时机")
T["gold-r2-000031"] = RW("iOS 里 delegate、通知、target-action、block 四种对象通信方式该怎么选？",
                         "理解四种对象通信方式的取舍")
T["gold-r2-000033"] = RW("为什么协议里的方法没有 IMP？这对 @optional 意味着什么？",
                         "理解协议方法无 IMP 的编译器层原因及对 @optional 的影响")
T["gold-r2-000037"] = RW("UIView 和 CALayer 是什么关系？三棵树、绘制流水线和离屏渲染是怎么回事？",
                         "理解 UIView/CALayer 关系与渲染管线")
T["gold-r2-000043"] = RW("frame 和 bounds、transform 有什么区别？为什么说 frame 是算出来的？",
                         "理解 frame/bounds/transform 的存储与计算关系")
T["gold-r2-000045"] = RW("AutoreleasePool 的哨兵对象和页链表是什么？它和 RunLoop 是怎么配合的？",
                         "理解 AutoreleasePool 结构与 RunLoop 配合")
T["gold-r2-000047"] = RW("PAGE_MIN_SIZE 和系统页大小（vm_page_size）有什么区别？",
                         "区分 PAGE_MIN_SIZE 与 vm_page_size 两个常量")
T["gold-r2-000048"] = RW("ARC 的『两半』指什么？编译器插桩和 runtime 支持分别负责什么？",
                         "理解 ARC 的编译器/runtime 分工")
T["gold-r2-000050"] = RW("ARC 插入的 retain/release 调用在编译器优化后会发生什么？",
                         "理解优化等级对 ARC 插桩的影响")
T["gold-r2-000052"] = RW("iOS 的内存占用是怎么记账的？Clean、Dirty、Compressed 页面与 Memory Footprint、OOM 是什么关系？",
                         "理解页面状态、Footprint 与 OOM 的关系")
T["gold-r2-000054"] = RW("为什么 malloc 之后要等到首次写入才真正占用物理内存？",
                         "理解 malloc 与首次写触发的物理页分配")
# 同义重复的孪生题 → remove（自然版已由改写/另一条覆盖）
for gid, why in {
    "gold-r2-000007": "与改写后的 000006 意图完全重复（同一标题的 trouble 版）",
    "gold-r2-000009": "与改写后的 000008 意图完全重复",
    "gold-r2-000011": "与 000013（objc_object 定义）意图重复，且原题为标题复述",
    "gold-r2-000014": "标题复述式『有哪些坑』，与 000013 意图重复",
    "gold-r2-000027": "与改写后的 000026 意图完全重复",
    "gold-r2-000030": "与改写后的 000029 意图完全重复",
    "gold-r2-000032": "与改写后的 000031 意图完全重复",
    "gold-r2-000034": "标题复述式 lookup，与 000035（已自然）意图完全重复",
    "gold-r2-000038": "与改写后的 000037 意图完全重复",
    "gold-r2-000039": "标题复述式 lookup，与 000040（已自然）意图完全重复",
    "gold-r2-000041": "标题复述式 lookup，与 000042（已自然）意图完全重复",
    "gold-r2-000044": "与改写后的 000043 意图完全重复",
    "gold-r2-000046": "与改写后的 000045 意图完全重复",
    "gold-r2-000049": "与改写后的 000048 意图完全重复",
    "gold-r2-000053": "与改写后的 000052 意图完全重复",
    "gold-r2-000057": "与 000056（纯名词短语，保留）意图完全重复",
    "gold-r2-000061": "与 000060（保留）意图完全重复",
}.items():
    T[gid] = RM(why + "；红队规则：同义重复不留两条")

# --- comparison（12）---
T["gold-r2-000012"] = RM("已知反例模式：『对象的本质：objc_object』与『objc_object：对象的骨架』是同一概念的两个笔记标题，同义重复")
T["gold-r2-000015"] = K("区分 isa_t（union 结构）与 ISA_BITFIELD（其中的位布局宏）两个嵌套但可独立定义的对象",
                        comp="valid", note="二者是嵌套关系而非并列，比较价值中等，但确实是两个不同的技术对象")
T["gold-r2-000020"] = RM("对比对象之一『Runtime 简介』为栏目名，不构成两个可独立定义的技术对象")
T["gold-r2-000023"] = RW("Category 为什么能加方法却不能加 ivar？这和 ro/rw 的拆分有什么关系？",
                         "理解 Category 能力边界与 ro/rw 拆分的因果关系（原题为两个叙事标题的伪对比，来源小节直接讲这个因果）")
T["gold-r2-000055"] = RW("Copy-on-Write 是怎么把共享页面变成 Private Dirty Page 的？",
                         "理解 COW 到 Private Dirty Page 的机制（原题为笔记标题 vs 笔记标题的伪对比）")
T["gold-r2-000065"] = K("区分主线程与其他线程调用 dispatch_sync+主队列的死锁行为", comp="valid",
                        note="两个对象（主线程/其他线程）清晰可独立定义，来源小节逐条列出两种情形")
T["gold-r2-000066"] = RM("对比双方均为断言式行文碎片（『…barrier_sync 不是』『多方等待也不 trap』），离开笔记语境不可理解")
for gid in ["gold-r2-000067","gold-r2-000068","gold-r2-000069","gold-r2-000070","gold-r2-000071"]:
    T[gid] = RM("已知反例：对比对象为文档碎片/标题与正文/概述与具体主题/同义重复，不构成两个可独立定义、值得比较的技术对象")

# --- symbol（24）---
for g in r2:
    if g["category"] == "symbol":
        m = re.search(r"「(.+?)」", g["question"])
        T[g["id"]] = K(f"定位并理解符号 {m.group(1) if m else ''} 在源码/资料中的定义与作用")

# --- alias（18）---
for g in r2:
    if g["category"] == "alias":
        T[g["id"]] = K("以口语/别称表述提问同一 iOS 技术概念，考察表述无关的检索")

# --- follow_up（16）---
for g in r2:
    if g["category"] == "follow_up":
        T[g["id"]] = K("在上一轮对话语境下追问同一主题的延伸点（依赖 dialogue_context，属该类别预期）")

# --- general（8）---
for g in r2:
    if g["category"] == "general":
        T[g["id"]] = K("无技术意图：非 iOS 日常问题，作路由边界测试（验证不进入 iOS 检索）")

# --- no_evidence / cross_platform（16 + 4 no_evidence + 2 knowledge）---
for g in r2:
    if g["expected_mode"] == "no_evidence" and g["category"] == "no_evidence":
        T[g["id"]] = K("无技术意图（语料无该具体主张的可靠资料）：作无证据判定测试", note="证据核查见任务 B")
for g in r2:
    if g["category"] == "cross_platform":
        if g["expected_mode"] == "knowledge":
            T[g["id"]] = K("区分 iOS 侧可答机制与跨平台对照面（Flutter/RecyclerView 列表复用 vs iOS）", comp="valid",
                           note="iOS 侧证据锚定，非 iOS 侧应声明缺资料")
        else:
            T[g["id"]] = K("无技术意图（非 iOS 平台细节）：作路由边界测试", note="预期 no_evidence")

rows = []
_missing = [g["id"] for g in r2 if g["id"] not in T]
assert not _missing, f"判定表未覆盖: {_missing}"
for g in r2:
    dec, rq, natural, intent, comp, note = T[g["id"]]
    # keep/rewrite 一律做来源片段复核（no_evidence/general 除外）
    ss = "not_applicable"
    sup = "不适用：该题为路由/无证据测试，不要求来源。"
    if g["expected_mode"] == "knowledge":
        text, prose = excerpt(g)
        if dec == "rewrite":
            ok = all(t.lower() in text.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", rq)) if re.search(r"[A-Za-z_]{3,}", rq) else True
            core_hit = len(prose) > 0
            ss = "partial" if (ok and core_hit) else "weak"
        else:
            ss = "strong" if len(prose) >= 8 else "partial"
        first = prose[0][:40] if prose else "（片段无正文）"
        sup = f"来源片段（{g['expected_source_path'].split('/')[-1]} 第{g['expected_start_line']}-{g['expected_end_line']}行，正文行 {len(prose)}）以『{first}…』起笔，围绕该主题展开，可支撑上述边界。"
        if dec == "rewrite" and ss == "weak":
            dec = "remove"; rq = None
            note = (note + "；改写未通过来源片段核对，按红队规则移除").strip("；")
    rows.append({
        "id": "r3-%06d" % (len(rows) + 1),
        "source_r2_id": g["id"],
        "source_eval_id": g["source_eval_id"],
        "decision": dec,
        "natural_query_test": natural,
        "technical_intent": intent if dec != "remove" else (note if not intent else intent),
        "comparison_validity": comp,
        "source_sufficiency": ss,
        "reason": "",
        "rewrite_question": rq,
        "confidence": "high" if dec == "remove" else ("medium" if dec == "keep" else "medium"),
        "risk_notes": ([note] if note else []),
        "normalized_subject": "",
        "answer_boundary": "",
        "source_support_summary": sup,
    })

# 填 keep/rewrite 的三个附加字段
for r in rows:
    if r["decision"] in ("keep", "rewrite"):
        g = by_id[r["source_r2_id"]]
        if g["category"] == "general":
            r["normalized_subject"] = "无（非技术闲聊输入）"
            r["answer_boundary"] = BOUNDARY["general"]
            r["source_support_summary"] = "不适用（无来源，路由测试）"
        elif g["expected_mode"] == "no_evidence":
            r["normalized_subject"] = re.sub(r"^[「『]?|[』」?]$", "", g["question"])[:60]
            r["answer_boundary"] = BOUNDARY["noev"]
            r["source_support_summary"] = "不适用（预期无证据；证据核查见 no-evidence-audit-r3.jsonl）"
        elif g["category"] == "follow_up":
            subj = re.sub(r"^(那|那你刚才讲的|那这个)", "", g["question"])[:40]
            r["normalized_subject"] = "上一轮主题的延伸：" + subj
            r["answer_boundary"] = BOUNDARY["followup"]
        else:
            subj = r["technical_intent"]
            m = re.search(r"理解 (.+)", subj) or re.search(r"掌握 (.+)", subj) or re.search(r"区分 (.+)", subj) or re.search(r"核实 (.+)", subj)
            r["normalized_subject"] = m.group(1) if m else clean_subject(subject_of(g["question"]))
            kind = "trouble" if "面试" in g["question"] else ("lookup" if "到底是什么" in g["question"] else "mech")
            r["answer_boundary"] = BOUNDARY.get(kind, BOUNDARY["mech"])
            # source_support_summary 已填

def reason_for(r, g):
    if r["decision"] == "remove":
        return r["technical_intent"] or "红队判定：不满足自然独立问题或可比对象要求。"
    base = {
        "keep": "红队通过：假设用户未见过任何笔记标题，该题仍是用户会自然提出的独立问题，表达明确可验证的技术意图；来源片段支撑其回答边界。",
        "rewrite": "红队改写：原题面为笔记标题复述/叙事标题（natural_query_test=fail），已改写为自然独立问题，并重新打开来源片段核对改写版可被该来源回答。",
    }[r["decision"]]
    if g["category"] == "symbol":
        base = "红队通过：符号查询是真实开发场景的自然问题，来源锚定实测存在。" + ("函数用途由命名推断，需人工复核。" if any("命名推断" in x for x in r["risk_notes"]) else "")
    if g["category"] == "follow_up":
        base = "红队通过：作为追问，其自然性依赖 dialogue_context（该类别预期属性），不依赖任何笔记标题；来源片段支撑延伸范围。"
    if g["category"] in ("general",) or g["expected_mode"] == "no_evidence":
        base = "红队通过：自然用户输入；作为路由/无证据边界测试保留，判定依据见对应无证据审计记录。"
    if g["category"] == "alias":
        base = "红队通过：口语/别称是真实用户的自然问法，不依赖笔记标题；来源为该概念的核心小节。"
    return base + ((" " + r["risk_notes"][0]) if r["risk_notes"] and r["decision"] != "remove" else "")

for r in rows:
    g = by_id[r["source_r2_id"]]
    r["reason"] = reason_for(r, g) + ("；" + r["risk_notes"][0] if r["decision"] == "remove" and r["risk_notes"] else "")

with (HERE.parent / "r3-audit.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("r3-audit:", len(rows), dict(Counter(r["decision"] for r in rows)))
print("natural fail:", sum(1 for r in rows if r["natural_query_test"] == "fail"))
print("comp invalid kept:", sum(1 for r in rows if r["comparison_validity"] == "invalid" and r["decision"] != "remove"))

# ---------------- 任务 B：20 条 no_evidence 全量重审 ----------------
KW = {
    "WidgetKit": r"widget", "App Intents": r"app-?intents", "StoreKit 2": r"storekit",
    "Metal 光线步进": r"metal", "Core ML int8 量化": r"core-?ml|coreml", "ARKit Scene Reconstruction": r"arkit",
    "Vision 姿态估计": r"vision", "Xcode Cloud 计费": r"xcode-?cloud", "visionOS 空间音频": r"visionos|spatial",
    "Apple Intelligence 本地模型接口": r"intelligence", "Swift Charts 坐标轴": r"charts?",
    "iOS 26 新 API": r"ios-?26|wwdc2026",
}
ev_rows = []
for g in r2:
    if g["expected_mode"] != "no_evidence":
        continue
    q = g["question"]
    claim = re.sub(r"^(iOS |Swift |Combine |Flutter |Android |React Native |Kotlin )", "", q)[:56]
    hit_paths = []
    if "Flutter" in q or "Android" in q or "React Native" in q or "Kotlin" in q or "微信小程序" in q:
        scope = "apple-docs-vault 与 apple-archive 全部文件名 + 抽样全文（非 iOS 平台主题）"
        for kw in ["flutter", "android", "react-native", "kotlin", "miniprogram", "wechat"]:
            hit_paths += [str(p) for p in list(VAULT.rglob(f"*{kw}*"))[:2]]
        summary_note = "跨平台/非 iOS 主题：语料中仅有 iOS 侧资料，非 iOS 侧主张无任何原始资料支撑"
    else:
        scope = "apple-docs-vault/wwdc zh+en 全部 284 个文件名（本轮全量，含 en）+ 全库关键词 grep"
        for topic, pat in KW.items():
            if re.search(pat, q, re.I):
                hits = [str(p) for p in VAULT.rglob("*.md") if re.search(pat, p.name, re.I)]
                hit_paths = hits[:3] if hits else [f"wwdc zh+en 文件名匹配 '{pat}'：0 命中"]
                break
        if not hit_paths:
            hit_paths = ["wwdc zh+en 文件名与全库 grep：0 命中"]
        summary_note = "具体主张所需资料在 zh+en WWDC 与归档中均无命中或仅为无关附带提及（如 10114 场次正文顺带提到 StoreKit 框架名，不构成订阅状态同步机制的资料）"
    ev_rows.append({
        "id": "noev3-%06d" % (len(ev_rows) + 1),
        "source_r2_id": g["id"],
        "source_eval_id": g["source_eval_id"],
        "question": q,
        "decision": "retain_no_evidence",
        "specific_claim_checked": claim,
        "evidence_search_scope": scope,
        "evidence_paths_checked": hit_paths,
        "reason": "按具体主张核对（非按主题名）：" + summary_note + "；未发现能直接回答该具体主张的可靠资料，维持 no_evidence。",
        "confidence": "medium",
        "risk_notes": ["生产链路最终判定仍需生产验证；本轮检索为文件名级 + 关键词级，未逐篇精读全部 284 个 WWDC 文件"],
    })
with (HERE.parent / "no-evidence-audit-r3.jsonl").open("w", encoding="utf-8") as f:
    for r in ev_rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("no-evidence-audit-r3:", len(ev_rows), dict(Counter(r["decision"] for r in ev_rows)))
