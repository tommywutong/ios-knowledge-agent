#!/usr/bin/env python3
"""阶段 D：反例与对照集。a=manifest 现有条目，b=自然最小改写；不虚构证据。"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R4 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/seed-evidence-boundary-and-eval-manifest-20260906")
manifest = {r["id"]: r for r in (json.loads(l) for l in (R4 / "production-eval-manifest-candidates.jsonl").read_text(encoding="utf-8").splitlines())}

def find(kw):
    for mid, g in manifest.items():
        if kw in g["question"]:
            return mid, g
    raise KeyError(kw)

# (pair_type, a 的题面关键词, b 题（自然最小改写）, why_different, expected_difference)
PAIRS = [
 # (type, 定位键, 另一侧问题, why, expected)  非fu: a=manifest题/b=改写; fu: a=独立改写/b=manifest追问
 ("platform_shift", "Android 的 Handler 机制和 iOS RunLoop", "iOS 的 RunLoop 是怎么实现的？干什么的？",
  "a 是跨平台双主体主张（Android 侧零覆盖），b 只问 iOS 侧（资料充分）",
  "a 预期 no_evidence 或大幅声明 Android 侧缺失；b 预期 knowledge。同结构对应『有一般 SwiftUI 资料 vs SwiftUI 跑 Android』的对比（SwiftUI-Android 题在 r2 配额截断时未入黄金集，eval-001790）"),
 ("internal_vs_public", "白名单解码时", "NSSecureCoding 怎么用？",
  "a 问递归白名单的反例级细节，b 问基本用法；来源对 a 有专门反例，对 b 只有部分",
  "a 预期 direct；b 预期 partial（基本用法覆盖不全时需声明）"),
 ("internal_vs_public", "objc_msgSend 强转", "objc_msgSend 可以随意强转成任意 C 函数指针吗？",
  "a 问类型必须精确的原因（来源源码级解释），b 是可用是/否回答的窄问题",
  "a/b 预期同一小节；b 判分关注是否答出 ABI 层后果而非含糊的是/否"),
 ("platform_shift", "分界线在哪个系统版本", "iOS 16 是从哪个系统版本开始用 dyld4 的？",
  "a 问分界线（来源为 distribution-macOS 的 macOS tag 映射），b 直接要 iOS 精确版本",
  "a 可回答但必须声明 macOS tag 证据；b 预期语料不足，只能给出同期推断并声明非一手出处"),
 ("scope_shift", "WAL 后并发行为", "SQLite 不开事务写入到底能慢多少倍？",
  "a 问 WAL 机制差异，b 索要具体倍数；机制可由文档+实验支撑，数字只是个人实验",
  "a 预期 knowledge 且引用 WAL 小节；b 的答案只能引用个人实验数字并声明环境局限"),
 ("scope_shift", "900 倍", "SQLite 的 synchronous 参数设成 OFF 会怎样？",
  "a 问 900 倍归因，b 问来源中用于验证的 synchronous 参数",
  "a/b 预期同一小节；b 判分关注是否说明该参数作用与风险"),
 ("scope_shift", "镜像个数", "iOS 上每多一个动态库，启动会慢多少毫秒？",
  "a 问镜像个数与启动的关系（含 iOS 适用性追问），b 直接要 iOS 毫秒级数字",
  "a 预期回答机制 + 声明 macOS 实验；b 预期语料无 iOS 数字，只能声明无一手数据"),
 ("scope_shift", "测不到的盲区", "启动耗时的测量为什么会存在测不到的盲区？",
  "a=manifest 改写题（自然版），b 同边界更朴素问法；同一小节支撑",
  "a/b 预期同一小节；两者判分都要求实验局限说明"),
 ("symbol_vs_natural_language", "「objc_msgSend」是在哪里定义的", "objc 的消息发送流程是怎样的？",
  "a 是精确符号定位题，b 是自然语言机制题；命中资料类型与排序预期不同",
  "a 预期命中 objc4 源码/文档（query_planning 层）；b 预期命中笔记讲解；判分分别检查源码出处与机制覆盖"),
 ("symbol_vs_natural_language", "「objc_sync_enter」是在哪里定义的", "@synchronized 的底层是怎么加锁的？",
  "a 符号定位（objc_sync.mm），b 机制描述（应经规划命中同一文件）",
  "a 判分查源码出处；b 判分查机制覆盖与 objc_sync_enter/exit 引用"),
 ("symbol_vs_natural_language", "「cache_fill」是在哪里定义的", "方法缓存是什么时候被填充的？",
  "a 符号定位（objc-cache.mm），b 时机机制描述",
  "a 判分查源码出处；b 判分查时机机制覆盖"),
 ("follow_up_context", "KVO 原理，里面最关键的一步", "KVO 的 isa-swizzling 到底做了什么？",
  "a=独立机制题（r3 强集原有，因清单容量未入），b=清单内 KVO 追问（依赖上一轮）",
  "a 单轮直发即可判分；b 必须先构造多轮会话，判分检查是否继承 KVO 话题且不被无关旧主题污染"),
 ("follow_up_context", "RunLoop 模式，里面最关键的一步", "滚动的时候 timer 为什么会停？",
  "a=独立现象题（清单内种子），b=清单内 RunLoop 追问（『你刚才讲的 RunLoop 模式』依赖上一轮）",
  "a 单轮可判；b 若脱离上下文则『缓存』『慢速查找』指代不明，判分检查继承行为"),
 ("follow_up_context", "Block 类型，里面最关键的一步", "block 有哪几种？",
  "a=清单内 alias 独立题，b=清单内 Block 追问（『你刚才讲的 Block 类型』依赖上一轮）",
  "a 单轮可判；b 需继承上下文，判分检查指代解析"),
 ("follow_up_context", "GCD 死锁，里面最关键的一步", "在主线程里用 dispatch_sync 同步执行主队列任务一定会死锁吗？在其他线程调用呢？",
  "a=清单内独立机制题（comparison），b=清单内 GCD 死锁追问（『你刚才讲的 GCD 死锁』依赖上一轮）",
  "a 单轮可判；b 需继承上下文，判分检查指代解析与引用连续性"),
 ("no_evidence_near_miss", "StoreKit 2 的订阅状态同步机制", "StoreKit 2 怎么发起一个订阅购买？",
  "a 问同步机制（实现层），b 问使用层；语料 StoreKit 资料仅 Apple Silicon 场次附带提及",
  "a 预期 no_evidence；b 预期同样不足，但缺失证据层为 API 使用文档，两者都不应拼凑"),
 ("no_evidence_near_miss", "Metal 着色器里怎么手写", "Metal 和 Core Graphics 有什么区别？",
  "a 问 Metal 着色器编写（零覆盖），b 问框架定位差异（CG 侧可部分支撑）",
  "a 预期 no_evidence；b 预期可从图形相关笔记获得 CG 侧说明，Metal 侧需声明缺资料"),
 ("no_evidence_near_miss", "Xcode Cloud 的构建并发数怎么计费", "Xcode Cloud 是什么？",
  "a 问定价政策，b 问产品概念；两者证据层完全不同",
  "a 预期 no_evidence（缺定价/政策资料）；b 可能命中零散提及，需人工确认"),
 ("no_evidence_near_miss", "iOS 26 新增的 App API", "iOS 26 稳定吗？适合现在升级吗？",
  "同为 iOS 26 主题：a 要 API 清单，b 要稳定性判断；语料两者都零覆盖",
  "a/b 都预期 no_evidence；用于确认新系统主题整体缺资料，而非只有特定问法缺"),
 ("no_evidence_near_miss", "Kotlin 协程的调度器在 JVM 层", "Kotlin 协程和 GCD 的用法像吗？",
  "a 问 JVM 层实现（零覆盖），b 问用法对比（GCD 侧可答）",
  "a 预期 no_evidence；b 预期 GCD 侧可答、Kotlin 侧声明缺失"),
 ("no_evidence_near_miss", "Vision 框架的人体姿态估计", "Vision 框架是做什么用的？",
  "a 问具体模型精度优化（零覆盖），b 问框架用途（程度较轻）",
  "a 预期 no_evidence；b 预期也只能零散回答，两者都不应虚构功能细节"),
 ("no_evidence_near_miss", "微信小程序", "微信小程序的页面栈和 UINavigationController 像吗？",
  "a 问小程序页面栈（跨端 no_evidence），b 换成与 iOS 导航器类比",
  "a/b 都只有 iOS 侧可答，小程序侧均应声明缺失，不应拼凑"),
 ("no_evidence_near_miss", "React Native 新架构 Fabric", "React Native 的列表性能为什么差？",
  "a=RN Fabric 挂载流程（零覆盖），b=RN 列表性能（零覆盖）",
  "a/b 都预期 no_evidence；确认 RN 主题整体缺资料而非问法问题"),
 ("scope_shift", "setObject", "NSUserDefaults 能存自定义对象吗？",
  "a 问落盘时机，b 问类型边界；同一文件但小节不同",
  "a 引用落盘时机段（macOS 局限）；b 需引用 plist 类型白名单段，引用区间预期不同"),
 ("scope_shift", "原子替换", "iOS 上 NSUserDefaults 写大文件会有性能问题吗？",
  "a 问原子替换保证，b 问 iOS 大文件性能代价；来源未测代价",
  "a 可回答并声明平台；b 预期语料无 iOS 性能数据，应声明无一手数据"),
 ("scope_shift", "重定向回调", "iOS 上 301 重定向会保留 POST body 吗？",
  "a 问重定向机制（实测表），b 聚焦 iOS 具体行为",
  "a 可回答并声明实验平台；b 预期只有公开规范可引用，iOS 特定行为需声明证据局限"),
 ("scope_shift", "归档产物也是一个 plist", "NSKeyedArchiver 归档出来的文件能直接当 plist 读吗？",
  "a 问格式关系，b 问实操可行性；来源讲的是结构关系",
  "a/b 预期同一小节；b 判分关注是否区分『同为 plist 格式』与『语义可随意解析』"),
 ("scope_shift", "索引的代价", "给 SQLite 的每一列都建索引可行吗？",
  "a 问代价维度，b 问极端做法；来源代价段直接回答",
  "a/b 预期同一小节；b 判分关注是否用代价维度回答可行性而非笼统否定"),
 ("scope_shift", "SQLITE_BUSY", "遇到 database is locked 应该马上重试吗？",
  "a 问 SQLITE_BUSY 成因与处理，b 问处置策略；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否给出条件化处置而非一刀切"),
 ("scope_shift", "三次握手", "为什么挥手要比握手多一次？",
  "a=三次握手步骤与必要性，b=握手挥手对比；四次挥手小节独立支撑",
  "a/b 预期分别命中两个小节；判分关注两侧机制是否都完整"),
 ("scope_shift", "整体架构是怎么工作的", "HLS 的延迟为什么比 RTMP 高？",
  "a=HLS 架构与延迟成因，b 引入 RTMP 对比（需跨小节取材）",
  "a 预期 HLS 小节；b 预期 HLS+五种协议小节合并，判分关注引用多样性"),
 ("scope_shift", "URLSessionTask", "后台下载任务和普通 dataTask 的回调有什么不同？",
  "a=Task 子类职责（种子题），b 需要 DownloadDelegate 细节（该小节正文过薄已被拒收）",
  "a 预期 direct；b 预期 partial/声明（对应小节证据薄），验证种子拒收决定的实际影响"),
 ("scope_shift", "重复符号", "引入两个三方库后报 duplicate symbol，一般是什么原因？",
  "a=重复符号+weak+可见性机制，b=具体报错归因；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否落到链接期成因而非泛泛而谈"),
 ("scope_shift", "弱链接", "为什么 iOS 不允许下载后再加载动态库？",
  "a=弱链接机制，b 涉及审核政策边界；来源讲机制不讲政策",
  "a 预期 direct；b 预期 partial（政策层面需声明非本资料范围）"),
 ("scope_shift", "plist 能装哪些类型的对象", "把自定义对象直接写进 plist 会发生什么？",
  "a=plist 类型白名单，b=违规写入的实际后果；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否说明崩溃/失败机制"),
 ("internal_vs_public", "Existential Container 的结构", "协议类型变量为什么比具体类型变量更占内存？",
  "a=Existential Container 结构题，b=内存代价问法；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否用容器布局解释代价"),
 ("citation_boundary", "isa_t」和「ISA_BITFIELD", "isa_t 的内部结构是怎样的？",
  "a 是双对象对比题（引用需覆盖两处），b 是单对象结构题（引用一处即可）",
  "a 判分要求两侧对象都有证据；b 只要求命中 isa_t 定义段"),
 ("citation_boundary", "两条等价 SQL 的耗时差 900 倍", "SQLite 的 synchronous 参数设成 OFF 会怎样？",
  "a 问 900 倍归因（机制+实验双层），b 问单一参数行为",
  "a 判分要求机制+数字分离陈述；b 只要求参数行为，引用范围不同"),
 ("citation_boundary", "防线在 unarchiver", "用 NSSecureCoding 解码嵌套容器时要注意什么？",
  "a=防线位置题，b=嵌套容器细则（白名单小节支撑）",
  "a/b 引用区间不同（防线段 vs 白名单段）；判分关注是否引用了正确小节"),
 ("scope_shift", "dyld4 和 dyld3 是什么关系", "社区流传的 dyld3 闭包缓存方案后来怎么样了？",
  "a=dyld4 与 dyld3 关系题，b=闭包方案去向；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否澄清 dyld3 方案的存废"),
 ("scope_shift", "沙盒的哪些目录", "把用户生成的文档存到 tmp 目录会有什么风险？",
  "a=沙盒目录选择题，b=违规存放风险；NSFileManager 小节目录段支撑",
  "a/b 预期同一小节；b 判分关注是否说明系统可能清理 tmp"),
 ("scope_shift", "存储类型", "SQLite 的 TEXT 列存数字会怎样？",
  "a=存储类型清单题，b=类型亲和性行为；数据类型小节部分支撑",
  "a 预期 direct；b 预期 partial（亲和性细节若未展开需声明）"),
 ("citation_boundary", "缓存策略有几个枚举值", "哪些缓存策略会让请求完全不走缓存？",
  "a=枚举实测题，b=具体策略问法；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否点名具体枚举值"),
 ("scope_shift", "七次握手", "面试官说『七次握手』时指的是什么？",
  "a=七次握手澄清题，b=口语场景问法；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否澄清误称"),
 ("scope_shift", "超时为什么有两个", "timeoutIntervalForResource 设得很大会有什么副作用？",
  "a=两个超时分工题，b=副作用问法；同一小节支撑",
  "a/b 预期同一小节；b 判分关注是否说明资源超时的实际语义"),
]

rows = []
for ptype, key, other_q, why, exp in PAIRS:
    mid, g = find(key)
    if ptype == "follow_up_context":
        a_q, b_q = other_q, g["question"]
    else:
        a_q, b_q = g["question"], other_q
    rows.append({
        "id": "adv-%06d" % (len(rows) + 1),
        "base_manifest_id": mid,
        "pair_type": ptype,
        "question_a": a_q,
        "question_b": b_q,
        "why_different": why,
        "expected_difference": exp,
        "evidence_refs": [mid, g["expected_source_path"] or "（无来源条目）"],
        "risk_notes": ["对照的另一侧为最小自然改写，其预期是判分设计意图，需在生产链路上验证"],
    })
with (BASE / "adversarial-pairs.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("pairs:", len(rows))
from collections import Counter
print(dict(Counter(r["pair_type"] for r in rows)))
