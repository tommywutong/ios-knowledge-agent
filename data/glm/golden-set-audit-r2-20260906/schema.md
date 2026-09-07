# schema.md —— 本批次 JSONL 字段规范

UTF-8、一行一个合法 JSON 对象。

## 1. gold-audit.jsonl（190 条 = 旧黄金集逐条）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `audit-%06d` |
| source_gold_id | string | 旧黄金集条目 id（gold-%06d），必须存在 |
| source_eval_id | string | 必须与旧黄金集条目一致 |
| decision | string | `keep`/`rewrite`/`remove`；rewrite 必须有 rewrite_question，其余必须为 null |
| standalone_quality | string | `strong`/`partial`/`weak`：是否为真实用户会独立提出的问题 |
| evidence_fit | string | `strong`/`partial`/`weak`/`not_applicable`：标注来源行是否足以支撑问题核心范围；no_evidence/general 为 not_applicable |
| routing_fit | string | `correct`/`questionable`/`wrong` |
| reason | string | 判定依据（含实际读到的片段观察） |
| rewrite_question | string\|null | 仅 rewrite；必须再次打开来源人工确认后填写 |
| confidence | string | `low`/`medium`/`high` |
| risk_notes | string[] | 可空数组 |

硬性规则（由 tools/audit_r2.py 实现）：
- 题面含 `目录 / 这篇在系列中的位置 / 本篇 / 本节 / Part N / 第N(部分|篇|章) / draft / 时间戳标题` → remove
  或"已核对来源的自然概念题"改写（人工核对表写在脚本内，含核对到的片段内容描述）；
- knowledge 题按问题词与来源片段的实际重叠率核验（ascii 不区分大小写 + CJK 2-gram），alias 题按其概念主条目核验，
  cross_platform 题只声明 iOS 侧锚点由上一轮保证（不用 iOS 片段覆盖率高估证据范围）；
- 重叠率不足 → remove，不得只因标题或关键词相同判为有效。

## 2. no-evidence-audit.jsonl（7 条指定候选）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `noevid-%06d` |
| source_eval_id | string | 必须是指定的 7 条之一 |
| decision | string | `retain_no_evidence`/`promote_to_knowledge_candidate`/`remove` |
| question_aspect_checked | string | 被核验的"具体主张" |
| evidence_paths_checked | string[] | 实际检索/打开过的证据路径或检索说明 |
| evidence_summary | string | 实际核对到的内容 |
| reason | string | 判定依据 |
| confidence | string | `low`/`medium`/`high` |
| risk_notes | string[] | 可空数组 |
| promoted_evidence | object\|null | 仅 promote：`{path, start_line, end_line, aux_path}`，校验器核对路径与行号真实性 |

## 3. gold-eval-candidates-r2.jsonl（160 条）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `gold-r2-%06d` |
| source_gold_id | string\|null | 旧黄金集条目；B 阶段提升的条目为 null |
| source_eval_id | string | 原 eval id |
| question | string | keep=原题；rewrite=人工核对后的改写题 |
| category / topic / difficulty / expected_mode | string | 枚举同前批 |
| expected_source_path / expected_start_line / expected_end_line / expected_evidence_type | string/int\|null | knowledge 必填且校验；no_evidence/general 必须 null |
| aliases / dialogue_context | 数组 | 同前批 |
| selection_reason | string | 含复核方式说明 |
| semantic_review_id | string\|null | 指向 gold-audit 的 keep/rewrite 记录 |
| no_evidence_audit_id | string\|null | 指向 no-evidence-audit 的 promote 记录（提升条目专用） |
| diagnostic_value / risk_notes | string / string[] | 同前批语义 |

约束：160-220 条；remove 一律不得进入；题面禁止文档结构残留
（`目录|这篇在系列中的位置|本篇|本节|Part N|第N部分/篇/章|draft:|时间戳标题`，校验器强制）。
