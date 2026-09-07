#!/usr/bin/env python3
"""生成 gold-coverage.md：黄金集覆盖表 + 诚实缺口说明。"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
gold = [json.loads(l) for l in (HERE.parent / "gold-eval-candidates.jsonl").read_text(encoding="utf-8").splitlines()]

def tbl(title, key, vals=None):
    c = Counter(key(g) for g in gold)
    keys = sorted(c) if vals is None else [v for v in vals if v in c]
    lines = [f"## {title}", "", "| 值 | 数量 |", "|---|---|"]
    for k in keys:
        lines.append(f"| {k} | {c[k]} |")
    lines.append(f"| **合计** | {len(gold)} |")
    return "\n".join(lines) + "\n"

md = ["# gold-coverage —— 黄金评测候选集覆盖报告\n"]
md.append(f"黄金集共 **{len(gold)}** 条，全部来自阶段 A 审查结论为 keep 或『改写后再次核对通过』的候选，"
          "reject 条目一律未进入。每条都带 semantic_review_id 可回溯审查依据。\n")
md.append(tbl("1. 按 category", lambda g: g["category"]))
md.append(tbl("2. 按 topic", lambda g: g["topic"]))
md.append(tbl("3. 按 difficulty", lambda g: g["difficulty"], ["easy", "medium", "hard"]))
md.append(tbl("4. 按 expected_mode", lambda g: g["expected_mode"], ["knowledge", "no_evidence", "general"]))
md.append(tbl("5. 按 expected_evidence_type", lambda g: str(g["expected_evidence_type"])))
md.append("\n## 6. 覆盖缺口（如实说明，未凑数）\n")
md.append("""| 缺口 | 黄金集中数量 | 原因 | 应补充的真实资料类型 |
|---|---|---|---|
| network（网络） | 2 | 网络类模板题大量被拒（对比对象缺席/小节偏薄），通过审查的独立问题少 | 本地已有 URLSession/HTTP tips 文章与 WWDC 网络场次；需人工从这些文件中手写独立问题 |
| persistence（持久化） | 5 | 持久化笔记多为选型综述，小节锚点覆盖率高但厚度中等，多数被判 rewrite | 已有 SQLite/FMDB/持久化选型笔记；可人工细化到事务/索引/FMDB 队列的具体小节出题 |
| cross_platform（跨平台干扰） | 6 | 该类型本来就只有 20 条源候选 | 需要新增真实跨平台语料或人工构造对比题 |
| build-startup（构建启动） | 5 | 该主题在评测池中基数小（19 条）且 84% FTS miss 反映问法差异 | Mach-O/dyld/启动三篇笔记外，可补 WWDC startup 相关场次与官方文档 |
| swift-interop（Swift 互操作） | 0（仅 build-startup 内极少量相关） | 源池只有 19 条且审查通过率低 | tips 的 Swift 方法调用/Existential Container/struct-class 文章可人工出题；WWDC Swift 场次未入库评测 |
| 多轮追问（follow_up） | 16 | 源池 81 条，按配额与评分截取 | 上一批的合成上下文追问仍需人工确认衔接后可再扩 |
| 精确符号（symbol） | 24 | objc4 源码题保持小而硬；源池 154 条 | objc4 更多元数据结构（objc-file.mm、objc-initialize.mm）可人工补充 |""")
md.append("""
## 7. 使用边界

- 黄金集是"可投入评测的候选"，不是生产回归集：knowledge 条目的来源可支撑性经过规则化语义审查，
  但最终适配性（尤其 rewrite 的 12 条）建议人工终审后再用于生产对照。
- no_evidence/general 条目不携带来源路径，属设计预期；不得为其伪造出处。
- 追问条目的 dialogue_context 中 16 条里有部分上一轮助手内容为合成占位（risk_notes 已标注）。
- 未依据任何一次本地 FTS miss 将黄金集条目标记为"生产故障"，检索层结论必须由生产 Retrieval v2 复测得出。
""")
(HERE.parent / "gold-coverage.md").write_text("\n".join(md), encoding="utf-8")
print("gold-coverage written")
