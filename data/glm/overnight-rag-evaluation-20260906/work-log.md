# work-log —— overnight-rag-evaluation-20260906

## 阶段 0：启动与边界确认（2026-09-06）

- 完整阅读 AGENTS.md、HANDOFF.md、PROGRESS.md、SPEC.md、config.yaml、README.md。
- 只读核对：本仓库 `main` 与 `origin/main` 同步，工作区仅含用户自己的未跟踪文件 `mermaid-diagram.svg`（未触碰）。
- 确认 `data/glm/` 此前不存在，本批次目录为全新创建，无覆盖风险。
- 写入范围锁定为本批次目录；辅助脚本全部放在批次目录内 `tools/`。

## 阶段 1：资料覆盖清单

- 扫描范围（只读 `ls`/`find`/`wc -l`）：
  - `/Users/tommywu/Obsidian/iOS/20 专题笔记/`（52 个 md，11 个子目录）
  - `/Users/tommywu/Desktop/26暑期内容/tips-master/sources/`（129 个 md）
  - `/Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced/`（19 个 md）
  - `/Users/tommywu/Desktop/26暑期内容/iOS底层源码探索/objc4/`（objc4 源码，重点 runtime 头文件与 msgSend 实现）
  - `/Users/tommywu/Desktop/26暑期内容/MemoryMapLab/`
  - `data/repos/apple-docs-vault/wwdc/`（286 个 md）与 `blogs/`
  - `data/repos/apple-developer-archive-vault/`（抽样）
- 产出：`source-coverage.jsonl`，只记录脚本验证过存在且统计过行数的文件。**137 条**（obsidian-ios 52、summer2026 52、objc4-source 15、apple-docs-core 14、summer-labs 4）。
- 阻碍：objc4 该版本无 `objc-runtime-old.mm`（未收录）；`objc-msg-arm64.s` 实际位于 `runtime/Messengers.subproj/`，已按真实路径修正。

## 阶段 2：术语与别名库

- 术语数据由人工按 11 个类别编写（436 条唯一术语），证据定位由脚本在 137 个覆盖文件内做精确子串扫描（区分中英文）。
- 产出：`terminology-aliases.jsonl` **436 条**，其中 **342 条**定位到真实证据行（路径+行号实测）；**94 条**未能在覆盖文件中命中，已置 `evidence_* = null` 并标注"术语候选，未作为事实证据验证"。
- 高歧义术语 3 条（copy、atomic、Category 与 Extension 等），中歧义 210 条。
- 风险：证据行是"术语首次出现行"，不代表该行完整解释了术语，仅供人工复核起点。

## 阶段 3：评测题库

- 方法：语料标题索引（270 文件 / 5,612 标题）+ 六类意图模板（查询/机制/排障/对比/边界/概括）按主题循环生成 knowledge 题；精确符号题锚定 objc4 源码与 tips 文件实测命中；no_evidence/general/cross_platform/追问题为人工策展。
- 关键约束：knowledge 题的 `expected_source_path/行号` 全部由脚本实测定位（标题行或短语行），定位失败即丢弃；生成后全量校验"路径存在 + 行号合法"为 0 错误，批次间无重复 id。
- 产出 8 个批次共 **1,866 条**（runtime 164 / memory 207 / runloop-gcd 224 / uikit-network 等 821 / source-symbols 119 / routing 102 / alias 148 / follow-up 81）。
- 风险：模板生成的题面与小节内容适配需人工复核（risk_notes 已逐条标注）；跨平台题中 11 条 knowledge 题已锚定 iOS 侧证据并补齐别名；追问的"上一轮助手内容"部分为合成占位。

## 阶段 4：FTS 抽样（最终）

- 首轮按主题顺序截断导致 runtime/uikit/source-symbol 未被抽到，已改为**主题轮转均衡抽样**重跑：252 条，覆盖全部 13 个主题桶。
- 最终状态：**pass 66 / partial 46 / miss 140 / not_run 0**。
- 关键信号：symbol 类 0/20 命中（top8 被 `apple-docs-vault/oss` 周报/博客镜像占据）；build-startup 84%、source-symbol/swift-interop 100% miss；kvc-kvo-notify/uikit/runloop-gcd 表现最好（miss 24-25%）。
- **重要发现**：FTS 返回的 observed_top_paths 中有 31 条在磁盘上不存在——本地索引含陈旧 display path（`awesome-ios-interview-main/articles/ios-basics/` 已从磁盘消失但仍入库，约 32 条路径），已在 quality-findings 登记为 medium 发现，未做任何清理。
- 结果文件：`retrieval-samples/fts-sample-results.jsonl`。

## 阶段 5：资料质量发现（最终）

- 产出：`quality-findings.jsonl` **332 条**（含追加的 2 条陈旧索引/双路径发现）。全部为"发现报告"，未执行任何修复或排除。

## 阶段 6：失败归因（最终）

- 产出：`failure-triage.jsonl` **120 条** = 定义类 18 + 案例类 102（lexical_recall 52、rerank 38、missing_source 12；抽样案例的 source_coverage→missing_source、alias→lexical_recall 已映射到允许类别）。

## 阶段 7：报告

- `coverage-report.md` 与 `FINAL_REPORT.md` 已写入；全量 JSONL schema 校验 3,143 行 0 错误。

## 未解决风险

1. 模板题的"题面-小节适配"必须人工抽查（尤其 compare/boundary 类）。
2. 94 条术语未找到语料证据，存在笔者常识性错误风险。
3. FTS 抽样仅覆盖本地 `--no-vector` 路径，不能推断生产 Vectorize+RRF+reranker 的效果。
4. no_evidence 题中的部分主题（如 Combine、SwiftUI）可能在 apple-archive/bulk 有零星 FTS 命中，生产判定需复核。
