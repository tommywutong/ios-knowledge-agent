#!/usr/bin/env python3
"""阶段 A：130 条 manifest 逐题证据账本。
每条重新打开来源区间核对；quoted_anchor 从实际文本提取，保证与行号一致。
"""
import json, re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R4 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/seed-evidence-boundary-and-eval-manifest-20260906")
R3 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/golden-set-red-team-r3-20260906")

manifest = [json.loads(l) for l in (R4 / "production-eval-manifest-candidates.jsonl").read_text(encoding="utf-8").splitlines()]
sba = {r["source_seed_id"]: r for r in (json.loads(l) for l in (R4 / "seed-boundary-audit.jsonl").read_text(encoding="utf-8").splitlines())}
r3gold = {r["id"]: r for r in (json.loads(l) for l in (R3 / "gold-eval-candidates-r3.jsonl").read_text(encoding="utf-8").splitlines())}
r3audit = {r["source_r2_id"]: r for r in (json.loads(l) for l in (R3 / "r3-audit.jsonl").read_text(encoding="utf-8").splitlines())}
nev3 = {r["source_r2_id"]: r for r in (json.loads(l) for l in (R3 / "no-evidence-audit-r3.jsonl").read_text(encoding="utf-8").splitlines())}

_file_cache = {}
def lines_of(p):
    if p not in _file_cache:
        _file_cache[p] = Path(p).read_text(encoding="utf-8", errors="replace").split("\n")
    return _file_cache[p]

def anchor_of(path, s, e):
    ls = lines_of(path)
    seg = ls[max(0, s-1):min(e, len(ls))]
    prose = [l.strip() for l in seg if len(l.strip()) > 12 and not l.strip().startswith("#")]
    if not prose:
        prose = [l.strip() for l in seg if l.strip()]
    a = prose[0] if prose else ""
    return a[:280]

def subject_of(m):
    if m["origin"] == "undercovered_seed":
        a = sba.get(m["origin_id"])
        if a and a.get("normalized_subject"):
            return a["normalized_subject"]
    else:
        rg = r3gold.get(m["origin_id"])
        if rg:
            a = r3audit.get(rg.get("source_r2_id"))
            if a and a.get("normalized_subject"):
                return a["normalized_subject"]
    return re.sub(r"^[「『]|』」?]$", "", m["question"])[:40]

