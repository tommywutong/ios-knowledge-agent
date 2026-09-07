#!/usr/bin/env python3
"""阶段 B：9 条高风险平台边界条目的独立深查。
每条重新打开来源片段核对；确认范围/未确认范围/安全与不安全措辞/manifest 修正需求。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
R4 = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/seed-evidence-boundary-and-eval-manifest-20260906")
manifest = {r["id"]: r for r in (json.loads(l) for l in (R4 / "production-eval-manifest-candidates.jsonl").read_text(encoding="utf-8").splitlines())}

KEYS = ["900 倍", "WAL 后并发", "分界线", "调试环境变量", "重定向回调", "setObject", "原子替换", "镜像个数", "测不到的盲区"]
TARGETS = {}
for mid, g in manifest.items():
    for k in KEYS:
        if k in g["question"]:
            TARGETS[k] = (mid, g)

def has_constraint(m, kw):
    return any(kw in c for c in (m.get("answer_constraints") or []))

ROWSPEC = [
 ("900 倍", dict(
   claim="两条等价 SQL 相差约 900 倍的量化结论",
   confirmed="来源为 Apple/SQLite 文档确认的机制（不开显式事务=每条语句独立事务、含 fsync 提交流程）+ 作者个人实验测得的量化结果",
   not_confirmed="900 倍这一数字在 iOS 设备、其他机器/系统/负载下的复现性；来源未声明实验硬件与系统版本",
   kind="mixed（Apple 文档机制 + personal_experiment 数字）",
   cond="来源未明确实验机器、系统版本、样本量；WAL 实验为双连接自建设计",
   safe="『不开显式事务时每条写语句都有独立事务开销，作者实测在其实验环境差距可达约 900 倍；具体数字随环境变化』",
   unsafe="『SQLite 不开事务会慢 900 倍』（把个人实验数字说成普遍事实）",
   rule="引用必须覆盖机制段；凡复述 900 倍必须标注为个人实验结果并声明环境局限",
   need_kw="个人实验")),
 ("WAL 后并发", dict(
   claim="WAL 模式下写不再阻塞读的并发行为差异",
   confirmed="rollback journal 与 WAL 的行为差异（SQLite 文档行为）+ 作者双连接对照实验的演示",
   not_confirmed="iOS 应用内嵌 SQLite 场景下的具体表现；实验的机器/系统条件来源未完整说明",
   kind="mixed（机制为公开文档 + personal_experiment 演示）",
   cond="双连接实验为自建设计，环境条件未完整声明",
   safe="『WAL 让读写不再互斥，来源以双连接实验演示了这一差异；具体表现以实际环境为准』",
   unsafe="『开了 WAL 一定不会锁』（来源实验只覆盖特定交错场景）",
   rule="引用需覆盖 WAL 机制段；实验演示必须标注为个人实验",
   need_kw="个人实验")),
 ("分界线", dict(
   claim="dyld2/dyld3/dyld4 的版本分界线",
   confirmed="分界线可通过 apple-oss-distributions/distribution-macOS 的 tag 一手查证——这是 macOS 的版本映射",
   not_confirmed="iOS 各系统版本的精确 dyld 分界：来源只能按『同期系统』推断，未给出 iOS 侧一手出处",
   kind="mixed（Apple 开源 tag 表 = macOS 事实 + iOS 同期推断）",
   cond="tag 表按 macOS 版本组织；iOS 侧分界为推断",
   safe="『dyld 分界可查 apple-oss 的 distribution-macOS tag（macOS 版本映射）；iOS 版本按同期推断，非一手确认』",
   unsafe="『iOS x.x 起 dyld4 上线』（把 macOS tag 映射包装成精确 iOS 版本结论）",
   rule="凡陈述分界必须注明证据为 macOS tag 表，iOS 为同期推断",
   need_kw="macOS")),
 ("调试环境变量", dict(
   claim="dyld 调试环境变量的可用性现状",
   confirmed="在 macOS 上 strings /usr/lib/dyld 验证部分变量已失效",
   not_confirmed="iOS 真机上这些变量的可用性（iOS 的 dyld 与限制策略不同，来源未验证）",
   kind="macOS_observation",
   cond="观察对象为 macOS 的 /usr/lib/dyld；系统版本未声明",
   safe="『在 macOS 上检查 dyld 二进制可见部分变量已移除；iOS 真机可用性未在本资料验证』",
   unsafe="『iOS 上 DYLD_PRINT 已经不能用了』（macOS 观察外推 iOS）",
   rule="必须注明观察平台为 macOS；iOS 结论需单独验证",
   need_kw="macOS")),
 ("重定向回调", dict(
   claim="URLSession 对 301/302/307/308 的重定向跟随与 body 处理差别",
   confirmed="作者用自建服务端（/r301 /r302 /r307 /r308）实测的对照表",
   not_confirmed="实验平台/系统版本来源未声明；iOS 与实验环境的差异",
   kind="personal_experiment（机制为公开行为，表格为个人实测）",
   cond="服务端实测，平台未声明；状态码语义本身为 HTTP 公开规范",
   safe="『来源以自建服务端实测了四种状态码的重定向行为；状态码语义为公开规范，实测以作者环境为准』",
   unsafe="『iOS 上 301 一定丢弃 body』（未声明实验平台即下 iOS 结论）",
   rule="引用需覆盖实测表；表述须区分公开规范与个人实测",
   need_kw="实测")),
 ("setObject", dict(
   claim="NSUserDefaults 写入后的落盘时机",
   confirmed="macOS 上读 ~/Library/Preferences 的逐毫秒观察：写后数毫秒文件即出现",
   not_confirmed="iOS 沙盒路径（Library/Preferences）下的落盘时机；iOS 行为只能引用 Apple 注释推断",
   kind="macOS_observation（+ Apple 头文件注释佐证原子性）",
   cond="实验在 macOS；作者自己曾差点误写结论并修正",
   safe="『来源在 macOS 上观察到写后数毫秒即落盘（非同步语义，是后台快速落盘）；iOS 沙盒行为以 Apple 文档为准』",
   unsafe="『iOS 上 setObject 后 3.4ms 就落盘』（把 macOS 路径观察说成 iOS 事实）",
   rule="必须注明路径观察来自 macOS；iOS 结论引用 Apple 文档而非实验数字",
   need_kw="macOS")),
 ("原子替换", dict(
   claim="偏好文件落盘为原子替换及其保证边界",
   confirmed="Apple 头文件注释（-synchronize 语义）与 macOS 观察",
   not_confirmed="任意写入规模下的性能代价；iOS 特定行为",
   kind="mixed（Apple_source 注释 + macOS_observation）",
   cond="保证范围来自 Apple 注释；代价未测",
   safe="『原子替换保证写入期间的崩溃不损坏旧文件；大规模写入的性能代价来源未测』",
   unsafe="『原子替换没有任何性能代价』",
   rule="引用需覆盖注释段；保证范围以 Apple 注释为准",
   need_kw="Apple")),
 ("镜像个数", dict(
   claim="启动耗时与动态库镜像个数的关系及其 iOS 适用性",
   confirmed="macOS 探针实验（KERN_PROC_PID 取 p_starttime，多配置对照）测得镜像数主导启动成本",
   not_confirmed="iOS 上的对应实测数字；来源有专门小节讨论『能推广到 iOS 吗』，结论为推断",
   kind="personal_experiment（macOS 探针）",
   cond="探针程序在 macOS 运行；样本量/机器型号来源未完整说明",
   safe="『来源在 macOS 用探针实测：镜像个数是启动成本的主导项；iOS 侧是推断，需真机复测』",
   unsafe="『iOS 上每多一个动态库启动慢 X ms』（把 macOS 数字说成 iOS 事实）",
   rule="引用需覆盖探针方法与『推广到 iOS』讨论小节；iOS 数字必须标注为推断",
   need_kw="macOS")),
 ("测不到的盲区", dict(
   claim="启动测量存在打点覆盖不到的盲区（约 400 微秒）",
   confirmed="作者测量实验中发现打点无法覆盖的一段（量级约 400 微秒，实验环境内）",
   not_confirmed="iOS 上盲区的量级与成因；实验的机器/系统条件来源未完整说明",
   kind="personal_experiment",
   cond="量级数字来自个人实验环境",
   safe="『来源在其测量实验发现一段打点覆盖不到的盲区（其环境约 400 微秒）；iOS 上的量级需单独测量』",
   unsafe="『iOS 启动总有 400 微秒测不到』",
   rule="引用需覆盖测量方法段；400 微秒必须标注为个人实验环境数值",
   need_kw="个人实验")),
]

out = []
for key, spec in ROWSPEC:
    mid, m = TARGETS[key]
    constrained = has_constraint(m, spec["need_kw"])
    out.append({
        "id": "pbr-%03d" % (len(out) + 1),
        "manifest_id": mid,
        "specific_claim": spec["claim"],
        "confirmed_scope": spec["confirmed"],
        "not_confirmed_scope": spec["not_confirmed"],
        "evidence_kind": spec["kind"],
        "platform_version_conditions": spec["cond"],
        "safe_answer_wording": spec["safe"],
        "unsafe_answer_wording": spec["unsafe"],
        "required_citation_rule": spec["rule"],
        "correction_needed_in_manifest": (not constrained),
        "correction_reason": ("" if constrained else
            f"manifest 的 answer_constraints 未包含『{spec['need_kw']}』类局限说明（现约束：{m.get('answer_constraints') or '无'}）；判分时应按本记录的 required_citation_rule 补充，不修改原 manifest"),
    })
with (BASE / "platform-boundary-review.jsonl").open("w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("platform-boundary-review:", len(out))
print("ids:", [(r["manifest_id"], r["correction_needed_in_manifest"]) for r in out])
