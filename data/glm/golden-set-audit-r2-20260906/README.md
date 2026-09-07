# golden-set-audit-r2-20260906 —— README

## 任务范围

对上一批 `semantic-review-and-golden-set-20260906` 的 190 条黄金评测候选做**逐条人工语义复核与纠错**，
并按"问题的具体主张"重审 7 条此前被错误 reject 的 no_evidence 候选。产出修正版黄金集
`gold-eval-candidates-r2.jsonl`（160 条）。此前两个 GLM 批次一律只读，未修改任何文件。

## 输入

- `semantic-review-and-golden-set-20260906/FINAL_REPORT.md`、`semantic-review.jsonl`、`gold-eval-candidates.jsonl`
- 上一批 `CODEX_REVIEW.md` 指出的 6 条结构标题混入（gold-000023/024/025/026/027/028）
- 原始资料（只读）：Obsidian 笔记、apple-docs-vault、apple-developer-archive-vault

## 输出文件

| 文件 | 说明 |
|---|---|
| `gold-audit.jsonl` | 190 条逐题复核（keep 150 / rewrite 9 / remove 31） |
| `no-evidence-audit.jsonl` | 7 条按具体主张重审（6 retain / 1 promote） |
| `gold-eval-candidates-r2.jsonl` | 修正版黄金集 160 条，全部可回溯 |
| `audit-summary.md` | 复核统计与代表案例 |
| `FINAL_REPORT.md` | 结论（已证实 / 候选 / 待生产验证 / 未做事项） |
| `schema.md` | 字段规范 |
| `tools/audit_r2.py`、`build_r2.py`、`validate_output.py` | 可复跑脚本与校验器 |

## 复核方式

1. `python3 tools/validate_output.py` —— 全量结构 + 跨文件引用 + 禁用结构残留校验。
2. 每条 `gold-audit.jsonl` 记录可对照 `source_gold_id` 打开旧黄金集条目核对题面；
   remove/rewrite 的 `reason` 均引用实际读到的片段内容。
3. `no-evidence-audit.jsonl` 的证据路径可直接打开复验（如 actor reentrancy 的
   `wwdc/en/wwdc2021/10133-protect-mutable-state-with-swift-actors.md` 第 281-295 行）。

## 边界（已遵守）

- 只写入本目录；未修改任何前批文件、原始资料、`db/`、配置、代码、网站、Git 历史。
- 未运行 `index/sync/ask/cards`、Wrangler、部署；未读取任何凭据；未触碰 `mermaid-diagram.svg`。
- 输出全部是候选；未宣称生产检索结论。

## 明确未做事项

- 未删除或改写此前批次的任何记录（纠正只发生在本批次的 r2 文件中）。
- 未把被拒条目"改头换面"塞回黄金集凑数；r2 规模 160 条为复核后的真实存活数。
- 未依据语料存在宽泛主题就推翻具体 no_evidence 问题（B 阶段逐条按主张核对）。
