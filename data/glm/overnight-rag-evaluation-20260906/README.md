# overnight-rag-evaluation-20260906

GLM 5.3 过夜离线批次：为 iOS 知识库 RAG 生成"待程序和人工复核"的检索评测资产。

## 目标

1. **检索评测题库**（`eval-candidates/`）：≥1,200 条评测候选，覆盖召回、路由、no_evidence、追问能力，全部可按来源路径和行号核验或明确标注为无证据/路由题。
2. **术语与别名库**（`terminology-aliases.jsonl`）：≥400 条中英文术语记录，用于后续查询规划与关键词扩展。
3. **资料质量发现**（`quality-findings.jsonl`）：≥300 条对实际检查过的资料的质量标记（重复、目录页、坏转换、低相关、行号风险等）。
4. **失败归因框架**（`failure-triage.jsonl`）：≥80 条失败模式定义与基于抽样的候选案例。
5. **FTS 离线抽样**（`retrieval-samples/`）：≥240 条只读 FTS 检索抽样结果。

## 禁止边界（本批次已遵守）

- 未修改任何原始资料：Obsidian、`26暑期内容`、`data/repos/`、`knowledge_cards/`、`db/`、网站仓库。
- 未运行任何写索引/生成卡片/同步/导出/部署命令（无 `index`、`sync`、`cards`、`export-*`、Cloudflare/Wrangler/Pages/D1/Vectorize）。
- 只使用了允许的只读检索命令 `uv run ioskb search "<问题>" --no-vector -k 8`。
- 未读取、记录任何凭据；未执行任何 git 写操作。
- 所有产物都是候选，不自动进入生产、原始语料或知识卡片。

## 文件用途

| 文件 | 用途 |
|---|---|
| `schema.md` | 所有 JSONL 的逐字段格式定义 |
| `work-log.md` | 分阶段执行记录、扫描范围、阻碍与未解决风险 |
| `source-coverage.jsonl` | 本批次实际检查并用于构建候选的资料覆盖面 |
| `terminology-aliases.jsonl` | 术语与别名候选（含证据行验证结果） |
| `eval-candidates/batch-*.jsonl` | 检索评测候选，按主题分批 |
| `retrieval-samples/fts-sample-results.jsonl` | 只读 FTS 抽样结果 |
| `quality-findings.jsonl` | 资料质量发现（只报告，不执行修复） |
| `failure-triage.jsonl` | 失败分类定义与候选案例 |
| `coverage-report.md` | 全量统计与人工复核优先级 |
| `FINAL_REPORT.md` | 批次总结 |
| `tools/` | 本批次内部使用的只读生成/验证脚本（属于批次目录内产物） |

## 复核方式

1. **JSONL 语法**：逐行 `json.loads` 校验（已由生成脚本执行，人工可复跑）。
2. **路径与行号**：`knowledge` 候选的 `expected_source_path` 必须真实存在，行号范围由脚本在原始文件中定位标题/短语所得；复核时可抽查 `sed -n '<start>,<end>p' <path>` 是否对题。
3. **题面有效性**：模板生成的题需人工确认对应小节确实回答该问题（`risk_notes` 中已标注 `模板生成待复核` 的条目优先）。
4. **FTS 抽样**：结果全部来自真实命令输出，可复跑同一查询对照。
5. `coverage-report.md` 列出最值得人工优先复核的前 30 项。
