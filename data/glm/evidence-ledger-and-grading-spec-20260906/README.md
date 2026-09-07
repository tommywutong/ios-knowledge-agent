# evidence-ledger-and-grading-spec-20260906 —— README

## 任务

为生产验证候选清单的 130 条逐条建立"证据账本"，并对 9 条高风险平台边界条目做独立深查，
为 P0/P1 生成判分契约候选、构造反例对照集。全部产物是"待 Codex 人工审核的离线判分候选"，
不生成最终问答正文，不调用任何生产接口。

## 输出

| 文件 | 说明 |
|---|---|
| `evidence-ledger.jsonl` | **130 条**全覆盖证据账本（core_claims 原子主张 / evidence_items 逐主张证据 / unsupported_claims） |
| `platform-boundary-review.jsonl` | **9 条**高风险平台边界深查（SQLite/WAL、dyld、URLSession、NSUserDefaults、镜像/盲区） |
| `grading-contract-candidates.jsonl` | **98 条**判分契约（P0 31 + P1 67 全覆盖） |
| `adversarial-pairs.jsonl` | **45 对**反例对照（7 类，全部锚定 manifest 真实条目或其最小改写） |
| `README.md` / `schema.md` / `coverage.md` / `FINAL_REPORT.md` | 说明与结论 |
| `tools/gen_ledger.py`、`gen_boundary_review.py`、`gen_contracts.py`、`gen_pairs.py`、`validate_output.py` | 可复跑脚本与校验器 |

## 方法要点

- **quoted_anchor 从实际文本提取**：每条 evidence_item 的短摘录由脚本从标注行号区间内取真实原文行，
  校验器再验证其确为区间子串——杜绝"摘录与行号不一致"。
- **主张拆分**：多层主张（机制 + iOS 适用性 + 性能数字）拆成多个 core_claims，分别标注
  evidence_kind 与 support_level；只能支撑一部分的条目 evidence_status=partial/mixed，
  并在 unsupported_claims 写明不能答什么。
- **平台证据性质沿用前批实测结论**：dyld 环境变量段=macOS 观察（strings /usr/lib/dyld）、
  NSUserDefaults 段=macOS 路径观察、镜像个数/启动盲区=macOS 探针实验、SQLite 900 倍/WAL/YYModel=个人实验、
  WWDC 场次=Apple_source、objc4 源码=historical_reference、tips 教程=iOS_public_api。
- **dyld 分界的特殊性**：来源证据是 apple-oss-distributions/**distribution-macOS** 的 tag 映射——
  macOS 事实；iOS 分界只是同期推断，账本已按 partial 处理并在 unsafe 措辞中示范。

## 复核方式

`python3 tools/validate_output.py` —— 校验 JSONL 合法性、唯一 ID、130 条全覆盖、路径/行号真实、
quoted_anchor 与行号区间一致、no_evidence 的 unsupported_claims、契约与账本回溯、
P0/P1 全覆盖、9 条平台边界全覆盖、correction=true 条目的账本联动、对照对两端不同。
校验器不使用词汇重叠率作为任何"证据充分"依据。
