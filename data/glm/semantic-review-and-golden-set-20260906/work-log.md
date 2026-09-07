# work-log —— semantic-review-and-golden-set-20260906

## 阶段 0：输入与边界确认

- 复读 AGENTS/HANDOFF/PROGRESS/SPEC + 上一批 `CODEX_REVIEW.md`、`schema.md`。
- 关键背景采纳：31 条 observed path 属已清理的陈旧索引（Codex 已 `sync --source summer2026 --no-embed` 并验证 clean）；
  source-symbol 20/20 miss 不能证明符号检索故障（生产有查询规划+向量+RRF+rerank）。
- 输入确认：1,866 条评测候选，模板标记 1,381 条（trouble 310 / compare 283 / lookup 259 / mech 220 / boundary 168 / summary 141），非模板 485 条。

## 阶段 A：语义审查（1,866 条全覆盖）

- 方法：确定性规则管道（tools/review_pipeline.py）。每条都打开 `expected_source_path` 并读取锚定行号区间的原文，
  统计：正文行数/字符量、链接行占比、锚点词覆盖率、对比对象覆盖率、误区关键词、文档局部结构词（Part/编号/素材/归档/`draft: false`）、改写主语自然度。
- 规则要点：
  - 片段正文 <2 行或 <60 字符 → reject（标题相似不等于内容可答）；
  - compare 题对比对象未在该小节出现 → 降级为单概念机制题（改写主语再核覆盖率）；
  - 文档局部语境依赖（Part N/一、二、/④/日期/`draft: false`）→ 剥离改写，主语不合格（叙述性小标题、>18 字）则 reject；
  - boundary 元问句（"资料里有没有对应说明"）→ 改写为独立问法；
  - alias 类概念提取 bug（首轮 148 条全拒）已修复：从 eval rationale 提取「概念」主条目 + 问题词覆盖率兜底；
  - rewrite 必须带改写题，否则降级 reject（修掉 23 条漏网）。
- 过程修正 4 轮，最终决策分布：**keep 975 / rewrite 480 / reject 411**；
  其中模板题 1,381 = keep 556 / rewrite 452 / reject 373；非模板 485 = keep 419 / rewrite 28 / reject 38。
- 局限：规则审查能可靠发现结构性问题，不能替代对内容的完整理解；全部 keep 在投产前仍应人工抽查。

## 阶段 B：黄金集

- 池：keep 975 + 改写后再次核对通过的 rewrite；拒绝项 0 进入。
- 评分：置信度+语义契合+独立性+难度，配额 answerable 78 / comparison 24 / symbol 28 / alias 18 / follow_up 16 / no_evidence 16 / general 8 / cross_platform 8，主题上限 22。
- 产出 **190 条**（knowledge 162 / no_evidence 20 / general 8；rewrite 版 12 条）。
- 与阶段 D 联动：被 WWDC 语料证伪的 no_evidence 候选（SwiftUI/Combine/Swift Concurrency/SwiftData/TestFlight 共 7 条）在审查层即被拒绝，未进入黄金集。

## 阶段 C：查询与别名缺口（46 条）

- 信号来源：FTS 抽样分主题 miss 率、术语库 94 条无证据条目（抽样 25 条）、术语映射质量发现、阶段 A 拒绝聚类、CODEX_REVIEW。
- P0 两条：① source-symbol 的"问题→符号查询"规划层缺口（CODEX 已实测裸符号查询可召回）；② 生产快照落后于本地清理后的索引。
- 每条都有 why_not_conclusive，明确"本地 FTS-only 不能归因单层、不能外推生产"。

## 阶段 D：补充巡检（30 条）

- **重要发现（5 条证伪）**：SwiftUI、Combine、Swift Concurrency/actor、SwiftData、TestFlight 五个主题在
  apple-docs-core 的 WWDC 语料中实际存在场次文件（zh 105 篇 / en 178 篇，如 `wwdc/en/wwdc2019/722-introducing-combine.md`、
  `wwdc/zh/wwdc2021/10133-protect-mutable-state-with-swift-actors.md`），上一批 no_evidence 候选对这些主题的
  "语料缺失"假设不成立 → 对应候选已在阶段 A 被拒绝。
- apple-archive：MemoryMgmt、qa 等 10 个抽样，1 条确认正常、无超长行问题（抽样范围内）。
- apple-docs-bulk：meta/ 目录的仓库工作文档（PROJECT_STATUS.md、DEEPSEEK_RUNBOOK.md 等 8 条）位于 include 范围内会进 FTS 索引 → manual_source_review。
- apple-docs/zh 单文件书目 2 条抽样正常。
- Swift 互操作/构建启动 5 篇 tips 资料核实内容充分——该主题评测题少是"出题问题"而非"资料缺失"。

## 阶段 E：校验与收尾

- `tools/validate_output.py` 全绿：4 个 JSONL 共 2,132 行，唯一 ID、跨文件引用、枚举、路径/行号、黄金集只引用 keep/rewrite 全部通过。
- 只读 git 检查：工作区仅新增本目录；上一批文件与 `mermaid-diagram.svg` 未触碰。

## 未解决的不确定性

1. 规则审查对"题面-内容"语义适配的判定是保守近似，keep 条目仍需人工按比例抽查。
2. 12 条 rewrite 版黄金题是否被锚定小节完整回答，未经人工终审。
3. 黄金集 no_evidence 条目（WidgetKit/App Intents/StoreKit/Metal 等）仅通过"WWDC 文件名零命中"核对，未做全库穷尽检索。
4. 黄金集缺口（network 2 / cross_platform 6 / build-startup 5 / swift-interop 0）为真实审查结果，未凑数。
