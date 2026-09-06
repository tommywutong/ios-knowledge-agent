#!/usr/bin/env python3
"""只读生成 eval-candidates/*.jsonl。
来源锚定：每个 knowledge 题的 expected_source_path 必须真实存在，
行号由脚本在原文件中实际定位（标题行/短语行），定位失败即丢弃并记录。
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path("/Users/tommywu/Desktop/iOS知识agentt")
OUT_DIR = HERE.parent / "eval-candidates"
SPECIALS = json.loads((HERE / "eval_specials.json").read_text(encoding="utf-8"))
INDEX = json.loads((HERE / "corpus_index.json").read_text(encoding="utf-8"))

SUMMER = Path("/Users/tommywu/Desktop/26暑期内容")
OBS = Path("/Users/tommywu/Obsidian/iOS/20 专题笔记")
OBJC = SUMMER / "iOS底层源码探索/objc4/runtime"
VAULT = ROOT / "data/repos/apple-docs-vault"

def topic_of(path):
    p = path
    for key, t in [
        ("Runtime/", "runtime"), ("Runtime 与对象通信/", "kvc-kvo-notify"),
        ("内存管理/", "memory"), ("对象模型/", "memory"),
        ("并发与运行循环/", "runloop-gcd"), ("UIKit 与渲染/", "uikit"),
        ("Block/", "block"), ("架构与网络/", "network"),
        ("持久化与序列化/", "persistence"), ("编译链接与启动/", "build-startup"),
        ("Foundation", "foundation"),
    ]:
        if key in p:
            return t
    for key, t in [
        ("RunLoop", "runloop-gcd"), ("Runtime", "runtime"), ("GCD", "runloop-gcd"),
        ("Block", "block"), ("KVC", "kvc-kvo-notify"), ("KVO", "kvc-kvo-notify"),
        ("URLSession", "network"), ("HTTP", "network"), ("网络", "network"),
        ("离屏渲染", "uikit"), ("图层", "uikit"), ("Auto Layout", "uikit"),
        ("ScrollView", "uikit"), ("视图", "uikit"), ("UIView", "uikit"), ("CALayer", "uikit"),
        ("锁", "runloop-gcd"), ("线程", "runloop-gcd"), ("多线程", "runloop-gcd"),
        ("归档", "persistence"), ("存储", "persistence"), ("SQLite", "persistence"), ("NSCache", "foundation"),
        ("Mach-O", "build-startup"), ("静态库", "build-startup"), ("动态库", "build-startup"), ("dyld", "build-startup"),
        ("ASLR", "build-startup"), ("Crash", "build-startup"), ("符号", "build-startup"),
        ("内存", "memory"), ("属性", "memory"), ("weak", "memory"), ("strong", "memory"), ("copy", "memory"),
        ("关联对象", "runtime"), ("category", "runtime"), ("分类", "runtime"), ("Method", "runtime"),
        ("struct", "swift-interop"), ("Swift", "swift-interop"), ("协议", "swift-interop"),
        ("事件", "uikit"), ("手势", "uikit"), ("动画", "uikit"), ("动画", "uikit"), ("转场", "uikit"),
        ("图片", "foundation"), ("图像", "foundation"), ("缓存", "foundation"),
        ("面试", "runtime"), ("CocoaPods", "build-startup"), ("LLDB", "build-startup"), ("Git", "build-startup"),
    ]:
        if key in Path(p).name:
            return t
    return "foundation"

TEMPLATE_POOL = [
    ("lookup", "easy", "answerable",
     lambda x, y, t: f"「{x}」到底是什么？请根据你的资料解释一下这个概念。",
     lambda x, t: [f"{x} 是什么", f"{x} 的定义", f"{x}概念"]),
    ("mech", "medium", "answerable",
     lambda x, y, t: f"请讲讲{x}的底层机制或工作原理，资料里有哪些关键细节？",
     lambda x, t: [f"{x} 的原理", f"{x} 机制", f"讲讲{x}"]),
    ("trouble", "hard", "answerable",
     lambda x, y, t: f"我在面试里被问到「{x}」的细节答得不好，请结合资料帮我系统梳理一遍，并指出容易踩的坑。",
     lambda x, t: [f"{x} 面试怎么答", f"{x} 常见坑", f"{x}细节梳理"]),
    ("compare", "medium", "comparison",
     lambda x, y, t: f"「{x}」和「{y}」在你的资料里是怎么区分的？各自的适用场景是什么？",
     lambda x, t: [f"{x} 和相关概念对比", f"{x} 与 {t} 主题里相近概念的区别", f"{x} 对比"]),
    ("boundary", "hard", "answerable",
     lambda x, y, t: f"「{x}」有哪些容易被忽略的边界条件或常见误区？资料里有没有对应说明？",
     lambda x, t: [f"{x} 的边界条件", f"{x} 误区", f"{x} 有什么坑"]),
    ("summary", "easy", "answerable",
     lambda x, y, t: f"帮我用资料里的内容概括一下「{x}」的要点，最好能给出出处行号。",
     lambda x, t: [f"{x} 要点总结", f"{x} 笔记", f"{x} 重点"]),
]

def pick_templates(i):
    a = TEMPLATE_POOL[i % len(TEMPLATE_POOL)]
    b = TEMPLATE_POOL[(i + 2) % len(TEMPLATE_POOL)]
    return [a, b] if a[0] != b[0] else [a, TEMPLATE_POOL[(i + 3) % len(TEMPLATE_POOL)]]

BAD_HEAD = re.compile(r"^(https?:|!|\d+\.\d*$|——|[-–—]+$)")

def load_file(path):
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    return text, text.split("\n")

def find_phrase(lines, phrase):
    for i, ln in enumerate(lines, 1):
        if phrase in ln:
            return i
    return None

def section_end(lines, start, level, nlines):
    pat = re.compile(r"^(#{1,%d})\s" % max(level, 1))
    for i in range(start, len(lines)):
        m = pat.match(lines[i])
        if m and i + 1 > start:
            return i
    return min(start + 60, nlines)

def ev_type(path):
    s = str(path)
    if "wwdc" in s:
        return "wwdc"
    if "/blogs/" in s:
        return "blog"
    if s.endswith((".h", ".m", ".mm", ".c", ".cpp", ".s", ".swift")):
        return "source_code"
    return "note"

records = []
used_ids = set()
used_questions = set()

def add(question, category, topic, difficulty, mode, path, start, end, aliases, rationale,
        dialogue=None, created="source-grounded", risks=None):
    if question in used_questions:
        return False
    used_questions.add(question)
    records.append({
        "id": "eval-%06d" % (len(records) + 1),
        "question": question,
        "category": category,
        "topic": topic,
        "difficulty": difficulty,
        "expected_mode": mode,
        "expected_source_path": path,
        "expected_start_line": start,
        "expected_end_line": end,
        "expected_evidence_type": ev_type(path) if path else None,
        "aliases": aliases[:5],
        "dialogue_context": dialogue or [],
        "rationale": rationale,
        "risk_notes": risks or [],
        "created_from": created,
    })
    return True

TEMPLATE_RISK = ["模板生成：题面与该小节内容适配需人工复核"]

# ---------- 1. 标题锚定的 knowledge 题（obsidian + tips 精选 + 面试文章） ----------
TIPS_KEEP = [
    "Block的本质", "KVC、KVO的本质", "RunLoop从入门到进阶", "Runtime从入门到进阶一",
    "Runtime从入门到进阶二", "分类category、load、initialize的本质和源码分析",
    "关联对象 Associated Object 的本质", "事件传递和响应链（Responder Chain）",
    "图像IO之图片加载、解码，缓存", "图层性能之离屏渲染、栅格化、回收池",
    "URLSession详解", "Grand Central Dispatch的使用", "线程同步之自旋锁",
    "Mach-O可执行文件", "静态库和动态库对比", "Crash日志符号化", "NSCache的使用",
    "深复制、浅复制、copy、mutableCopy", "协议、泛型和Existential Container",
    "委托、通知传值的用法与区别", "地址空间布局随机化ASLR及iOS内核如何实现随机化",
    "计时器CADisplayLink", "setNeedsLayout VS layoutIfNeeded", "UIScrollView的用法",
    "Auto Layout的使用", "KVC和KVO学习笔记", "Swift方法调用", "多线程简述",
    "线程同步之os_unfair_lock", "线程同步之@synchronized", "线程同步之互斥锁",
    "UIImage" ,
]
TIPS_KEEP = [t for t in TIPS_KEEP if t != "UIImage"]
stats = {"kept": 0, "skipped_phrase": 0}

for f in INDEX:
    path = f["path"]
    name = Path(path).name[:-3]
    is_obs = "Obsidian" in path
    is_tips = "tips-master" in path
    is_art = "ios-advanced" in path
    if is_tips and name not in TIPS_KEEP:
        continue
    cap = 10 if is_obs else (3 if is_tips else 2)
    topic = topic_of(path)
    text, lines = load_file(path)
    nlines = len(lines)
    heads = [h for h in f["headings"]
             if h["level"] <= 3 and 2 <= len(h["text"]) <= 50 and not BAD_HEAD.match(h["text"])]
    # 去重相邻同名
    seen, uniq = set(), []
    for h in heads:
        if h["text"] not in seen:
            seen.add(h["text"])
            uniq.append(h)
    heads = uniq[:cap]
    for idx, h in enumerate(heads):
        x = h["text"].strip().lstrip("#").strip()
        start = h["line"]
        end = section_end(lines, start, h["level"], nlines)
        if end <= start:
            end = min(start + 20, nlines)
        for k, (kind, diff, cat, qf, af) in enumerate(pick_templates(idx) + ([TEMPLATE_POOL[(idx + 4) % len(TEMPLATE_POOL)]] if topic == "runloop-gcd" else [])):
            y = heads[(idx + 1) % len(heads)]["text"] if kind == "compare" and len(heads) > 1 else None
            q = qf(x, y, topic)
            if q in used_questions:
                continue
            aliases = af(x, topic)
            if kind == "compare" and y:
                aliases = [f"{x} {y} 区别", f"{x} 和 {y} 对比", f"{x} 与 {y} 的差异"] + aliases[:2]
            add(q, cat, topic, diff, "knowledge", path, start, end, aliases,
                f"预期证据：{Path(path).name} 的「{x}」小节（第{start}-{end}行），来源锚定由标题行实测定位。",
                risks=TEMPLATE_RISK)
            stats["kept"] += 1

# ---------- 2. WWDC / 博客精选 ----------
VAULT_SEL = [
    ("wwdc/zh/wwdc2018/416-ios-memory-deep-dive.md", 3),
    ("wwdc/zh/wwdc2021/10180-detect-and-diagnose-memory-issues.md", 2),
    ("wwdc/zh/wwdc2016/720-concurrent-programming-with-gcd-in-swift-3.md", 2),
    ("blogs/zh/sealiesoftware/objc-explain-non-pointer-isa.md", 2),
    ("blogs/zh/sealiesoftware/objc-explain-so-you-crashed-in-objc-msgsend.md", 2),
    ("blogs/zh/sealiesoftware/objc-explain-exceptions-and-autorelease-pools.md", 2),
    ("blogs/zh/onevcat/objective-c中的block.md", 2),
    ("blogs/zh/leichunfeng/objective-c-category-的实现原理.md", 2),
    ("blogs/zh/southpeak/foundation-nskeyvalueobserving-kvo.md", 2),
]
for rel, cap in VAULT_SEL:
    p = VAULT / rel
    if not p.is_file():
        continue
    text, lines = load_file(str(p))
    nlines = len(lines)
    heads = []
    fence = False
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        m = re.match(r"^(#{1,3})\s+(.+?)\s*$", ln) if not fence else None
        if m and 2 <= len(m.group(2)) <= 60 and not BAD_HEAD.match(m.group(2)):
            heads.append({"level": len(m.group(1)), "text": m.group(2), "line": i})
    heads = heads[:cap]
    for idx, h in enumerate(heads):
        x = h["text"].strip()
        start = h["line"]
        end = section_end(lines, start, h["level"], nlines)
        for kind, diff, cat, qf, af in pick_templates(idx)[:2]:
            q = qf(x, None, "wwdc-doc" if "wwdc" in rel else "blog")
            aliases = af(x, "官方资料")
            add(q, cat, "wwdc-doc" if "wwdc" in rel else "blog", diff, "knowledge", str(p),
                start, end, aliases,
                f"预期证据：{rel} 的「{x}」小节（第{start}-{end}行）。",
                risks=TEMPLATE_RISK)

# ---------- 3. 符号题（objc4 + tips 精确符号） ----------
OBJC_FILES = {
    "isa.h", "objc-object.h", "objc-private.h", "objc-runtime-new.h", "objc-runtime-new.mm",
    "objc-cache.mm", "objc-weak.h", "objc-weak.mm", "objc-auto.mm", "NSObject.mm",
    "objc-sync.mm", "objc-references.mm", "objc-loadmethod.mm", "objc-class.mm",
    "objc-runtime.mm", "objc-sel.mm", "objc-opt.mm", "objc-os.mm", "objc-os.h", "objc-abi.h",
    "message.h", "Messengers.subproj/objc-msg-arm64.s",
}
sym_added = 0
for s in SPECIALS["symbols"]:
    q_main = f"objc4 源码（或对应资料）里的「{s['sym']}」是在哪里定义的？它的大致作用是什么？"
    placed = False
    for rel in s["files"]:
        if rel.startswith("TIPS/"):
            p = SUMMER / "tips-master/sources" / (rel[len("TIPS/"):] + ".md")
        else:
            p = OBJC / rel
        if not p.is_file():
            continue
        lines = load_file(str(p))[1]
        nlines = len(lines)
        ln = find_phrase(lines, s["sym"])
        if not ln:
            continue
        add(q_main, "symbol", s["topic"], "medium", "knowledge", str(p), ln, min(ln + 30, nlines),
            list(s["aliases"]) + [f"{s['sym']} 定义在哪"],
            f"精确符号题：预期证据在 {p.name} 第{ln}行附近（符号实测命中）。",
            risks=["符号作用描述为常识推断，源码细节需人工复核"])
        placed = True
        sym_added += 1
        break

# 追加：从 objc4 关键文件自动抽取函数符号
FUNC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*\s+)+[\*\s]*([A-Za-z_][A-Za-z0-9_]*)\s*\(")
SYM_FILES = ["objc-runtime-new.mm", "objc-cache.mm", "objc-weak.mm", "objc-sync.mm",
             "objc-references.mm", "objc-loadmethod.mm", "NSObject.mm", "objc-sel.mm"]
KEY = re.compile(r"objc_|weak|cache|class|method|autorelease|retain|release|dealloc|sel|swizzle|Category|load")
extra_syms = []
for fn in SYM_FILES:
    p = OBJC / fn
    if not p.is_file():
        continue
    lines = load_file(str(p))[1]
    seen_names = set()
    for i, ln in enumerate(lines, 1):
        m = FUNC_RE.match(ln)
        if m:
            nm = m.group(2)
            if nm in seen_names or not KEY.search(nm) or len(nm) < 8:
                continue
            seen_names.add(nm)
            extra_syms.append((nm, str(p), i, len(lines)))
# 确定性抽样 60 个
extra_syms = extra_syms[:: max(1, len(extra_syms) // 90)][:90]
for nm, path, ln, nlines in extra_syms:
    add(f"objc4 源码里有个函数叫「{nm}」，它是做什么的？定义在源码的什么位置？",
        "symbol", "source-symbol", "medium", "knowledge", path, ln, min(ln + 40, nlines),
        [nm, f"{nm} 函数", f"{nm} 定义位置"],
        f"精确符号题：函数签名在 {Path(path).name} 第{ln}行实测存在。",
        risks=["函数作用描述基于命名推断，需人工复核源码内容"])

# ---------- 4. 路由题：no_evidence / general / cross_platform ----------
for q in SPECIALS["no_evidence"]:
    add(q, "no_evidence", "routing", "medium", "no_evidence", None, None, None, [],
        "该主题在当前已索引语料中缺乏可靠原始证据（语料以 ObjC runtime/内存/RunLoop/UIKit 为主），"
        "预期应路由为 no_evidence 而不是编造知识回答；即使 FTS 有零星命中也不应视为充分证据。",
        created="adversarial-routing",
        risks=["个别主题可能在 apple-archive/bulk 的 FTS 有零星命中，最终判定需生产复核"])
for q in SPECIALS["general"]:
    add(q, "general", "general", "easy", "general", None, None, None, [],
        "明显的非 iOS 日常问题，预期直接走 general 模式，不进入 iOS 检索。",
        created="adversarial-routing")
for item in SPECIALS["cross_platform"]:
    mode = item["mode"]
    path, start, end = None, None, None
    risks_extra = []
    if mode == "knowledge" and item.get("path"):
        base = Path(item["path"])
        if base.is_file():
            lines = load_file(item["path"])[1]
            nlines = len(lines)
            ln = find_phrase(lines, item["phrase"]) or find_phrase(lines, item["phrase"].split()[0])
            if ln:
                path, start, end = item["path"], ln, min(ln + 40, nlines)
            else:
                mode = "no_evidence"
                risks_extra.append("未能在预期文件中定位短语，已降级为 no_evidence")
        else:
            mode = "no_evidence"
            risks_extra.append("预期文件不存在，已降级为 no_evidence")
    add(item["q"], "cross_platform", "routing", "medium", mode, path, start, end, [],
        "跨平台干扰题：" + item["why"] + "；预期模式 " + mode +
        ("；iOS 侧证据锚定于 " + Path(path).name if path else "。"),
        created="adversarial-routing",
        risks=["跨平台题的预期模式是设计意图，需人工确认与生产路由行为一致"] + risks_extra)

# ---------- 5. 别名/口语/改写题 ----------
for c in SPECIALS["alias_concepts"]:
    base = OBS / c["file"]
    if not base.is_file():
        p2 = SUMMER / "tips-master/sources" / c["file"]
        base = p2
    if not base.is_file():
        continue
    lines = load_file(str(base))[1]
    nlines = len(lines)
    ln = find_phrase(lines, c["phrase"])
    if not ln:
        continue
    for qi, q in enumerate(c["qs"]):
        add(q, "alias", topic_of(str(base)), "easy" if qi % 2 == 0 else "medium", "knowledge",
            str(base), ln, min(ln + 40, nlines),
            [c["concept"], c["phrase"], f"{c['concept']} 原理", f"{c['concept']} 面试"],
            f"口语/改写题：预期证据与「{c['concept']}」主条目相同（{base.name} 第{ln}行附近），"
            "考察别名与口语表达下的召回。",
            risks=["别名题与对应概念题共享证据，行号由短语实测定位"])
    extra_forms = [f"用大白话讲讲{c['concept']}，我基础不太好。",
                   f"{c['concept']}面试一般会怎么问？按资料里的内容准备一下。",
                   f"有没有适合自学{c['concept']}的资料段落？帮我定位一下。"]
    add(extra_forms[hash(c["concept"]) % 3], "alias", topic_of(str(base)), "medium", "knowledge",
        str(base), ln, min(ln + 40, nlines),
        [c["concept"], c["phrase"], f"{c['concept']} 入门", f"{c['concept']} 怎么学"],
        f"口语/改写题（学习咨询变体）：预期证据同「{c['concept']}」主条目。",
        risks=["别名题与对应概念题共享证据，行号由短语实测定位"])
    ctx = [
        {"role": "user", "content": c["qs"][0], "mode": "knowledge"},
        {"role": "assistant", "content": f"（上一轮回答概述了「{c['concept']}」的机制与要点，具体见资料对应小节。）", "mode": "knowledge"},
    ]
    add(f"那你刚才讲的{c['concept']}，里面最关键的一步是什么？为什么是它？", "follow_up", topic_of(str(base)), "medium",
        "knowledge", str(base), ln, min(ln + 40, nlines),
        [f"{c['concept']} 关键步骤", f"{c['concept']} 核心机制"],
        "追问题：『这里面』指代上一轮对「%s」的回答，必须继承上下文才能路由；预期检索同一主题。"
        % c["concept"],
        dialogue=ctx, created="follow-up-template",
        risks=["上一轮助手内容为合成占位，语义衔接需人工复核"])

# ---------- 6. 追问题 ----------
for f in SPECIALS["followups"]:
    base = OBS / f["path"]
    if not base.is_file():
        continue
    lines = load_file(str(base))[1]
    nlines = len(lines)
    ln = find_phrase(lines, f["phrase"])
    if not ln:
        ln = find_phrase(lines, f["phrase"].split(" ")[0])
    if not ln:
        continue
    ctx = [
        {"role": "user", "content": f["prev_q"], "mode": f["prev_mode"]},
        {"role": "assistant", "content": f["prev_sum"], "mode": f["prev_mode"]},
    ]
    add(f["q"], "follow_up", topic_of(str(base)), "medium", "knowledge", str(base),
        ln, min(ln + 40, nlines), list(f["aliases"]),
        "追问题：只有携带上一轮上下文才可理解（『那/为什么』指代上一轮），"
        "预期继承上一轮 knowledge 模式并检索该主题；证据锚定在追问所涉小节。",
        dialogue=ctx, created="follow-up-template",
        risks=["追问短语为定位锚点，语义衔接需人工复核"])

# ---------- 7. 分批输出 ----------
batch_rules = [
    ("batch-001-runtime.jsonl", {"runtime"}),
    ("batch-002-memory.jsonl", {"memory"}),
    ("batch-003-runloop-gcd.jsonl", {"runloop-gcd"}),
    ("batch-004-uikit-network.jsonl", {"uikit", "network", "kvc-kvo-notify", "block", "foundation", "persistence", "swift-interop"}),
    ("batch-005-source-symbols.jsonl", {"source-symbol"}),
    ("batch-006-routing-no-evidence.jsonl", {"routing", "general"}),
    ("batch-007-alias-typo.jsonl", None),  # category=alias
    ("batch-008-follow-up.jsonl", None),   # category=follow_up
]
def in_batch(r, name, topics):
    if r["category"] == "alias":
        return name.endswith("alias-typo.jsonl")
    if r["category"] == "follow_up":
        return name.endswith("follow-up.jsonl")
    if topics is None:
        return False
    return r["topic"] in topics

counts = {}
for name, topics in batch_rules:
    rows = [r for r in records if in_batch(r, name, topics)]
    counts[name] = len(rows)
    with (OUT_DIR / name).open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(name, len(rows))
print("TOTAL:", len(records))
from collections import Counter
print("by category:", dict(Counter(r["category"] for r in records)))
print("by mode:", dict(Counter(r["expected_mode"] for r in records)))
print("by difficulty:", dict(Counter(r["difficulty"] for r in records)))
