# semantic-review-and-golden-set-20260906 —— README

## 任务范围

把上一批 `data/glm/overnight-rag-evaluation-20260906/` 的 1,866 条评测候选（其中 1,381 条带
"模板生成：题面与该小节内容适配需人工复核"标记）转化为三类可复核产物：

1. **语义审查队列**（`semantic-review.jsonl`）：逐条打开来源、读取锚定行号区间的真实文本后给出
   keep / rewrite / reject 判定，覆盖全部 1,866 条（1,381 条模板题为强制下限，另含 485 条非模板题
   以便黄金集能覆盖追问/路由/无证据类型）。
2. **黄金评测候选集**（`gold-eval-candidates.jsonl`）：190 条小而硬的候选，只来自 keep 或
   "改写后再次核对通过"的审查结论。
3. **查询与别名缺口报告**（`query-gap-report.jsonl`，46 条）与**资料质量补充巡检**
   （`quality-followup.jsonl`，30 条）。

## 输入

- 上一批全部 JSONL（eval-candidates / terminology-aliases / retrieval-samples / failure-triage / quality-findings）
- 上一批 `CODEX_REVIEW.md`（含关键背景：31 条 observed path 属已清理的陈旧索引；FTS-only miss 不可外推生产）
- 原始资料（只读）：Obsidian 笔记、26暑期内容、objc4 源码、apple-docs-vault、apple-developer-archive-vault

## 输出文件

| 文件 | 说明 |
|---|---|
| `semantic-review.jsonl` | 1,866 条逐条审查记录（decision/semantic_fit/standalone_quality/routing_fit/reason/rewrite_question） |
| `semantic-review-summary.md` | 审查统计、拒绝原因聚类、改写模式、30+ 代表案例索引 |
| `gold-eval-candidates.jsonl` | 190 条黄金候选，每条可回溯 semantic_review_id |
| `gold-coverage.md` | 黄金集覆盖表 + 如实缺口说明 |
| `query-gap-report.jsonl` | 46 条缺口，区分 alias/查询规划/词法召回/重排/资料覆盖/routing，只提可验证实验 |
| `quality-followup.jsonl` | 30 条补充巡检发现（全部实际打开核对过） |
| `schema.md` / `work-log.md` / `FINAL_REPORT.md` | 规范、过程记录、结论 |
| `tools/` | 确定性审查/构建/校验脚本，可复跑 |

## 边界（已遵守）

- 只写入本目录；未修改上一批任何文件；未修改原始资料、`db/`、`config.yaml`、代码、测试、网站。
- 未运行 `index/sync/ask`、Cloudflare/Wrangler、部署、任何 Git 写操作。
- 未读取/记录任何凭据；未触碰 `mermaid-diagram.svg`。
- 阶段 D 使用了少量本地 FTS/文件名检索做观察，全部结论标注"不可外推生产"。

## 复核方式

1. 运行 `python3 tools/validate_output.py`：校验 JSON 合法性、唯一 ID、跨文件引用、枚举值、
   来源路径存在性、行号范围、黄金集只引用 keep/rewrite 结论。
2. 抽查 `semantic-review.jsonl`：对照 `source_eval_id` 打开 `source_path` 指定行区间，
   核对 `reviewed_excerpt_summary` 与 `reason` 是否与原文一致。
3. 黄金集：每条 `semantic_review_id` 可回溯审查依据；rewrite 条目的题面必须等于审查记录中的
   `rewrite_question`（校验器强制）。
4. `quality-followup.jsonl` 的 5 个 no_evidence 证伪条目可直接按其中真实路径打开 WWDC 场次文件复验。

## 明确未做事项

- 未生成任何最终问答正文；未宣称线上/本地检索成功或失败。
- 未依据本地 FTS miss 断言生产检索故障；所有检索层结论标记为"待生产 Retrieval v2 复测"。
- 未执行任何排除、改名、重建索引或别名回灌；所有建议停留在 `review_only` / `manual_source_review` 等只读动作。
- 未对上一批被拒绝候选做任何覆盖或删除。
