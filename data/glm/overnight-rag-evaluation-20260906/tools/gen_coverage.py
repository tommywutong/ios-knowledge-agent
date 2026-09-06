#!/usr/bin/env python3
"""只读生成 source-coverage.jsonl：验证路径存在并统计真实行数。"""
import json, sys
from pathlib import Path

ROOT = Path("/Users/tommywu/Desktop/iOS知识agentt")
OUT = ROOT / "data/glm/overnight-rag-evaluation-20260906/source-coverage.jsonl"
OBS = "/Users/tommywu/Obsidian/iOS/20 专题笔记"
SUMMER = "/Users/tommywu/Desktop/26暑期内容"
VAULT = ROOT / "data/repos/apple-docs-vault"
ARCHIVE = ROOT / "data/repos/apple-developer-archive-vault"

# (source_id, path, content_kind, topic, platform, language, selection_reason, risk_notes)
ENTRIES = []

def add(source_id, path, kind, topic, platform, lang, reason, risks=None):
    ENTRIES.append((source_id, path, kind, topic, platform, lang, reason, risks or []))

# --- obsidian-ios：全部专题笔记 ---
obs_files = sorted(Path(OBS).rglob("*.md"))
for p in obs_files:
    rel = p.relative_to(OBS)
    add("obsidian-ios", str(p), "note", f"专题笔记：{p.stem}", "iOS", "zh",
        "核心个人资产，向量+FTS 双路索引，问答引用最高优先级来源之一",
        ["个人笔记理解可能有误差，引用时需与其他来源对照"] if "归档" in str(rel) or "AI 融合" in p.stem else [])

# --- summer2026：tips 精选 + 面试文章 ---
TIPS = [
    "Block的本质", "KVC、KVO的本质", "RunLoop从入门到进阶", "Runtime从入门到进阶一",
    "Runtime从入门到进阶二", "分类category、load、initialize的本质和源码分析",
    "关联对象 Associated Object 的本质", "事件传递和响应链（Responder Chain）",
    "iOS中定义属性时的atomic、nonatomic、copy、assign、strong、weak等几个特性的区别",
    "strong、weak和unowned的区别", "深复制、浅复制、copy、mutableCopy",
    "图像IO之图片加载、解码，缓存", "图层性能之离屏渲染、栅格化、回收池",
    "URLSession详解", "多线程简述", "Grand Central Dispatch的使用",
    "线程同步之自旋锁", "线程同步之互斥锁", "线程同步之@synchronized", "线程同步之os_unfair_lock",
    "Mach-O可执行文件", "静态库和动态库对比", "Crash日志符号化", "NSCache的使用",
    "Timer的使用", "计时器CADisplayLink", "setNeedsLayout VS layoutIfNeeded",
    "UIScrollView的用法", "UICollectionView及其新功能drag and drop",
    "UIViewPropertyAnimator的使用", "Auto Layout的使用", "协议、泛型和Existential Container",
    "struct和class区别", "Swift方法调用", "Swift指针的使用", "委托、通知传值的用法与区别",
    "地址空间布局随机化ASLR及iOS内核如何实现随机化", "WebKit的使用",
    "UserNotifications框架详解", "使用NSFileManager管理文件系统",
    "数据存储之归档解档 NSKeyedArchiver NSKeyedUnarchiver",
    "使用偏好设置、属性列表、归档解档保存数据、恢复数据", "HTTP Live Streaming 详解",
    "三次握手、七次握手、四次挥手", "网络模型：七层、五层、四层概念及功能分析",
    "UIImage?named?的陷阱" ,
]
TIPS = [t for t in TIPS if t != "UIImage?named?的陷阱"]
for name in TIPS:
    add("summer2026", f"{SUMMER}/tips-master/sources/{name}.md", "note", name, "iOS", "zh",
        "暑期学习 tips 文章，覆盖机制讲解与 API 用法，向量+FTS 索引")

ARTICLES = [
    "iOS面试题：Runloop", "iOS面试题：Runtime", "iOS面试题：内存管理",
]
# 面试文章实际文件名需验证，先扫描目录
art_dir = Path(SUMMER) / "awesome-ios-interview-main/articles/ios-advanced"
if art_dir.exists():
    for p in sorted(art_dir.glob("*.md")):
        add("summer2026", str(p), "note", p.stem, "iOS", "zh",
            "面试向进阶文章，问题形式与评测题风格接近，适合抽取 answerable/comparison 候选",
            ["目录/清单型文章风险：需确认有正文而非纯链接"])

# --- summer-labs：实验源码 ---
LAB = [
    ("MemoryMapLab/README.md", "md", "内存地图实验说明"),
    ("MemoryMapLab/MemoryMapLab/main.m", "source_code", "内存地图实验入口"),
    ("MemoryMapLab/MemoryMapLab/MemoryExperiment.m", "source_code", "对象内存布局实验代码"),
    ("MemoryMapLab/MemoryMapLab/AppDelegate.m", "source_code", "实验 App 代理"),
]
for rel, kind, topic in LAB:
    add("summer-labs", f"{SUMMER}/{rel}", kind, topic, "iOS", "mixed",
        "活跃实验源码，个人动手实验，可作为内存/对象模型的实践证据")

