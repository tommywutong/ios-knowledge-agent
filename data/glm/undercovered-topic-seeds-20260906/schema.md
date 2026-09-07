# schema.md —— 本批次 JSONL 字段规范

UTF-8、一行一个合法 JSON 对象。行号 1-indexed 含首尾。

## 1. seed-eval-candidates.jsonl（85 条）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `seed-%06d` |
| question | string | 题面；禁止结构残留与泛模板句（校验器正则强制） |
| category | string | 只允许 `answerable`/`symbol`/`alias`/`comparison`/`follow_up` |
| topic | string | `network`/`persistence`/`build-startup`/`swift-interop` |
| difficulty | string | `easy`/`medium`/`hard` |
| expected_mode | string | 种子题固定 `knowledge` |
| expected_source_path | string | 真实存在的原始资料路径 |
| expected_start_line / expected_end_line | int | 锚点小节实测范围（1 ≤ start ≤ end ≤ 文件行数） |
| expected_evidence_type | string | 本轮全部为 `note` |
| normalized_subject | string | 去笔记措辞后的自然技术对象 |
| answer_boundary | string | 该题问到哪里为止 |
| source_support_summary | string | 来源为何能支撑该边界（含实测正文/代码行数与小节开头摘述） |
| aliases | string[] | ≥1 条同义改写 |
| dialogue_context | object[] | 仅 follow_up 非空；`{role, content, mode}` |
| why_this_is_a_real_user_question | string | 用户不看笔记也会自然提出该问题的场景 |
| diagnostic_value | string | 能暴露召回/重排/别名/路由/追问/引用定位中的哪类能力 |
| risk_notes | string[] | 可空数组 |

## 2. source-map.jsonl（85 条）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `sec-%03d` |
| topic | string | 四主题之一 |
| source_path | string | 真实路径 |
| start_line / end_line | int | 小节实测范围 |
| source_type | string | 本轮全部为 `note` |
| actual_concepts | string[] | 该小节承载的概念（取自对应题的 normalized_subject） |
| why_selected | string | 选入理由（含正文行数，声明非目录/标题句/时间戳/README/meta） |
| question_ids | string[] | 该小节产出的题目 id（≤2，校验器核对存在性与数量） |
| risk_notes | string[] | 可空数组 |

## 3. rejected-seed-ideas.jsonl（12 条）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | string | `rej-%03d` |
| idea | string | 被放弃的候选（截断描述） |
| kind | string | `document_structure`（文档结构标题/meta/知识卡片）/ `insufficient_evidence`（证据不足）/ `concept_duplicate`（概念重复）/ `unnatural_question`（不自然问法）/ `anchor_missing` / `thin_section` / `section_quota`（自动拒收） |
| topic | string | 所属主题或 `全部` |
| detail | string | 放弃理由 |