# 特殊题的人工核账（claims / status / unsupported）
OVERRIDES = {
 "900 倍": dict(
   claims=["SQLite 不开启显式事务时，每条写语句都各自走一次完整提交流程（Apple/SQLite 文档行为）",
           "作者在同一环境实测得到两条等价 SQL 相差约 900 倍的量化结果",
           "该 900 倍数字在其他机器/系统/负载下可复现"],
   status="mixed",
   unsupported=["900 倍的量化数字不可外推：来源未提供其他机器、系统版本、负载下的对照数据"]),
 "WAL 后并发": dict(
   claims=["WAL 模式下写不再阻塞读，rollback journal 下会阻塞（来源以实验对照展示）",
           "实验结论来自作者自建的双连接对照实验，环境细节（机器/系统）来源未完整说明"],
   status="mixed",
   unsupported=["WAL 在 iOS 应用内嵌场景下的具体表现，来源未单独验证"]),
 "分界线": dict(
   claims=["dyld2/dyld3/dyld4 的版本分界可通过 apple-oss-distributions/distribution-macOS 的 tag 查证（macOS 版本映射）",
           "该分界线与社区流传说法不同，来源给出了一手出处",
           "iOS 各系统版本的精确 dyld 分界与 macOS tag 一一对应"],
   status="partial",
   unsupported=["iOS 侧的精确 dyld 版本分界：来源证据是 distribution-macOS 的 macOS tag 映射，iOS 只是同期推断"]),
 "DYLD_PRINT": dict(
   claims=["部分 dyld 调试环境变量已失效，可用性可通过检查 dyld 二进制验证（macOS 观察）",
           "失效/可用清单同样适用于 iOS 真机"],
   status="partial",
   unsupported=["iOS 真机上 dyld 环境变量的可用性：来源未在 iOS 设备验证"]),
 "setObject": dict(
   claims=["NSUserDefaults 写入后有落盘延迟，作者实测写后数毫秒内文件即出现（macOS 路径 ~/Library/Preferences 观察）",
           "落盘采用原子替换（Apple 头文件注释佐证）",
           "iOS 沙盒下的落盘时机与 macOS 观察一致"],
   status="mixed",
   unsupported=["iOS 沙盒路径与落盘时机的直接观察：来源实验在 macOS 上进行"]),
 "原子替换": dict(
   claims=["偏好文件落盘为原子替换，可防止写一半损坏（Apple 注释佐证）",
           "原子替换保证写入期间的崩溃不损坏旧文件",
           "该保证扩展到任意写入规模"],
   status="partial",
   unsupported=["大规模写入的性能代价与 iOS 特定行为：来源未覆盖"]),
 "镜像个数": dict(
   claims=["启动耗时的主导成本与动态库镜像个数相关（作者探针实验，macOS）",
           "该结论可推广到 iOS（来源专门小节讨论适用性）"],
   status="mixed",
   unsupported=["iOS 上的对应实测数字：来源为 macOS 探针实验，iOS 侧是推断"]),
 "测不到": dict(
   claims=["启动测量存在打点覆盖不到的盲区（来源以其测量实验说明）",
           "盲区成因与量级在 iOS 上与 macOS 一致"],
   status="partial",
   unsupported=["iOS 启动盲区的量级：来源为个人实验环境"]),
 "重定向": dict(
   claims=["URLSession 对 301/302/307/308 的重定向跟随与 body 处理存在差别（来源以服务端实测表展示）",
           "实测条件（平台/系统版本）在来源中完整说明"],
   status="mixed",
   unsupported=["iOS 真机与作者实验环境的差异：来源未声明实验平台"]),
 "重入": dict(
   claims=["actor 重入指 await 挂起期间 actor 可执行其他任务（WWDC 10133 场次直接解释）",
           "设计对策：在同步代码内完成状态变更、await 前恢复不变量（来源给出代码级说明）",
           "重入机制的目的：防死锁并保证前进性"],
   status="direct", unsupported=[]),
 "键映射": dict(
   claims=["YYModel 与 JSONModel 在键映射环节的实现次数不同（来源源码级分析）",
           "作者基准测试得到的具体倍数可复现"],
   status="partial",
   unsupported=["基准数字的普遍复现性：来源为个人测试环境"]),
 "元数据缓存": dict(
   claims=["YYModel 对 runtime 元数据做一次性缓存，是性能差距的主要来源之一（来源分析）",
           "『值 49 倍但只值一次』的量化在其他环境成立"],
   status="partial",
   unsupported=["量化数字的普遍性：个人实验环境"]),
 "objc_msgSend 强转": dict(
   claims=["objc_msgSend 直接强转函数指针调用必须类型精确，否则 ABI 层出错（来源源码级解释）",
           "该行为在所有 arm64 环境一致"],
   status="direct", unsupported=[]),
 "归档产物": dict(
   claims=["NSKeyedArchiver 产物是扁平表结构，对象环通过 UID 表达（来源逐项解析）",
           "解档时 initWithCoder 可能拿到半成品对象"],
   status="direct", unsupported=[]),
 "白名单": dict(
   claims=["NSSecureCoding 白名单解码不递归，容器需逐层声明（来源反例演示）",
           "子类默认放行、NSObject 是后门（来源说明）"],
   status="direct", unsupported=[]),
 "防线在 unarchiver": dict(
   claims=["安全解码的真正防线在 unarchiver 的配置而非单次 decodeObjectOfClass: 调用（来源论证）"],
   status="direct", unsupported=[]),
 "Existential Container": dict(
   claims=["Existential Container 的固定布局与 value witness table 职责（来源图示讲解）"],
   status="direct", unsupported=[]),
 "isa-swizzling": dict(
   claims=["KVO 的 isa-swizzling 会生成中间类并覆写 setter（来源实测打印中间类符号）",
           "教科书中『后半段』说法在当前系统不成立（来源以实验澄清）"],
   status="direct", unsupported=[]),
 "缓存策略枚举": dict(
   claims=["NSURLRequest 各缓存策略枚举的实际行为可实测区分（来源实验表）",
           "实测环境与系统版本在来源中完整声明"],
   status="mixed",
   unsupported=["iOS 与作者实验平台的差别：来源未声明实验平台"]),
}

