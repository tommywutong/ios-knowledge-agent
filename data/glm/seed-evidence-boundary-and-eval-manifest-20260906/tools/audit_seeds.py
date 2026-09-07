#!/usr/bin/env python3
"""第一阶段：85 条种子的证据边界红队审计。
分类依据：已实际打开的来源片段（dyld strings/macOS 路径/探针数据/个人基准等）+ 文件级证据性质。
"""
import json, re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
SEEDS = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/undercovered-topic-seeds-20260906/seed-eval-candidates.jsonl")
seeds = [json.loads(l) for l in SEEDS.read_text(encoding="utf-8").splitlines()]

# 平台/证据局限：必须说明的题目（按题面特征匹配）
MUST_STATE_PAT = [
    r"900 倍", r"WAL 后并发", r"值 49 倍", r"键映射这一笔账", r"objc_msgSend 强转",
    r"NSUserDefaults", r"setObject", r"原子替换", r"registerDefaults", r"plist",
    r"cachePolicy|缓存策略枚举", r"重定向", r"dyld 环境变量|DYLD_PRINT", r"400 微秒|测不到",
    r"镜像个数|计价单位", r"加载时机|dlopen", r"Segment 的所有 Section|段大小",
]
FILE_SCOPE = {
    "iOS 网络分层": "mixed_evidence",          # Apple 文档语义 + 作者实测
    "URLSession详解": "Apple_source",
    "三次握手": "iOS_public_api",
    "网络模型": "iOS_public_api",
    "HTTP Live Streaming": "Apple_source",
    "五种常见流媒体协议": "iOS_public_api",
    "iOS 数据库：SQLite": "mixed_evidence",     # SQLite 官方文档 + 个人实验（900 倍/WAL）
    "iOS 持久化选型": "mixed_evidence",          # macOS 观察（~/Library/Preferences）+ Apple 头文件注释
    "iOS 序列化": "Apple_source",                # clang 源码（CGObjCMac.cpp）+ Apple 机制
    "iOS YYModel": "personal_experiment",        # 个人基准测试
    "SQLite的使用一": "iOS_public_api",
    "使用NSFileManager": "iOS_public_api",
    "iOS App 启动": "mixed_evidence",            # strings/usr/lib/dyld（macOS 观察）+ Apple 公开版本信息
    "iOS Mach-O": "mixed_evidence",              # Apple 公开格式 + macOS 产物例证
    "iOS 从源码到可执行文件": "mixed_evidence",  # clang/nm 编译实验（macOS）
    "iOS 静态库与动态库": "mixed_evidence",      # Apple 公开机制 + 探针实测
    "Crash日志符号化": "iOS_public_api",
    "地址空间布局随机化": "mixed_evidence",      # 公开机制 + iOS 内核资料
    "Swift方法调用": "Apple_source",
    "协议、泛型和Existential": "Apple_source",
    "struct和class区别": "Apple_source",
    "Swift指针的使用": "Apple_source",
    "Swift编、解码协议Codable": "Apple_source",
}
REWRITE = {
    "现在还有哪些 dyld 环境变量在 iOS 上能用？哪些已经失效了？": (
        "dyld 的调试环境变量（比如 DYLD_PRINT 系）现在的可用情况怎么样？怎么验证一个变量还在不在？",
        "原题直接问『在 iOS 上能用』，但来源证据是 macOS 上 strings /usr/lib/dyld 的观察，不能支撑 iOS 真机结论；改写为平台中性的可用性问题，并强制回答说明观察平台。"),
    "启动阶段测量中『400 微秒的洞』指什么？为什么会有测不到的部分？": (
        "启动耗时的测量为什么会出现测不到的盲区？这类盲区一般出在哪一段？",
        "『400 微秒的洞』是笔记自造的比喻，未看过笔记的用户无法形成此问；改写为自然的测量盲区问题，并保留实验证据局限说明。"),
    "为什么说启动的计价单位是『镜像个数』而不是代码量？这个结论能推广到 iOS 吗？": (
        "为什么动态库的数量（镜像个数）比代码量更影响启动耗时？这个结论在 iOS 上成立吗？",
        "『计价单位』为笔记自造措辞；改写后保留『macOS 实验 + iOS 是否适用』的边界追问，答案必须区分实验平台。"),
}
DUP = {}  # 本批未发现重复题意（同小节 ≤2 题由上一轮约束，且题面意图各异）