# --- objc4-source：关键 runtime 文件 ---
OBJC = [
    ("objc4/runtime/objc-runtime-new.h", "类/方法/Category 结构（新版 runtime）"),
    ("objc4/runtime/objc-runtime-new.mm", "类加载、方法查找、cache、weak 实现"),
    ("objc4/runtime/Messengers.subproj/objc-msg-arm64.s", "objc_msgSend 汇编快速路径"),
    ("objc4/runtime/objc-object.h", "对象布局、retain/release/isa 操作"),
    ("objc4/runtime/objc-opt.mm", "opt（方法缓存/协议列表）优化实现"),
    ("objc4/runtime/NSObject.mm", "NSObject 实现、alloc/retain/release/autorelease"),
    ("objc4/runtime/objc4-841.13/runtime/NSObject.h", None),  # 占位，不存在则跳过
    ("objc4/runtime/NSObject.h", "NSObject 接口"),
    ("objc4/runtime/isa.h", "nonpointer isa 位域定义"),
    ("objc4/runtime/objc-cache.mm", "方法缓存实现"),
    ("objc4/runtime/objc-weak.h", "weak 表结构"),
    ("objc4/runtime/objc-weak.mm", "weak 引用注册与置 nil"),
    ("objc4/runtime/objc-runtime-old.mm", "旧版 runtime（对照用）"),
    ("objc4/runtime/objc-auto.mm", "autorelease 相关"),
    ("objc4/runtime/objc-accessors.mm", "关联对象/属性访问器"),
    ("objc4/runtime/objc-loadmethod.mm", "+load 调用顺序"),
    ("objc4/runtime/Object.h", "根对象接口"),
]
for rel, topic in OBJC:
    if topic is None:
        continue
    add("objc4-source", f"{SUMMER}/iOS底层源码探索/{rel}", "source_code", topic, "iOS", "en",
        "objc4 官方源码镜像（排除旧版重复目录），符号级证据来源",
        ["type=source_code 生产降权，需与笔记/文档配合引用"])

# --- apple-docs-core：WWDC + 博客 ---
WWDC = [
    "wwdc/zh/wwdc2018/416-ios-memory-deep-dive.md",
    "wwdc/zh/wwdc2021/10180-detect-and-diagnose-memory-issues.md",
    "wwdc/zh/wwdc2024/10173-analyze-heap-memory.md",
    "wwdc/zh/wwdc2016/720-concurrent-programming-with-gcd-in-swift-3.md",
    "wwdc/zh/wwdc2025/312-improve-memory-usage-and-performance-with-swift.md",
    "wwdc/en/wwdc2018/416-ios-memory-deep-dive.md",
]
BLOGS = [
    "blogs/zh/sealiesoftware/objc-explain-non-pointer-isa.md",
    "blogs/zh/sealiesoftware/objc-explain-objc-msgsend-stret.md",
    "blogs/zh/sealiesoftware/objc-explain-so-you-crashed-in-objc-msgsend.md",
    "blogs/zh/sealiesoftware/objc-explain-exceptions-and-autorelease-pools.md",
    "blogs/zh/onevcat/objective-c中的block.md",
    "blogs/zh/leichunfeng/objective-c-category-的实现原理.md",
    "blogs/zh/southpeak/foundation-nskeyvalueobserving-kvo.md",
    "blogs/zh/cocoawithlove/how-blocks-are-implemented-and-the-consequences-cocoa-with-love.md",
]
for rel in WWDC:
    add("apple-docs-core", str(VAULT / rel), "wwdc", rel.split("/")[-1], "iOS", "mixed",
        "WWDC 官方逐字稿，权威等级最高，向量+FTS 双路")
for rel in BLOGS:
    add("apple-docs-core", str(VAULT / rel), "blog", rel.split("/")[-1], "iOS", "mixed",
        "经 content_filter 确认为 Apple 平台主题的技术博客，生产排序第三级",
        ["博客观点需与官方文档/源码对照"])

# --- apple-archive：抽样 ---
ARCH = [
    "documentation/Cocoa/Conceptual/MemoryMgmt",
    "qa/qa1490",
]
for rel in ARCH:
    base = ARCHIVE / rel
    if base.exists():
        mds = sorted(base.rglob("*.md"))[:2]
        for p in mds:
            add("apple-archive", str(p), "doc", p.parent.name, "iOS", "en",
                "英文官方历史文档归档抽样（FTS-only 来源），用于关键词兜底验证",
                ["无向量：纯语义问题可能搜不到，属预期取舍"])

ok, missing = [], []
for source_id, path, kind, topic, platform, lang, reason, risks in ENTRIES:
    p = Path(path)
    if not p.is_file():
        missing.append(path)
        continue
    lines = p.read_text(encoding="utf-8", errors="replace").count("\n") + 1
    ok.append({
        "source_id": source_id, "source_path": path, "content_kind": kind,
        "topic": topic, "platform": platform, "language": lang,
        "line_count_estimate": lines, "selection_reason": reason, "risk_notes": risks,
    })

with OUT.open("w", encoding="utf-8") as f:
    for r in ok:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"written {len(ok)} entries; missing {len(missing)}")
for m in missing:
    print("MISSING:", m)
from collections import Counter
print(Counter(r["source_id"] for r in ok))
