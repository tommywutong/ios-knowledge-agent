# Candidate consolidation output schema

Each output row contains exactly: `schema_version`, `task_id`, `cluster_id`,
`member_input_ids`, `decision`, `representative_input_ids`, `reason`,
`keep_distinctions`, `recommended_next_step`, `confidence`, `offline_only`, `admission`.

Allowed decisions: `keep_one`, `keep_multiple`, `hold_for_human`.
All outputs must copy the task, cluster and member IDs exactly. `representative_input_ids`
must be a non-empty subset of the members, except `hold_for_human` may leave it empty.
Use `keep_one` only when the supplied rewritten questions test the same learning intent.
Do not infer whether source material supports the questions. No paths, source excerpts,
line numbers, final answers, API keys, production claims, or index changes are allowed.
