# 网站版 iOS 知识问答

生产实现已集成到 `/Users/tommywu/tommywu-lab`，不再从本目录复制旧模板。

- API：`functions/api/ios-ask.ts`
- 前端：`src/components/global/IosKnowledgeChat.astro`
- 运行时评估：`docs/ios-agent-runtime-evaluation.json` 与 `scripts/run-ios-agent-evaluation.mjs`
- 当前部署与数据同步流程：[DEPLOY_PLAN.md](DEPLOY_PLAN.md)

当前方案使用 Workers AI 查询向量、Vectorize 语义召回和 D1 FTS 关键词召回；DeepSeek 只根据
本次检索到的原始资料生成带编号引用的流式回答。知识卡片不进入最终事实证据。

更新资料时先导出稳定 `v1-*` Vectorize ID 和 D1 FTS SQL 批次，再按部署计划完成 upsert、stale ID
清理和 D1 原子切换。不要按旧文档创建 `/api/ask`、`RATE_KV` 或独立问答页面。
