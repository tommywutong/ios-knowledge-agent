# golden-set-red-team-r3-20260906 —— README / schema

## 任务

对 r2 黄金集 160 条做**红队审查**（假设用户从未看过任何笔记标题/章节/编号/系列），并重审全部
20 条 no_evidence 题。产出"小而硬"的 r3 强集。此前批次一律只读。

## 输出

| 文件 | 说明 |
|---|---|
| `r3-audit.jsonl` | 160 条逐题红队判定（keep 112 / rewrite 19 / remove 29） |
| `no-evidence-audit-r3.jsonl` | 20 条 no_evidence 全量重审（全部 retain） |
| `gold-eval-candidates-r3.jsonl` | **131 条** r3 强集（不强制凑满 160，质量优先） |
| `FINAL_REPORT.md` | 结论与统计 |
| `tools/audit_r3.py`、`build_r3.py`、`validate_output.py` | 可复跑脚本与校验器 |

## schema 要点

### r3-audit.jsonl
`id`(r3-%06d)、`source_r2_id`、`source_eval_id`、`decision`(keep/rewrite/remove)、
`natural_query_test`(pass/fail)、`technical_intent`（一句话技术意图；general/no_evidence 题如实写
"无技术意图，作路由/无证据边界测试"）、`comparison_validity`(not_applicable/valid/invalid)、
`source_sufficiency`(strong/partial/weak/not_applicable)、`reason`、`rewrite_question`(仅 rewrite)、
`confidence`、`risk_notes`。
**keep/rewrite 额外必填**：`normalized_subject`（去笔记措辞后的自然技术对象）、
`answer_boundary`（题问到哪里为止）、`source_support_summary`（来源为何能支撑该边界，基于实际读取的片段）。

### no-evidence-audit-r3.jsonl
`source_r2_id`、`source_eval_id`、`question`、`decision`、`specific_claim_checked`、
`evidence_search_scope`、`evidence_paths_checked`、`reason`、`confidence`、`risk_notes`。
只有发现能直接回答该具体主张的可靠资料才可 promote。

### gold-eval-candidates-r3.jsonl
同 r2 字段 + `normalized_subject`/`answer_boundary`/`source_support_summary`/`semantic_review_id`/
`no_evidence_audit_id`；伪对比改写题类别随题面降为 answerable。

## 复核方式

`python3 tools/validate_output.py` —— 含 5 条已知反例黑名单（绝不进入 r3）、题面结构残留正则、
comparison 必须 valid、keep/rewrite 必须三字段齐备、no_evidence 必须关联 r3 审查记录。
校验器不使用词汇重叠率作为任何保留依据。
