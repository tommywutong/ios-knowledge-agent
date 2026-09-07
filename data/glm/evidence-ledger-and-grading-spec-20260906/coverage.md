# coverage —— 证据账本与判分规范覆盖报告

## 1. 证据账本（130 条全覆盖）

| evidence_status | 数量 | 说明 |
|---|---|---|
| direct | 78 | 核心主张有来源直接支撑（含 22 条 source-symbol、20 条 no_evidence 之外的纯文档题等） |
| partial | 11 | 部分主张只能推断（主要是 macOS 观察 → iOS 适用性） |
| mixed | 5 | 直接证据与不可外推的量化数字并存（SQLite 900 倍、WAL、NSUserDefaults、缓存策略实测、镜像个数） |
| no_evidence | 20 | 全部给出"缺失证据层"与具体 unsupported_claims |
| needs_human | 16 | 全部为 follow_up：上一轮助手内容为合成占位，衔接需人工确认 |

按主题：build-startup 25 条中仅 13 条 direct（5 partial + 1 mixed + 2 needs_human + 4 needs_human 分布见上），
persistence 21 条中 12 条 direct；swift-interop 6 条全部 direct；network 19/20 direct。
薄弱主题的证据边界风险显著高于其他主题——与前三轮结论一致。

## 2. 平台边界深查（9 条，manifest id 与任务指定完全一致）

| manifest_id | 主题 | confirmed / not_confirmed | correction_needed |
|---|---|---|---|
| pem-000028 | SQLite 900 倍 | 机制（Apple/SQLite 文档）+ 个人实验数字 / 数字的外推性 | false（manifest 已带约束） |
| pem-000029 | WAL 并发 | 机制 + 双连接实验演示 / iOS 内嵌场景表现 | false |
| pem-000030 | dyld 三代分界 | distribution-macOS tag 映射（macOS 事实）/ **iOS 精确分界（同期推断）** | **true**（manifest 无版本证据来源约束） |
| pem-000031 | DYLD_PRINT 可用性 | macOS strings 观察 / iOS 真机可用性 | false |
| pem-000032 | URLSession 重定向 | 自建服务端实测表 / 实验平台未声明 | false |
| pem-000034 | NSUserDefaults 落盘 | macOS ~/Library/Preferences 观察 / iOS 沙盒行为 | false |
| pem-000035 | 原子替换保证边界 | Apple 注释 + macOS 观察 / 任意规模代价 | **true**（manifest 缺"保证范围以 Apple 注释为准"约束） |
| pem-000053 | 镜像个数计价 | macOS 探针实验 / iOS 实测数字（推断） | false |
| pem-000054 | 启动测量盲区 | 个人实验盲区（约 400 微秒）/ iOS 量级 | **true**（manifest 缺数字环境局限约束） |

## 3. 判分契约（98 条 = P0 31 + P1 67 全覆盖）

- refund_expected=true：20 条（全部 no_evidence）；
- manual_review_required=true：31 条（16 追问 + 15 平台/实验局限题）；
- 每条契约的 must_not_claim 直接引用 ledger 的 unsupported_claims 或平台边界深查的 unsafe_answer_wording。

## 4. 反例对照集（45 对）

| pair_type | 数量 |
|---|---|
| scope_shift | 21 |
| no_evidence_near_miss | 8 |
| follow_up_context | 4 |
| internal_vs_public | 3 |
| symbol_vs_natural_language | 3 |
| citation_boundary | 4 |
| platform_shift | 2 |

任务点名的五组对照全部落地：SwiftUI 一般资料 vs 跑 Android（以 Android Handler/iOS RunLoop 同构对替代，
SwiftUI-Android 题未入 130 清单已在字段中注明）、Combine API vs 内部实现、macOS dyld4 分界 vs iOS 精确版本、
WAL 机制 vs 900 倍数字、裸符号 vs 自然语言、独立题 vs 追问。

## 5. 未纳入与原因

- P2 的 32 条 manifest 条目未生成判分契约（任务限定 P0/P1）；
- 45 对对照中 question_b 为最小自然改写（非 manifest 条目），其生产表现需实测验证；
- needs_human 的 16 条追问在合成上下文被真实对话替换前，判分契约只能作为占位规范。
