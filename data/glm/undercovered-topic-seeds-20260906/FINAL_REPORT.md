# FINAL_REPORT —— undercovered-topic-seeds-20260906

执行日期：2026-09-06。任务：为 network / persistence / build-startup / swift-interop 四个评测薄弱主题
建立"真实资料锚定的评测种子池"。

## 0. 校验记录

```
命令：python3 tools/validate_output.py
结果：seeds: 85 | source-map: 85 | rejected: 12
      topics: {network: 20, persistence: 21, build-startup: 25, swift-interop: 19}
      ALL CHECKS PASSED（0 错误）
```

校验覆盖：JSONL 合法性、唯一 ID、来源路径真实、行号范围（含文件行数上界）、题目-来源映射双向一致、
每来源小节 ≤2 题、四主题配额、题面结构残留与泛模板句禁用（含"根据你的资料""资料里有哪些关键细节"）。

## 1. 产出

| 文件 | 数量 | 说明 |
|---|---|---|
| seed-eval-candidates.jsonl | 85 | network 20 / persistence 21 / build-startup 25 / swift-interop 19 |
| source-map.jsonl | 85 | 全部为完整正文的笔记小节（21 个文件），行号实测 |
| rejected-seed-ideas.jsonl | 12 | 主动放弃记录（结构标题 3、证据不足 1、概念重复 2、不自然问法 4、自动拒收 2） |

## 2. 已证实 / 候选 / 待验证 的边界

- **已证实**：85 条的来源路径与小节行号均实测定位；每小节正文密度经校验（≥3 行正文或 ≥8 行代码）；
  每小节 ≤2 题；未使用目录/标题句/时间戳/README/meta/知识卡片。
- **候选**：每题的 `answer_boundary` 与"来源可支撑边界"是规则+人工通览标题结构后的判断，
  未经逐字精读全部小节；题面的自然性为作者判断。
- **待生产验证**：这些种子在生产 Retrieval v2 上的召回/重排/别名/路由表现，本批不做任何断言。

## 3. 各主题最薄弱的资料点（下轮补题方向）

1. **network**：TLS/证书校验细节、HTTP/2、URLSession 后台下载完整机制——本地无完整专题。
2. **persistence**：Core Data 只有"代价"视角的间接提及，缺独立完整小节。
3. **build-startup**：Swift 链接特性（Swift metadata、protocol conformance）语料缺失。
4. **swift-interop**：WWDC en 场次质量参差（10254 逐字稿压成单行），可用性受限。

## 4. 明确没有做的事情

- 未修改任何既有 `data/glm/` 批次（r3 已完成并校验通过后才启动本任务）。
- 未修改原始资料、Obsidian、`26暑期内容`、`data/repos/`、`db/`、索引、配置、代码、测试、网站、Cloudflare。
- 未运行 `ioskb index/sync/ask/cards`、Wrangler、部署或任何 Git 写操作。
- 未读取或输出任何凭据；未触碰 `mermaid-diagram.svg`。
- 未生成最终答案，未宣称生产检索效果。

## 5. 最值得 Codex 再审的 20 条

见 `coverage.md` 第 5 节（seed-000021/024/025/032/034/035/036/037/041/042/043/045/049/051/053/054/056/058/063/064）。
优先理由：全部为 hard 级机制题，锚定小节信息密度高，且多为"以讹传讹澄清类"，
生产检索的召回与重排最容易在这类题上暴露差距。
