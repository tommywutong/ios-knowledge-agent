#!/usr/bin/env python3
"""只读生成 quality-findings.jsonl：对实际检查过的资料做质量标记。"""
import hashlib, json, re
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/tommywu/Desktop/iOS知识agentt")
OUT = ROOT / "data/glm/overnight-rag-evaluation-20260906/quality-findings.jsonl"
OBS = Path("/Users/tommywu/Obsidian/iOS/20 专题笔记")
SUMMER = Path("/Users/tommywu/Desktop/26暑期内容")
VAULT = ROOT / "data/repos/apple-docs-vault"
TIPS = SUMMER / "tips-master/sources"
ART = SUMMER / "awesome-ios-interview-main/articles/ios-advanced"
CONV = ROOT / "data/converted"

findings = []
def add(path, s, e, ftype, sev, summary, action, conf, risks=None):
    findings.append({
        "id": "quality-%06d" % (len(findings) + 1),
        "source_path": str(path), "start_line": s, "end_line": e,
        "finding_type": ftype, "severity": sev, "evidence_summary": summary[:300],
        "recommended_action": action, "confidence": conf, "risk_notes": risks or [],
    })

def load(p):
    return p.read_text(encoding="utf-8", errors="replace").split("\n")

# ---------- 1. WWDC 中英双语重复对（同一 session 两份逐字稿都在索引里） ----------
zh = {p.name: p for p in (VAULT / "wwdc/zh").rglob("*.md")}
en = {p.name: p for p in (VAULT / "wwdc/en").rglob("*.md")}
dup_pairs = sorted(set(zh) & set(en))
for name in dup_pairs[:210]:
    add(zh[name], 1, 1, "duplicate", "medium",
        f"同一 WWDC session「{name}」的中文版与英文版逐字稿均被 apple-docs-core 收录（zh/en 双份），"
        "检索时同内容会出现两份近似候选，挤占 top-k 名额。",
        "review_only", "high", ["两份内容对引用校验无害，但会降低来源多样性"])

# ---------- 2. 目录页 / 链接汇总页 ----------
DIR_HINT = re.compile(r"(目录|索引|CATALOG|_Index|README|汇总|导航|链接)")
def link_ratio(lines):
    n_link = sum(1 for ln in lines if re.search(r"\]\([^)]+\)", ln))
    return n_link / max(1, len(lines))
checked_dir_pages = 0
for base in [OBS, TIPS, ART]:
    for p in sorted(base.rglob("*.md")):
        stem = p.stem
        if not DIR_HINT.search(stem):
            continue
        lines = load(p)
        lr = link_ratio(lines)
        if lr > 0.25 or len(lines) < 40:
            add(p, 1, min(30, len(lines)), "directory_page",
                "low" if lr <= 0.5 else "medium",
                f"疑似目录/导航页：文件名含目录线索，链接行占比 {lr:.0%}，正文行数 {len(lines)}。",
                "review_only", "medium")
            checked_dir_pages += 1

# ---------- 3. 超长物理行（bad_conversion / line_risk） ----------
long_files = 0
for base in [OBS, TIPS, ART, VAULT / "wwdc/zh", VAULT / "blogs/zh"]:
    for p in sorted(base.rglob("*.md")):
        lines = load(p)
        if not lines:
            continue
        worst = max(range(len(lines)), key=lambda i: len(lines[i]))
        if len(lines[worst]) > 8000:
            add(p, worst + 1, worst + 1, "bad_conversion", "medium",
                f"存在超长单行（第{worst+1}行，{len(lines[worst])}字符），多为 docx/网页转换残留，"
                "影响切块粒度与 FTS 命中精度。",
                "split_chunk_candidate", "medium")
            long_files += 1
        elif len(lines[worst]) > 3000:
            add(p, worst + 1, worst + 1, "line_risk", "info",
                f"最长单行 {len(lines[worst])} 字符（第{worst+1}行），接近切块器兜底边界，命中后上下文易失焦。",
                "review_only", "low")
            long_files += 1
        if long_files > 90:
            break
    if long_files > 90:
        break

# ---------- 4. 内容完全重复（跨文件 hash 一致） ----------
by_hash = defaultdict(list)
for p in sorted(OBS.rglob("*.md")):
    t = p.read_text(encoding="utf-8", errors="replace")
    if len(t.strip()) < 200:
        continue
    by_hash[hashlib.sha256(t.encode()).hexdigest()].append(p)
for h, ps in by_hash.items():
    if len(ps) > 1:
        for p in ps[1:]:
            add(p, 1, 1, "duplicate", "medium",
                f"与 {ps[0].name} 内容逐字节相同（SHA-256 一致），重复索引会同屏出现两份相同候选。",
                "review_only", "high")

