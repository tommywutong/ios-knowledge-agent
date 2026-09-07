# FINAL_REPORT —— evidence-ledger-and-grading-spec-20260906

执行日期：2026-09-06。任务：为生产评测候选清单 130 条建立证据账本、平台边界深查、判分契约与反例对照集。

## 0. 校验记录

```
命令：python3 tools/validate_output.py
结果：ledger: 130 | platform-boundary: 9 | contracts: 98 | pairs: 45
      ledger status: {direct: 78, no_evidence: 20, needs_human: 16, mixed: 5, partial: 11}
      ALL CHECKS PASSED（0 错误）
```

校验覆盖：JSONL 合法、唯一 ID、130 条 manifest 全覆盖、knowledge 路径/行号真实、
quoted_anchor 必须为行号区间子串（逐条验证）、no_evidence 必须有 unsupported_claims 且引用规则完整、
契约与账本回溯一致（mode/refund/must_not_claim 联动）、P0/P1 契约全覆盖、9 条平台边界全覆盖、
correction=true 条目的账本联动、对照对两端不同且 follow_up 对的 base 必须是追问条目。
校验器不使用词汇重叠率作为任何"证据充分"依据。

## 1. 已由真实文件与行号确认的事实

1. 130 条账本全部重新打开来源区间核对；每条 evidence_item 的 quoted_anchor 均为行号区间内的真实原文
   （校验器逐条验证子串关系），不是凭前批记录转写。
2. **dyld 三代分界的一手证据是 `apple-oss-distributions/distribution-macOS` 的 tag 表——macOS 版本映射**；
   iOS 分界只是同期推断（pem-000030，correction_needed=true）。
3. **DYLD_PRINT 可用性观察来自 macOS 的 /usr/lib/dyld**；iOS 真机可用性来源未验证（pem-000031）。
4. **NSUserDefaults 落盘时机观察使用 macOS 的 ~/Library/Preferences 路径**，作者本人曾在文中修正一次
   误判；iOS 沙盒行为只能引 Apple 注释推断（pem-000034/000035）。
5. **镜像个数计价与启动测量盲区（约 400 微秒）为 macOS 探针实验**；iOS 侧是推断（pem-000053/000054）。
6. **SQLite 900 倍、WAL 对照、YYModel 基准为个人实验**；机制部分有 Apple/SQLite 文档与源码佐证，
   数字部分不可外推（pem-000028/000029 + YYModel 三问）。
7. 协议方法无 IMP 的编译器证据（CGObjCMac.cpp:7674）、NSSecureCoding 白名单不递归、KVO 中间类实测等
   12 条 swift/persistence/runtime 题为 direct。

## 2. 只适用于 macOS 或个人实验的观察（16 条 must_state + 5 条 mixed/partial 的限制说明）

- macOS 观察：dyld 环境变量、NSUserDefaults 落盘时机/路径、镜像个数探针、Mach-O/nm 例证产物；
- 个人实验：SQLite 900 倍、WAL 双连接对照、YYModel 基准（14 倍/49 倍）、URLSession 重定向实测表、
  启动盲区 400 微秒、cachePolicy 枚举实测；
- 这些条目在 ledger 中均有 required_answer_constraints，在契约中缺局限说明判 partial/fail。

## 3. 仍是候选的判分设计

- 98 条判分契约的 pass/partial/fail 条件是设计意图，未经过任何真实生产回答的试判；
- needs_human 的 16 条追问：合成占位对话需先被真实多轮会话替换；
- 5 条 mixed 与 11 条 partial 的"部分可答"边界需人工逐条确认；
- 45 对对照的 expected_difference 是预期，不是实测。

## 4. 必须由 Codex 后续在生产 Retrieval v2 验证的行为

1. P0 31 条先行：actor reentrancy 跨语言召回、7 条精确符号的 query_planning、8 条 no_evidence 退款、
   3 条追问继承、4 条跨平台路由、SQLite/WAL 与 dyld 平台边界题的局限说明出现率；
2. 对照对 45 组的分组实测：同主题不同 scope 的命中差异是否如预期分离；
3. 引用定位：回答引用能否落到 ledger 标注行号区间；
4. no_evidence 20 条是否严格退款且不拼接同主题泛资料。

## 5. 原 manifest 中发现但未修改的问题（correction_needed=true，共 3 条）

1. **pem-000030（dyld 三代分界）**：缺少"版本分界证据为 macOS tag 映射、iOS 为同期推断"的约束——
   这是 9 条深查中最重要的一条，按原 manifest 判分可能放过"把 macOS 映射说成 iOS 精确版本"的回答；
2. **pem-000035（原子替换）**：缺少"保证范围以 Apple 注释为准、性能代价未测"的约束；
3. **pem-000054（启动测量盲区）**：缺少"400 微秒为个人实验环境数值"的约束。

以上仅报告，未修改原 manifest；判分时应按 platform-boundary-review 的 required_citation_rule 执行。

## 6. 明确没有做的事情

- 未修改任何既有 GLM 批次、原始资料、`db/`、索引、配置、代码、测试、网站仓库、Cloudflare 或 Git 历史。
- 未运行 `ioskb index/sync/ask/cards`、Wrangler、任何 Cloudflare 命令、生产接口请求或 Git 写操作。
- 未读取或输出任何凭据；未触碰 `mermaid-diagram.svg`。
- 未生成最终问答正文，未宣称生产检索成功或失败；未运行删除命令。