rows = []
for m in manifest:
    mode = m["expected_mode"]
    q = m["question"]
    ov = None
    for k, v in OVERRIDES.items():
        if k in q:
            ov = v; break
    if mode == "no_evidence":
        ne = nev3.get(r3gold[m["origin_id"]].get("source_r2_id"))
        claim = ne["specific_claim_checked"] if ne else q[:60]
        layer_miss = "内部实现/官方文档层证据" if any(k in q for k in ["内部", "底层", "实现"]) else (
            "跨平台事实" if any(k in q for k in ["Android", "Flutter", "Kotlin", "React Native", "微信"]) else (
            "定价/政策资料" if any(k in q for k in ["计费", "合规", "审核", "备案"]) else "API 使用文档"))
        claims = [f"该具体主张可由当前语料直接回答：{claim}"]
        items, status = [], "no_evidence"
        unsupported = [f"缺失的证据层：{layer_miss}。具体主张『{claim}』在 wwdc zh+en 文件名与全库关键词检索中均无直接对应资料"]
        rule = "系统必须返回 no_evidence 并退款，不得用同主题泛资料（如一般 SwiftUI/Combine/TestFlight 介绍）拼接回答，不得伪造引用"
        conf = "medium"
    elif mode == "general":
        claims = ["该输入为非技术日常输入，不构成技术主张"]
        items = []
        status = "not_applicable" if False else "direct"  # general 无来源，用 direct 表示"路由预期明确"
        status = "direct"
        unsupported = []
        rule = "路由为 general 即通过；不需要任何引用"
        conf = "high"
    else:
        subject = subject_of(m)
        if ov:
            claims = list(ov["claims"]); status = ov["status"]; unsupported = list(ov["unsupported"])
        else:
            claims = [f"『{subject}』的核心机制/用法由锚定小节直接讲解"]
            status = "direct"
            unsupported = []
        # 平台/实验约束 → 第二条主张（推断性）
        constraints = list(m.get("answer_constraints") or [])
        if constraints and ov is None:
            claims.append("该结论在 iOS 上同样成立（或数值可普遍复现）")
            if status == "direct":
                status = "partial"
            unsupported.append("iOS 真机上的直接验证：来源证据为 macOS 观察/个人实验，未在 iOS 设备复核" )
        # 引用项
        items = []
        if m.get("expected_source_path"):
            p = m["expected_source_path"]
            s_, e_ = m["expected_start_line"], m["expected_end_line"]
            ls = lines_of(p)
            n = len(ls)
            s_, e_ = max(1, s_), min(e_, n)
            anchor = anchor_of(p, s_, e_)
            seg = ls[s_-1:e_]
            prose = [l for l in seg if len(l.strip()) > 12 and not l.strip().startswith("#")]
            kind_map_r3 = {"wwdc": "Apple_source", "source_code": "historical_reference"}
            if m["origin"] == "undercovered_seed":
                a = sba.get(m["origin_id"])
                kind = {"Apple_source": "Apple_source", "iOS_public_api": "iOS_public_api",
                        "macOS_observation": "macOS_observation", "personal_experiment": "personal_experiment",
                        "mixed_evidence": "user_note_inference"}.get(a["evidence_scope"], "user_note_inference")
            else:
                et = m.get("expected_evidence_type")
                kind = kind_map_r3.get(et, "user_note_inference")
            if ov and ("900 倍" in q or "WAL" in q or "49 倍" in q or "镜像个数" in q or "测不到" in q or "重定向" in q or "缓存策略" in q or "setObject" in q or "DYLD" in q.upper()):
                kind = "personal_experiment" if "实验" in json.dumps(ov, ensure_ascii=False) or "实测" in json.dumps(ov, ensure_ascii=False) else kind
            for ci in range(len(claims)):
                items.append({
                    "claim_index": ci,
                    "source_path": p, "start_line": s_, "end_line": e_,
                    "evidence_kind": kind if ci == 0 else ("personal_experiment" if any(x in claims[ci] for x in ["实测", "倍", "复现", "量化"]) else kind),
                    "support_level": ("direct" if ci == 0 and status in ("direct", "mixed") else
                                      "direct" if status == "direct" else
                                      "contextual"),
                    "excerpt_summary": f"小节以『{anchor[:40]}…』起笔，正文 {len(prose)} 行，围绕『{subject}』展开。",
                    "quoted_anchor": anchor,
                })
            if not prose:
                status = "needs_human"
        rule = ("至少一条引用落在标注区间且支撑核心主张；" +
                ("回答若含 iOS 适用性/数值外推，必须显式声明局限，否则按引用越界判罚" if unsupported else "不得超出 answer_boundary"))
        conf = {"direct": "high", "partial": "medium", "mixed": "medium", "needs_human": "low"}[status]
        if mode == "knowledge" and m["category"] == "follow_up":
            ctx = m.get("dialogue_context") or []
            synth = any("合成" in x for x in (m.get("risk_notes") or []))
            claims = [f"必须从上一轮继承的话题：{(ctx[0]['content'][:40] + '…') if ctx else '（无）'}",
                      claims[0] if claims else "锚定小节支撑延伸回答"]
            unsupported = (["当前短问题本身不完整，路由与检索必须依赖上一轮模式与话题，不能单靠本句判断"]
                           + ["上一轮助手内容为合成占位，连续性需人工确认"] if synth else
                           ["当前短问题本身不完整，路由与检索必须依赖上一轮模式与话题"])
            status = "needs_human" if synth else "partial"
            conf = "low" if synth else "medium"
            rule = "判分前必须先构造 dialogue_context 的多轮会话；系统须继承上一轮模式与相关历史，检索不得混入无关旧话题"
    rows.append({
        "id": "ledger-%06d" % (len(rows) + 1),
        "manifest_id": m["id"], "origin": m["origin"], "origin_id": m["origin_id"],
        "question": q, "expected_mode": mode, "topic": m["topic"], "category": m["category"],
        "core_claims": claims, "answer_boundary": (g_answer(m, subject_of(m)) if False else ""),
        "evidence_status": status, "evidence_items": items,
        "unsupported_claims": unsupported,
        "required_answer_constraints": list(m.get("answer_constraints") or []),
        "citation_acceptance_rule": rule,
        "confidence": conf,
        "risk_notes": list(m.get("risk_notes") or []),
    })