# ---------- 5. 近似重复 / 冲突：归档稿与正稿并存 ----------
for p in sorted(OBS.rglob("*.md")):
    if "归档" in str(p) or "AI 融合" in p.stem:
        add(p, 1, 1, "conflict", "medium",
            "个人笔记的归档/AI 融合稿仍在语料目录内，虽然部分被 config 排除，"
            "但若与正稿并存易被检索到旧版表述，与最新笔记冲突。",
            "manual_source_review", "medium",
            ["config.yaml 的 obsidian-ios 排除了 99 归档/**；未排除路径需逐条确认"])

# ---------- 6. 低 iOS 相关（tips 中的算法/通用工程篇） ----------
LOW_IOS = ["Git新功能：switch、restore", "教你系统学习Git", "AVL树", "二分查找 Binary Search",
           "二叉搜索树 Binary Search Tree", "二叉树 Binary Tree", "栈 Stack", "链表 LinkedList",
           "队列的四种实现方式：数组、双向链表、环形缓冲区、栈", "树 Tree 基本信息及实现",
           "时间复杂度与空间复杂度", "三次握手、七次握手、四次挥手", "网络模型：七层、五层、四层概念及功能分析",
           "软链接、硬链接的区别", "依赖反转原则", "单一职责原则", "开闭原则", "接口隔离原则",
           "里氏替换原则", "备忘录模式 Memento Pattern", "原型模式 Prototype Pattern",
           "生成器模式 Builder Pattern", "策略模式 Strategy Pattern", "适配器模式 Adapter Pattern",
           "迭代器模式 Iterator Pattern", "工厂模式 Factory Pattern",
           "Swift编、解码协议Codable", "CocoaPods的安装与使用", "使用CocoaPods创建公开、私有pod",
           "LLDB的使用", "正则表达式NSRegularExpression", "iOS正则表达式语法全集",
           "宏(#define)与常量(const)的使用", "条件编译 Conditional Compilation"]
for name in LOW_IOS:
    p = TIPS / (name + ".md")
    if p.is_file():
        n = len(load(p))
        add(p, 1, n, "low_ios_relevance", "info",
            "通用算法/工程/软技能主题，与 iOS 知识问答直接相关性低，作为证据被引用时说服力弱。",
            "review_only", "medium")

# ---------- 7. oss 镜像的来源等级风险 ----------
OSS = VAULT / "oss"
oss_samples = sorted(OSS.rglob("*.md"))[:4000]
oss_dirs = defaultdict(int)
for p in oss_samples:
    rel = p.relative_to(OSS)
    oss_dirs[rel.parts[0]] += 1
for d, n in sorted(oss_dirs.items(), key=lambda kv: -kv[1])[:14]:
    sample_p = next((OSS / d).rglob("*.md"))
    add(sample_p, 1, 1, "ambiguous_version", "info",
        f"apple-docs-bulk 的 oss/{d}/ 目录收录了 {n} 个第三方镜像/周报类文档（类型标记为 doc，"
        "与官方文档同级），生产排序中 doc 权重 1.12 会放大第三方内容，与『官方文档并列第一』的意图存在偏差。",
        "manual_source_review", "medium",
        ["apple-docs-bulk 只进 FTS 不进向量，影响范围限于关键词兜底路径"])

# ---------- 8. 明确正常的抽样 ----------
import random
random.seed(20260906)
norm_pool = sorted(TIPS.rglob("*.md")) + sorted(OBS.rglob("*.md"))
normal_done = 0
for p in random.sample(norm_pool, 60):
    lines = load(p)
    if not lines or link_ratio(lines) > 0.25 or max(len(l) for l in lines) > 3000:
        continue
    prose = sum(1 for ln in lines if len(ln.strip()) > 30)
    if prose < 10:
        continue
    add(p, 1, len(lines), "normal_sample", "info",
        f"抽样确认正常：正文行 {prose}/{len(lines)}，标题层级正常，无明显转换异常或重复。",
        "review_only", "medium")
    normal_done += 1

# ---------- 9. objc4 已排除目录仍在磁盘（提示误引用风险） ----------
for old in ["iOS底层源码探索/_弃用-objc4-818-debug", "iOS底层源码探索/objc4-756.2-参照旧版"]:
    p = SUMMER / old
    if p.is_dir():
        add(p / "runtime" if (p / "runtime").is_dir() else p, 1, 1, "duplicate", "low",
            "该旧版 objc4 目录已按 config 排除出索引，但仍存在于磁盘；生成评测/引用时须确认路径"
            "指向在索引中的 objc4/runtime，避免误引已排除的旧版本源码。",
            "review_only", "high")

# ---------- 9b. 博客 zh/en 双语重复对 ----------
bzh = {p.name: p for p in (VAULT / "blogs/zh").rglob("*.md")}
ben = {p.name: p for p in (VAULT / "blogs/en").rglob("*.md")}
for name in sorted(set(bzh) & set(ben))[:60]:
    add(bzh[name], 1, 1, "duplicate", "low",
        f"博客「{name}」的中英两份译文均被收录（blogs/zh 与 blogs/en），关键词检索时同一观点会双份出现。",
        "review_only", "medium")

