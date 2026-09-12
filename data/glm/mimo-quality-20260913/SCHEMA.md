# MiMo quality batch schema v1

This is an offline candidate-cleaning batch. Nothing in `inputs/` or `outputs/`
is factual evidence, a production evaluation case, or approved training data.

Each output JSONL row must contain exactly these fields:

`schema_version`, `task_id`, `task_kind`, `input_id`, `source_candidate_id`,
`original_question_sha256`, `quality_action`, `quality_reason`,
`rewrite_question`, `duplicate_of_input_ids`, `query_variants`,
`evidence_scope`, `scope_reason`, `unsupported_request_parts`,
`recommended_action`, `confidence`, `admission`, `offline_only`.

Allowed values:

- `schema_version`: `mimo-quality-output/v1`
- `quality_action`: `keep`, `rewrite`, `remove_duplicate`, `remove_unnatural`, `hold_for_human`
- `query_variants[].variant_type`: `colloquial`, `concise`, `english_chinese`, `abbreviation`, `symbol`, `error_tolerant`
- `evidence_scope`: always `insufficient_excerpt`, because original material is not
  copied into this Git-backed work package
- `recommended_action`: `human_review`, `rewrite_then_human_review`, `dedupe_then_human_review`, `source_check_then_review`, `remove_candidate`
- `confidence`: `low`, `medium`, `high`
- `admission`: always `hold`
- `offline_only`: always `true`

`query_variants` contains 1-4 objects with exactly `text`, `variant_type`, and
`purpose`. Reasons must be independent judgments grounded in the supplied
candidate text and non-sensitive metadata. Do not infer source facts, write a
final answer, make an Apple implementation claim, or change source files.