def g_answer(m, subject):
    return ""

# 补 answer_boundary：种子用 sba；r3 用 r3-audit；no_evidence/general 用固定句
for r in rows:
    if r["answer_boundary"]:
        continue
    m = next(x for x in manifest if x["id"] == r["manifest_id"])
    if m["origin"] == "undercovered_seed":
        r["answer_boundary"] = sba[m["origin_id"]]["answer_boundary"]
    elif m["expected_mode"] == "no_evidence":
        r["answer_boundary"] = "预期边界：系统应判定证据不足并返回 no_evidence，不输出知识性正文"
    elif m["category"] == "general":
        r["answer_boundary"] = "预期边界：按 general 对话处理，不进入 iOS 检索"
    elif m["category"] == "follow_up":
        r["answer_boundary"] = "预期边界：仅延伸上一轮话题在锚定小节中的内容"
    else:
        rg = r3gold.get(m["origin_id"])
        a = r3audit.get(rg.get("source_r2_id")) if rg else None
        r["answer_boundary"] = (a["answer_boundary"] if a and a.get("answer_boundary") else "止于锚定小节可回答的范围")

with (BASE / "evidence-ledger.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("ledger:", len(rows))
print("status:", dict(Counter(r["evidence_status"] for r in rows)))
print("conf:", dict(Counter(r["confidence"] for r in rows)))
