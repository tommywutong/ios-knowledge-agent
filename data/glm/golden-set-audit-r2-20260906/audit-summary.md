# audit-summary —— 黄金集逐题复核与 no_evidence 重审汇总

## 1. 总览

- 旧黄金集 190 条逐题复核：**keep 150 / rewrite 9 / remove 31**。
- 7 条指定 no_evidence 候选按"具体主张"重审：**retain 6 / promote 1**。
- 修正版黄金集 r2：**160 条**（knowledge 132 / no_evidence 20 / general 8）。

## 2. 移除的 31 条（全部有逐条理由，见 gold-audit.jsonl）

| 类型 | 数量 | 代表案例 |
|---|---|---|
| Codex 指出的文档结构标题 | 4 | gold-000023/024「目录」、gold-000027/028「这篇在系列中的位置」→ remove |
| Codex 指出但可自然改写 | 2 | gold-000025（第一部分 · 快速路径）→ "objc_msgSend 的汇编快速路径是怎么通过方法缓存命中 IMP 的？"；gold-000026（第三部分 · 消息转发）→ "消息转发的流程是怎样的？每一步分别给了开发者什么机会？" |
| 时间戳/日期元数据残留 | 5 | gold-000085（2026-05-14 23:33 GCD…）、gold-000087/088（对比双方为时间戳标题）、gold-000086 → 改写为"主线程 dispatch_sync 主队列是否必死"、gold-000019（2015 → 至今） |
| 笔记标题/栏目复述 | 6 | gold-000011（Runtime 简介）、gold-000045（UITableView 标题复述→改写复用池题）、gold-000053（UIViewController 标题复述→改写生命周期题）、gold-000056（hitTest 标题复述→改写命中测试题） |
| 行文碎片/指代短语 | 7 | gold-000039「谁决定了先后顺序」、gold-000047「到底会有几个 cell 活着」、gold-000050/051「这块内存实际要多少」、gold-000057「alpha 的边界到底在哪」、gold-000054、gold-000063「注册」 |
| 编号规则语境 | 2 | gold-000078（规则一：…）、gold-000079（规则四：…）→ 均改写为自然 MRC 规则题 |
| 论断式小标题拼接 | 3 | gold-000014（objc_object：对象的骨架→改写）、gold-000070（x86_64 靠指令序列当签名）、gold-000073（进程级汇总与逐个 VM Region） |
| 无意义对比/泛题 | 4 | gold-000067/068（「要解决的问题」）、gold-000091（OOP 栏目对比）、gold-000094/098（「什么是X」和「X」对比） |
| 其余文档内部栏目标题 | 2 | gold-000097/099/101/102（「卡顿-检测」「编译优化-编译缓存」等栏目型对比） |

9 条 rewrite 全部重新打开来源片段人工核对（核对到的内容写入 reason），通过后才进入 r2。

## 3. no_evidence 重审（按具体主张，不按主题名）

| eval | 具体主张 | 判定 | 关键证据 |
|---|---|---|---|
| eval-001700 | SwiftUI 布局系统**内部实现** + UIScreenKit | retain_no_evidence（中等置信） | UIScreenKit 全库零命中（疑造词）；SwiftUI 场次为使用指南型。风险：生产可能对 SwiftUI 部分返回知识，建议人工改写或淘汰 |
| eval-001701 | actor **重入隔离**细节 | **promote_to_knowledge_candidate**（高置信） | `wwdc/en/wwdc2021/10133-…swift-actors.md` 第 281-295 行直接解释 reentrancy 成因与设计对策（561 行辅助） |
| eval-001702 | Combine Publisher **内部数据流** | retain_no_evidence | 722/721 为入门/实操场次，仅 API 层数据流，无内部实现 |
| eval-001703 | SwiftData **底层实现** | retain_no_evidence | 10075/10137/10138 均为使用层（history/underlying store/custom store），未披露实现 |
| eval-001712 | TestFlight **企业分发合规边界** | retain_no_evidence（高置信） | 语料仅有 10203 崩溃诊断场次；合规主题零覆盖 |
| eval-001754 | TestFlight **加密合规报告填写** | retain_no_evidence | apple-archive 与 apple-docs 全文 grep `export/encryption compliance` 无有效命中 |
| eval-001790 | SwiftUI **跑在 Android 上** | retain_no_evidence（高置信） | SwiftUI 场次均为 Apple 平台指南，无跨平台移植资料 |

## 4. r2 黄金集覆盖

| 维度 | 分布 |
|---|---|
| category | answerable 60 / symbol 24 / alias 18 / follow_up 16 / no_evidence 16 / comparison 12 / general 8 / cross_platform 6 |
| expected_mode | knowledge 132 / no_evidence 20 / general 8 |
| difficulty | easy 45 / medium 85 / hard 30 |
| evidence_type | note 107 / source_code 24 / wwdc 1 / 无来源 28 |
| 主题 | runtime 16、memory 17、runloop-gcd 17、uikit 16、source-symbol 22、kvc-kvo-notify 12、block 11、routing 22、foundation 6、persistence 5、build-startup 5、network 2、general 8、swift-interop 1 |

仍明显不足（如实说明，未凑数）：network 2、persistence 5、build-startup 5、swift-interop 1（本轮从 no_evidence 提升 1 条）。
这源于上一批出题结构，不是本轮复核能凭空修复的；需人工按真实资料补题。

## 5. 复核方法与局限

- 每条均打开来源片段实际读取；knowledge 题按问题词-片段重叠率（ascii 不区分大小写 + CJK 2-gram）核验；
  alias 题按概念主条目核验；cross_platform 题只核验 iOS 侧锚点（避免用 iOS 片段高估证据范围）。
- 修复了复核工具自身的两处度量伪影（大小写、CJK 长片段整段匹配），并以此为依据救回 10 条被误杀的自然题
  （如"runloop 的 mode 是干嘛的？""键值观察为什么能监听到值变化？"）。
- 局限：规则化证据核验不能完全替代人工阅读；r2 中 evidence_fit=partial 的 96 条建议人工再抽查；
  no_evidence 的 20 条在生产链路上的最终行为仍未知。
