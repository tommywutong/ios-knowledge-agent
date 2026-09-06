# schema.md —— 本批次所有 JSONL 的字段规范

所有 JSONL 文件均为 UTF-8、一行一个合法 JSON 对象、无 BOM、无 Markdown 包裹。
`null` 的语义在每条字段下单独说明；除此之外的字段不允许 `null`（缺失即违规）。
行号一律 1-indexed、含首尾，与 `SPEC.md` 的 chunk 约定一致。

## 1. source-coverage.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| source_id | string | 来源名，取 config.yaml 的 source 名：`obsidian-ios`/`summer2026`/`summer-labs`/`objc4-source`/`apple-docs-core`/`apple-docs-bulk`/`apple-archive` |
| source_path | string | 真实存在的绝对路径（生成脚本已验证） |
| content_kind | string | `note\|doc\|wwdc\|blog\|source_code` |
| topic | string | 该文件的主题（中文短语） |
| platform | string | `iOS`/`Apple平台`/`跨平台` 等 |
| language | string | `zh\|en\|mixed` |
| line_count_estimate | int | 实际统计的物理行数（非估算） |
| selection_reason | string | 为什么选入本批次 |
| risk_notes | string[] | 风险说明，可为空数组 |

## 2. terminology-aliases.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `alias-%06d`，批次内唯一 |
| canonical_term | string | 规范术语（符号/类名/概念名） |
| language | string | `zh\|en\|mixed` |
| aliases | string[] | ≥1 条别名/改写/中英文写法/常见错拼 |
| category | string | `runtime`/`memory`/`runloop-gcd`/`uikit`/`network`/`kvc-kvo-notify`/`block`/`foundation`/`swift-interop`/`build-startup`/`persistence` |
| platform_scope | string[] | 如 `["iOS","Objective-C"]` |
| ambiguity | string | `low\|medium\|high` |
| disambiguation_hint | string | 高/中歧义时的澄清说明；low 时可为空串 |
| evidence_path | string\|null | 真实原始资料路径；**null = 未在原始资料中定位到该术语，仅作术语候选** |
| evidence_start_line | int\|null | 术语在该文件中实际命中的行；null 同上 |
| evidence_end_line | int\|null | 与 start 相同（命中行本身）；null 同上 |
| risk_notes | string[] | 证据为 null 时必含 `"术语候选，未作为事实证据验证"` |

## 3. eval-candidates/batch-*.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `eval-%06d`，全批次唯一 |
| question | string | 问题正文（中文为主，可含英文符号） |
| category | string | `answerable\|symbol\|alias\|comparison\|follow_up\|no_evidence\|general\|cross_platform` |
| topic | string | `runtime`/`memory`/`runloop-gcd`/`uikit`/`network`/`kvc-kvo-notify`/`block`/`foundation`/`build-startup`/`persistence`/`source-symbol`/`routing`/`general` |
| difficulty | string | `easy\|medium\|hard` |
| expected_mode | string | `knowledge\|no_evidence\|general` |
| expected_source_path | string\|null | knowledge 必填且真实存在；其余为 null |
| expected_start_line | int\|null | knowledge 必填（小节标题行或短语命中行）；其余 null |
| expected_end_line | int\|null | knowledge 必填（该小节最后一行）；其余 null |
| expected_evidence_type | string\|null | `note\|doc\|wwdc\|blog\|source_code`；knowledge 必填；其余 null |
| aliases | string[] | ≤5 条同义改写；knowledge 必填 |
| dialogue_context | object[] | follow_up 必填；元素 `{role, content, mode}`，role 取 `user\|assistant` |
| rationale | string | 路由与预期证据范围说明 |
| risk_notes | string[] | 模板生成/标题推断等风险 |
| created_from | string | `source-grounded\|adversarial-routing\|follow-up-template` |

约束：`expected_mode=knowledge` 时来源三字段与 evidence_type 必填且路径已验证存在；
`expected_mode=no_evidence` 时来源字段全 null 且 rationale 解释原因；
`expected_mode=general` 时来源字段全 null。

## 4. retrieval-samples/fts-sample-results.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| eval_id | string | 对应 eval id |
| query | string | 实际执行的查询串 |
| expected_source_path | string\|null | 预期来源 |
| observed_top_paths | string[] | 实际返回的 file_path，按名次，最多 8 条 |
| expected_source_found | bool | 预期路径是否出现在返回结果中 |
| best_rank | int\|null | 预期路径的最佳名次（1 起）；未命中为 null |
| status | string | `pass\|partial\|miss\|not_run`；pass=第1-3名命中，partial=4-8名命中，miss=未命中，not_run=命令失败 |
| suspected_failure_class | string | `none\|alias\|lexical_recall\|source_coverage\|path_mismatch\|other` |
| notes | string | 简短说明 |

## 5. quality-findings.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `quality-%06d` |
| source_path | string | 真实存在的文件路径；目录级或索引级发现可指向真实目录 |
| start_line / end_line | int | 文件发现为实际行范围；目录级或索引级发现固定为 `1 / 1` 哨兵值，不能作为引用 |
| finding_type | string | `duplicate\|directory_page\|bad_conversion\|low_ios_relevance\|ambiguous_version\|conflict\|line_risk\|terminology_gap\|normal_sample` |
| severity | string | `info\|low\|medium\|high` |
| evidence_summary | string | ≤300 字观察摘要 |
| recommended_action | string | `review_only\|exclude_candidate\|add_alias\|split_chunk_candidate\|manual_source_review` |
| confidence | string | `low\|medium\|high` |
| risk_notes | string[] | 可为空数组 |

## 6. failure-triage.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `triage-%06d` |
| failure_class | string | 只允许 `missing_source\|source_quality\|lexical_recall\|semantic_recall\|rerank\|routing\|follow_up_context\|citation_validation\|answer_prompt\|unknown` |
| symptom | string | 症状描述 |
| diagnostic_questions | string[] | 定位用的检查问题 |
| evidence_needed | string[] | 需要收集的证据 |
| safe_next_step | string | 不改动生产的下一步 |
| must_not_do | string | 明确禁止的动作 |
| case_ref | string\|null | 若基于 FTS 抽样案例，引用对应 eval_id；定义类为 null |
