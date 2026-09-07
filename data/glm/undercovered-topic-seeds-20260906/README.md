# undercovered-topic-seeds-20260906 —— README

## 任务

为四个评测薄弱主题（network / persistence / build-startup / swift-interop）建立"真实资料锚定的
评测种子池"。所有题都从实际打开的原始资料小节中出题，行号实测定位；不生成最终答案，不证明生产检索效果。

## 输出

| 文件 | 说明 |
|---|---|
| `seed-eval-candidates.jsonl` | **85 条**种子候选（network 20 / persistence 21 / build-startup 25 / swift-interop 19） |
| `source-map.jsonl` | 85 个实际使用的来源小节（含行号、概念、选入理由、题目映射） |
| `rejected-seed-ideas.jsonl` | 12 条主动放弃的候选（含放弃类别与理由） |
| `coverage.md` / `FINAL_REPORT.md` / `README.md` / `schema.md` | 覆盖说明与结论 |
| `tools/seed_spec.py`、`gen_seeds.py`、`validate_output.py` | 判定表、生成器、校验器（可复跑） |

## 资料选择原则（已执行）

- 只从真实打开过并有完整正文的笔记小节出题；行号由脚本按锚点标题实测定位，小节边界取到同级下一标题。
- 不从目录、标题句、时间戳、系列位置、README、计划文档、meta 工作文档、栏目名出题（拒绝记录见 rejected）。
- 不从知识卡片出题（本轮未打开 knowledge_cards/）。
- 不把"资料中有同主题词"当成"足以回答具体问题"——每条带 answer_boundary 与 source_support_summary。
- 每个来源小节最多 2 题（校验器强制）。
- 禁止"资料里有哪些关键细节""根据你的资料解释"等泛模板句（校验器正则强制）。

## 复核方式

`python3 tools/validate_output.py` —— 校验 JSONL 合法性、唯一 ID、路径与行号范围（含文件行数上界）、
题目-来源映射一致性、每小节 ≤2 题、四主题配额、结构残留/模板句禁用。