# ---------- 9c. 归档与 bulk 镜像的超长行扫描 ----------
for base in [VAULT / "apple-docs", VAULT / "legacy-archive"]:
    if not base.is_dir():
        continue
    cnt = 0
    for p in sorted(base.rglob("*.md")):
        lines = load(p)
        if not lines:
            continue
        worst = max(range(len(lines)), key=lambda i: len(lines[i]))
        if len(lines[worst]) > 12000:
            add(p, worst + 1, worst + 1, "bad_conversion", "low",
                f"FTS-only 来源存在超长单行（第{worst+1}行，{len(lines[worst])}字符），"
                "整段文档可能被压缩成超长物理行，FTS 命中后返回的块会非常大。",
                "split_chunk_candidate", "medium")
            cnt += 1
            if cnt >= 18:
                break

# ---------- 9d. 归档索引页 ----------
for idx_dir in [VAULT / "_indexes", ROOT / "data/repos/apple-developer-archive-vault/_indexes"]:
    if not idx_dir.is_dir():
        continue
    for p in sorted(idx_dir.rglob("*.md"))[:12]:
        lines = load(p)
        lr = link_ratio(lines)
        if lr > 0.2:
            add(p, 1, len(lines), "directory_page", "low",
                f"索引/导航类文件：链接行占比 {lr:.0%}，正文密度低，被 FTS 收录后可能稀释关键词结果。",
                "review_only", "medium")

# ---------- 9e. 素材/归档与正稿同名近似重复 ----------
stems = defaultdict(list)
for p in sorted(OBS.rglob("*.md")):
    stems[re.sub(r"[\s：:（）()_-]", "", p.stem.lower())[:18]].append(p)
for k, ps in stems.items():
    if len(ps) > 1 and any(("素材" in str(p) or "归档" in str(p)) for p in ps):
        for p in ps[1:]:
            add(p, 1, 1, "duplicate", "low",
                f"与「{ps[0].name}」同名近似（归档/素材目录副本），主题重叠度高，检索时可能返回旧稿。",
                "review_only", "medium")

# ---------- 9f. 术语映射缺口（依据术语库生成阶段观察） ----------
TERM_GAP_NOTES = [
    ("Runtime/Part 2 - 消息发送与转发.md", "objc_msgSend/imp/cache 等符号在英文资料与中文笔记中的叫法不统一（消息发送/方法调用/msgSend），需别名表 bridging。"),
    ("内存管理/iOS weak 的实现：SideTable 与置 nil 的时机.md", "weak/sideTable/弱引用表 中英混用，查询『弱引用』未必命中 SideTable 源码块。"),
    ("并发与运行循环/iOS RunLoop：mode、source 与那张流程图今天还对不对.md", "RunLoop/运行循环/run loop 三种写法并存，英文查询与中文笔记存在词汇鸿沟。"),
    ("UIKit 与渲染/iOS UIView 与 CALayer：三棵树、绘制流水线与离屏渲染.md", "离屏渲染/offscreen rendering/屏外渲染 表述不一，且 GPU 合成相关英文术语密度高。"),
    ("编译链接与启动/iOS App 启动：三代 dyld、pre-main 与可测量的优化项.md", "pre-main/启动耗时/冷启动 混用，英文 dyld/load/bind 查询难以命中中文笔记。"),
    ("内存管理/iOS AutoreleasePool：哨兵、页链表与 RunLoop 的关系.md", "哨兵对象/POOL_BOUNDARY/sentinel 同义异形，别名缺失会降低符号查询召回。"),
    ("Runtime/Part 3 - Category：加载、覆盖与关联对象.md", "分类/类别/Category 三写法并存，关联对象/Associated Object 亦然。"),
    ("Runtime 与对象通信/iOS KVC 与 KVO：搜索顺序、isa-swizzling 与手动触发.md", "键值观察/KVO/观察者 混用；isa-swizzling 在中文笔记中的描述与英文源码注释存在术语映射缺口。"),
    ("Block/iOS Block 的变量捕获与 __block.md", "__block/byref/变量捕获 的英文符号与中文表述需要显式别名。"),
    ("并发与运行循环/iOS GCD：队列不是线程，以及死锁的准确边界.md", "串行队列/serial queue、栅栏/barrier 中英对照不完整。"),
]
for rel, note in TERM_GAP_NOTES:
    p = OBS / rel
    if p.is_file():
        add(p, 1, 1, "terminology_gap", "medium", note, "add_alias", "medium")

with OUT.open("w", encoding="utf-8") as f:
    for r in findings:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print("total:", len(findings))
print("type:", dict(Counter(r["finding_type"] for r in findings)))
print("severity:", dict(Counter(r["severity"] for r in findings)))