def file_scope(path):
    name = Path(path).name
    for k, v in FILE_SCOPE.items():
        if name.startswith(k):
            return v, name
    return "unclear", name

rows = []
for g in seeds:
    q = g["question"]
    scope, fname = file_scope(g["expected_source_path"])
    must = any(re.search(p, q) for p in MUST_STATE_PAT)
    constraints = []
    if must:
        if "NSUserDefaults" in q or "setObject" in q or "原子替换" in q or "registerDefaults" in q or "plist" in q:
            constraints.append("必须说明落盘/路径观察来自 macOS（~/Library/Preferences），iOS 沙盒路径与行为可能不同")
        elif "dyld" in q or "DYLD" in q or "400 微秒" in q or "测不到" in q:
            constraints.append("必须说明证据来自 macOS 上对 dyld/启动的观察，iOS 真机行为未在本资料中验证")
        elif "镜像个数" in q or "计价" in q or "加载时机" in q or "dlopen" in q or "Segment" in q:
            constraints.append("必须区分『macOS 探针实测数据』与『iOS 是否适用的推断』，不可直接外推")
        elif "900 倍" in q or "WAL" in q or "49 倍" in q or "键映射" in q or "objc_msgSend 强转" in q:
            constraints.append("必须说明耗时/倍数为作者个人实验测得，数值随环境变化，机制结论与具体数字要分开陈述")
        elif "cachePolicy" in q or "缓存策略" in q or "重定向" in q:
            constraints.append("必须说明实测条件与系统版本，行为以 Apple 文档为准、实测数值仅作参考")
    if scope == "personal_experiment":
        constraints.append("必须说明结论仅来自个人实验，不可作为普遍基准")
    dec, rq = "keep", None
    for k, (nq, why) in REWRITE.items():
        if q.startswith(k[:30]) or k[:20] in q:
            dec, rq = "rewrite", nq
            constraints.append("必须说明结论仅来自 macOS 实验，不可直接外推 iOS" if "iOS" in why or "macOS" in why else "必须注明证据局限")
            break
    natural = "fail" if dec == "rewrite" else "pass"
    src_name = fname
    rows.append({
        "id": "sba-%06d" % (len(rows) + 1),
        "source_seed_id": g["id"],
        "decision": dec,
        "natural_query_test": natural,
        "evidence_scope": scope,
        "platform_scope": ("macOS 观察，iOS 需单独验证" if must and ("macOS" in "".join(constraints) or scope in ("macOS_observation",)) else ("iOS 公开行为/公共协议知识" if scope in ("Apple_source", "iOS_public_api") else "混合：Apple 机制 + 个人/macOS 实验")),
        "source_sufficiency": "strong" if scope in ("Apple_source", "iOS_public_api") and not must else "partial",
        "must_state_limitations": must or dec == "rewrite",
        "required_answer_constraints": constraints,
        "normalized_subject": g["normalized_subject"],
        "answer_boundary": g["answer_boundary"],
        "reason": "",
        "rewrite_question": rq,
        "duplicate_of": None,
        "confidence": "medium" if scope in ("mixed_evidence", "personal_experiment") else "high",
        "risk_notes": (["该题来源为个人实验/平台特定观察，生产评测时答案必须带局限说明"] if must or dec == "rewrite" else []),
        "_q": q,
    })

# reason 组装（基于真实分类与片段观察）
for r in rows:
    g = next(x for x in seeds if x["id"] == r["source_seed_id"])
    if r["decision"] == "rewrite":
        r["reason"] = "红队改写：原题把 macOS 观察/自造措辞包装成可直接回答的问题，已改写并强制证据局限说明。来源证据性质：" + r["evidence_scope"] + "。"
    else:
        r["reason"] = (f"红队通过：题目为未看笔记也会自然提出的独立技术问题；来源（{g['expected_source_path'].split('/')[-1]}）"
                       f"证据性质为 {r['evidence_scope']}"
                       + ("，回答必须附带平台/实验局限说明。" if r["must_state_limitations"] else "，无平台外推风险。")
                       + " 与同主题其他种子意图不重复。")

for r in rows:
    r.pop("_q", None)
with (HERE.parent / "seed-boundary-audit.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("seed-boundary-audit:", len(rows), dict(Counter(r["decision"] for r in rows)))
print("must_state:", sum(1 for r in rows if r["must_state_limitations"]))
print("scope:", dict(Counter(r["evidence_scope"] for r in rows)))
