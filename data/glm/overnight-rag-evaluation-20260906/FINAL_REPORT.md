# FINAL_REPORT —— overnight-rag-evaluation-20260906

GLM 5.3 过夜离线批次总结（执行时间：2026-09-06，全程只读原始资料，写入仅限本批次目录）。

## 1. 已创建的文件

```
data/glm/overnight-rag-evaluation-20260906/
├── README.md                # 批次目标、禁止边界、复核方式
├── schema.md                # 全部 JSONL 的字段规范
├── work-log.md              # 分阶段执行记录
├── source-coverage.jsonl    # 137 条实际检查过的资料覆盖
├── terminology-aliases.jsonl# 436 条术语别名候选
├── eval-candidates/         # 8 个批次共 1,866 条评测候选
│   ├── batch-001-runtime.jsonl (164)
│   ├── batch-002-memory.jsonl (207)
│   ├── batch-003-runloop-gcd.jsonl (224)
│   ├── batch-004-uikit-network.jsonl (821)
│   ├── batch-005-source-symbols.jsonl (119)
│   ├── batch-006-routing-no-evidence.jsonl (102)
│   ├── batch-007-alias-typo.jsonl (148)
│   └── batch-008-follow-up.jsonl (81)
├── retrieval-samples/
│   └── fts-sample-results.jsonl  # 252 条真实 FTS 抽样
├── quality-findings.jsonl   # 332 条资料质量发现
├── failure-triage.jsonl     # 120 条失败归因（18 定义 + 102 案例）
├── coverage-report.md       # 全量统计与 Top30 复核清单
├── FINAL_REPORT.md          # 本文件
└── tools/                   # 批次内只读生成/校验脚本（可复跑）
```

## 2. 资产数量一览

| 资产 | 数量 | 关键质量指标 |
|---|---|---|
| 资料覆盖 | 137 | 全部实测行数，路径真实 |
| 术语别名 | 436 | 342 条有真实证据行；94 条标注无证据 |
| 评测候选 | 1,866 | knowledge 1,775 条 100% 路径/行号实测校验通过；无重复 id |
| FTS 抽样 | 252 | pass 66 / partial 46 / miss 140 / not_run 0；另发现 31 条陈旧索引路径 |
| 质量发现 | 332 | medium 119 / low 105 / info 108 |
| 失败归因 | 120 | 10 个允许类别全覆盖 |

## 3. 可信结论 vs 不可信结论

**可信（有程序化校验）：**
- 所有 knowledge 候选的来源路径真实存在、行号由脚本在原文实测定位，可按 `sed -n 's,e p'` 复核；
- FTS 抽样结果全部来自真实命令输出，可复跑对照；
- 质量发现中的重复对（SHA-256/同名双语）与超长行均为实测；
- 资料边界未被触碰（只有本目录写入，无 git 操作）。

**不可信 / 仅候选（须人工复核）：**
- 1,381 条"模板生成待复核"题的题面与小节内容适配性；
- 94 条无证据术语的正确性；
- 追问题中合成的"上一轮回答"占位文本；
- FTS miss 率**不能**推断生产 Vectorize+RRF+reranker 的效果（本抽样为 FTS-only）；
- no_evidence 题的判定基于语料主题常识，个别主题可能在归档镜像有零星命中。

## 4. 最严重的资料/检索风险

1. **精确符号检索在 FTS 路径失效**：symbol 类抽样 0/20 命中，top8 被 `apple-docs-vault/oss` 第三方镜像（周报/博客）占据；oss 内容以 type=doc 权重 1.12 参与排序，与"官方文档/源码并列第一"的生产意图存在偏差。
2. **WWDC/博客中英双语重复**：已记录 105 对 WWDC 和 60 对博客的双语重复，可能挤占关键词检索候选名额。
3. **编译链接/启动、Swift 互操作主题的中文笔记问法与关键词差异大**（miss 84-100%），别名覆盖不足。
4. **归档/旧稿与正稿并存的冲突风险**（AI 融合稿等）。
5. **本地索引含陈旧 display path**：`awesome-ios-interview-main/articles/ios-basics/` 等 32 个磁盘上已不存在的文件仍会被 FTS 返回，点击引用会失败（只报告，未清理）。

## 5. 下一次人工/Codex 应优先验证的 10 项

1. 抽查 `batch-005` 符号题的 20 条 miss 案例，确认 objc4 源码块在 FTS v2 表中是否可召回；
2. 人工裁定 `oss/` 镜像目录的来源等级与排序权重（quality-findings `ambiguous_version` 条目）；
3. 评估 WWDC zh/en 双语重复的治理方案（保留策略）；
4. 用生产 Retrieval v2 链路（Vectorize+RRF+reranker）重跑本批次抽样集，对照本地 FTS-only 差距；
5. 抽查 10 条 compare/boundary 模板题的"题面-小节"适配；
6. 逐条确认 94 条无证据术语；
7. 针对 build-startup/runtime/memory 的 52 条 lexical_recall 案例输出缺失别名清单，回灌术语表；
8. 确认 no_evidence 题在生产证据探测下的真实判定（尤其 Combine/SwiftUI 等主题）；
9. 复核 11 条跨平台 knowledge 题的锚点与 follow_up 的合成上下文；
10. 决定 low_ios_relevance 34 条 tips 的权重/收录策略。

## 6. 声明

本任务**未修改**任何原始资料（Obsidian、`26暑期内容`、`data/repos/` 镜像、`knowledge_cards/`、`db/`）、未修改索引与本地数据库、未触碰生产配置、Cloudflare 资源、Git 历史或网站仓库；除本批次目录外未创建/修改/删除任何文件；未运行任何写入性命令，仅使用了允许的只读检索 `uv run ioskb search --no-vector`；未读取或记录任何凭据。
