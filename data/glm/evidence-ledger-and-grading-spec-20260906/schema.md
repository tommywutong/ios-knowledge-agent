# schema.md —— 本批次 JSONL 字段规范

UTF-8、一行一个合法 JSON 对象。

## 1. evidence-ledger.jsonl（130 条 = manifest 全覆盖）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `ledger-%06d` |
| manifest_id / origin / origin_id / question / expected_mode / topic / category | 同 manifest | |
| core_claims | string[] | 1-4 条可判定的原子技术主张；多层主张（机制/iOS 适用性/数字）必须拆开 |
| answer_boundary | string | 该题问到哪里为止 |
| evidence_status | string | `direct`（核心主张全部有直接证据）/ `partial`（部分主张仅推断或无 iOS 侧证据）/ `mixed`（直接证据与不可外推数字并存）/ `no_evidence` / `needs_human`（追问的合成上下文需人工确认） |
| evidence_items | object[] | 每元素：`claim_index`、`source_path`、`start_line`、`end_line`、`evidence_kind`（Apple_source/iOS_public_api/macOS_observation/personal_experiment/user_note_inference/historical_reference）、`support_level`（direct/contextual/contradictory）、`excerpt_summary`（≤180 中文字符，概括实际读到的内容）、`quoted_anchor`（≤300 字符原文短摘录，必须为行号区间子串，校验器强制） |
| unsupported_claims | string[] | 资料没有覆盖的主张；no_evidence 条目必填且说明缺失的证据层 |
| required_answer_constraints | string[] | 继承 manifest 的回答约束 |
| citation_acceptance_rule | string | 引用接受规则；no_evidence 条目必须要求返回 no_evidence 且禁止同主题泛资料拼接 |
| confidence | string | `low`/`medium`/`high` |
| risk_notes | string[] | 可空数组 |

## 2. platform-boundary-review.jsonl（9 条）

`id`(pbr-%03d)、`manifest_id`、`specific_claim`、`confirmed_scope`（来源实际确认的范围）、
`not_confirmed_scope`（未确认/不可外推范围）、`evidence_kind`、`platform_version_conditions`
（机器/系统/样本量条件在来源中的说明情况）、`safe_answer_wording`、`unsafe_answer_wording`、
`required_citation_rule`、`correction_needed_in_manifest`(bool)、`correction_reason`。
约束：correction=true 时对应 ledger 条目必须有 unsupported_claims 且引用规则体现平台限制（校验器强制）。

## 3. grading-contract-candidates.jsonl（98 条 = P0+P1 全覆盖）

`id`(gcon-%06d)、`manifest_id`、`question`、`expected_mode`、`minimum_retrieval_requirements`、
`citation_requirements`、`answer_boundary_requirements`、`must_not_claim`、`pass_conditions`、
`partial_conditions`、`fail_conditions`、`refund_expected`(bool，= no_evidence)、
`manual_review_required`(bool)、`manual_review_reason`、`diagnostic_layer`、`priority`。

判分原则（已编码进字段）：knowledge 须同时检查路由/引用/核心主张覆盖/边界；
no_evidence 返回同主题泛资料或虚构引用即 fail 且退款；follow_up 须继承上下文；
macOS/个人实验题缺局限说明为 partial 或 fail；精确符号须命中正确源码/文档文件。

## 4. adversarial-pairs.jsonl（45 对）

`id`(adv-%06d)、`base_manifest_id`（必须存在于 manifest）、`pair_type`（scope_shift/platform_shift/
internal_vs_public/symbol_vs_natural_language/follow_up_context/no_evidence_near_miss/citation_boundary）、
`question_a`、`question_b`（两端必须不同）、`why_different`、`expected_difference`、`evidence_refs`、
`risk_notes`。follow_up 对中 question_b 必须是 manifest 的 follow_up 条目（校验器强制）。
