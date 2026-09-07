# FINAL_REPORT —— semantic-review-and-golden-set-20260906

给 Codex / 人工复核者的结论。执行日期：2026-09-06。

## 0. 校验记录

```
命令：python3 tools/validate_output.py
结果：semantic-review: 1866 | gold: 190 | gaps: 46 | quality-followup: 30
      ALL CHECKS PASSED（0 错误）
```

校验覆盖：JSON 逐行合法性、UTF-8、唯一 ID、跨文件引用（review↔eval、gold↔review/eval、
gap→eval/alias/quality/gold/review 前缀引用、qfollow→eval）、枚举值、来源路径存在性、
行号范围（≤ 文件真实行数）、黄金集只引用 keep/rewrite 审查结论、rewrite 题面与审查记录一致性、
黄金集规模 160-220、非知识条目无来源字段。

## 1. 已证实（程序化校验 + 真实文件读取）

1. **1,866 条评测候选全部完成语义审查**（强制下限 1,381 条模板题 100% 覆盖）。
   每条审查都实际读取了锚定行号区间的原文。决策：keep 975 / rewrite 480 / reject 411。
2. **411 条 reject 的具体依据**（见 semantic-review-summary.md 聚类）：锚定小节正文过薄、
   锚点词与片段重叠不足、对比对象缺席、文档局部语境依赖且无法自然改写。
3. **黄金集 190 条全部可回溯**：每条带 `semantic_review_id`，校验器强制
   "keep=原题 / rewrite=审查改写题"，reject 一律未进入；knowledge 条目路径与行号全部真实存在。
4. **5 个 no_evidence 假设被证伪**（附真实路径，可直接打开复验）：
   SwiftUI、Combine、Swift Concurrency/actor、SwiftData、TestFlight 在 apple-docs-core 的
   WWDC 语料中存在场次文件（zh 105 篇 / en 178 篇），例如：
   - `wwdc/en/wwdc2019/722-introducing-combine.md`
   - `wwdc/zh/wwdc2021/10133-protect-mutable-state-with-swift-actors.md`
   上一批对应 7 条 no_evidence 候选已在审查层拒绝，未进入黄金集。
5. **meta/ 工作文档进入 FTS 索引**：apple-docs-bulk 的 include 覆盖 `meta/**/*.md`，
   `PROJECT_STATUS.md`、`DEEPSEEK_RUNBOOK.md` 等仓库维护文档会被索引（8 条登记，附真实路径）。
6. Swift 互操作/构建启动主题的资料（5 篇 tips）内容充分——该主题评测题稀缺是**出题问题**，不是资料缺失。

## 2. 候选（待人工复核，不是事实）

- 975 条 keep 中按规则判为"强支撑"的条目：规则能查结构性问题，不能完全理解内容语义；
  建议按批次抽 10% 人工抽查。
- 480 条 rewrite 的改写题：改写主语经覆盖率与自然度复核，但"该节能否完整回答改写题"
  未经人工终审（黄金集中 12 条 rewrite 版已单独标注）。
- 46 条查询缺口（P0 2 / P1 17 / P2 27）：每条带 `why_not_conclusive`，均只提出只读实验。
- 30 条补充巡检发现：全部基于实际打开的文件，但抽样范围有限（apple-archive 10 个文件、
  bulk/zh 2 个、meta 8 个），不代表整个来源。

## 3. 待生产链路验证（本批不能下结论）

1. source-symbol 主题 100% FTS miss 的真实层级归因：CODEX 已证明裸符号查询可召回，
   最可能的缺口在"长问题 → 符号查询"的规划层；需生产 Retrieval v2（查询规划+Vectorize+RRF+reranker）复测。
2. 生产快照落后于本地索引清理：本地 32 个陈旧文件已清（freshness clean），
   生产 55,635 向量快照早于清理，实际行为未知；同步须走 HANDOFF 稳定 ID 流程，由人工执行。
3. 对比题双主题证据是否同入 top8（重排多样性）、追问路由是否正确继承上下文：只能在生产或生产自测入口验证。
4. 黄金集 20 条 no_evidence 中 WidgetKit/App Intents/StoreKit/Metal/Core ML/ARKit/Vision/visionOS/
   Xcode Cloud/Apple Intelligence 等主题仅通过"WWDC 文件名零命中"核对，未做全库穷尽检索，
   生产判定仍可能翻案。

## 4. 最值得 Codex 接手的前三项

1. **用生产 Retrieval v2 复测黄金集 190 条**：这是把"候选"变"生产回归集"的唯一途径；
   优先跑 knowledge 162 条与 P0 两条缺口中的符号规划实验（裸符号 vs 长问题对照）。
2. **人工终审 12 条 rewrite 版黄金题 + 按比例抽查 keep 条目**：决定黄金集能否定版；
   semantic-review-summary.md 第 5 节给了 30 条代表性案例作为校准样例。
3. **处理两个已证实的资料问题**：meta/ 工作文档是否应移出 include（8 条路径已列）；
   上一批 5 个被证伪主题的 no_evidence 判定逻辑需在评测框架中修正（7 条 eval id 在
   quality-followup.jsonl 的 related_eval_ids）。

## 5. 明确未做事项

- 未修改上一批任何文件、原始资料、`db/`、`config.yaml`、代码、测试、网站仓库、部署配置。
- 未运行 `index/sync/ask/cards`、Cloudflare/Wrangler、部署或任何 Git 写操作；未触碰 `mermaid-diagram.svg`。
- 未读取或记录任何凭据。
- 未生成最终问答正文；未宣称线上检索成功或失败；未依据本地 FTS miss 断言生产故障。
- 未执行任何资料排除、改名、重建索引、别名回灌或配置调整——所有建议停留在只读动作。
