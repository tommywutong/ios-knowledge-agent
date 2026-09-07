# schema.md —— 本批次 JSONL 字段规范

UTF-8、一行一个合法 JSON 对象。除注明可 null 的字段外不允许 null。行号 1-indexed 含首尾。

## 1. semantic-review.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `review-%06d`，本批次唯一 |
| source_eval_id | string | 必须存在于上一批 eval-candidates |
| decision | string | `keep`/`rewrite`/`reject`；rewrite 必须有 rewrite_question，keep/reject 必须为 null |
| semantic_fit | string | `strong`/`partial`/`weak`/`none`：来源片段能否支撑题面 |
| standalone_quality | string | `strong`/`partial`/`weak`：是否为独立自然问题 |
| routing_fit | string | `correct`/`questionable`/`wrong`：expected_mode 与类别是否自洽 |
| source_path | string\|null | 原 eval 的来源；no_evidence/general 为 null |
| source_start_line / source_end_line | int\|null | 同上；knowledge 条目必须满足 1 ≤ start ≤ end ≤ 文件行数 |
| reviewed_excerpt_summary | string | ≤180 中文字符，描述实际核对到的区间内容 |
| reason | string | 判定依据（引用规则信号 + 片段观察） |
| rewrite_question | string\|null | 仅 decision=rewrite 时非 null；改写主语经自然度闸门与覆盖率复核 |
| suggested_expected_mode | string\|null | `knowledge`/`no_evidence`/`general` 或 null（维持原值时为原值） |
| risk_notes | string[] | 保留原 eval 的风险标注 + 审查新增标注 |
| confidence | string | `low`/`medium`/`high` |

判定规则（确定性、可复跑，见 tools/review_pipeline.py）：正文过薄 reject；锚点词覆盖率 <50% reject；
Part/编号/素材等文档局部语境依赖 → 剥离改写（改写失败则 reject）；boundary 元问句一律改写；
compare 对比对象缺席 → 降级单概念题；叙述性小标题（④/日期/超长）不得作为改写主语。

## 2. gold-eval-candidates.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `gold-%06d` |
| source_eval_id | string | 原 eval id |
| question | string | keep=原题；rewrite=审查改写题（校验器强制一致） |
| category / topic / difficulty / expected_mode | string | 枚举同上一批 schema |
| expected_source_path / expected_start_line / expected_end_line / expected_evidence_type | string/int\|null | knowledge 必填且校验；no_evidence/general 必须 null |
| aliases | string[] | ≤5 |
| dialogue_context | object[] | follow_up 必填；`{role, content, mode}` |
| selection_reason | string | 入选理由 |
| semantic_review_id | string | 必须指向 decision=keep/rewrite 的审查记录 |
| diagnostic_value | string | 能暴露召回/重排/路由/追问/引用/无证据中的哪类问题 |
| risk_notes | string[] | 继承审查风险 + 黄金集新增风险 |

规模约束：160-220 条；reject 一律不得进入。

## 3. query-gap-report.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `gap-%06d` |
| canonical_term_or_query | string | 术语/查询/主题 |
| category | string | 自由短语（topic_recall / terminology_alias / corpus_missing / index_freshness 等） |
| observed_signal | string | 观察到的信号 |
| likely_layer | string | `alias`/`query_planning`/`fts_lexical_recall`/`semantic_recall`/`rerank`/`source_coverage`/`routing`/`unknown` |
| evidence_refs | string[] | eval-/alias-/quality-/gold-/review- 前缀 id 会被校验器核对存在性；其余为文件名引用 |
| why_not_conclusive | string | 为什么当前证据不能下结论 |
| safe_followup_experiment | string | 只读/离线/生产只读复测类下一步 |
| priority | string | `P0`/`P1`/`P2` |
| risk_notes | string[] | 可空数组 |

## 4. quality-followup.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `qfollow-%06d` |
| source_path | string | 实际打开核对过的真实路径（文件或目录） |
| start_line / end_line | int | 实际核对行区间（目录级观察用 1-1 哨兵，不作引用） |
| observation | string | ≤300 字实际观察 |
| recommended_action | string | `review_only`/`exclude_candidate`/`add_alias`/`split_chunk_candidate`/`manual_source_review` |
| confidence | string | `low`/`medium`/`high` |
| risk_notes | string[] | 可空数组 |
| related_eval_ids | string[] | 受影响的上一批 eval id（校验器核对存在性），可空数组 |

## null 语义总表

- `rewrite_question`：非 rewrite 一律 null。
- `suggested_expected_mode`：审查未建议改模式时填原值（不为 null）；仅来源路径非法时为 no_evidence。
- 黄金集/审查记录中 knowledge 之外条目的来源四字段：一律 null（缺证据 ≠ 伪造证据）。
- `related_eval_ids` / `risk_notes`：空数组表示无，而不是缺失。
