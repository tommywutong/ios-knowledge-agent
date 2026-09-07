#!/usr/bin/env python3
"""定位锚点小节 → 校验正文 → 生成 seed-eval-candidates / source-map / rejected-seed-ideas。"""
import json, re, sys
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from seed_spec import S, FILES

_file_cache = {}
def lines_of(p):
    if p not in _file_cache:
        _file_cache[p] = Path(p).read_text(encoding="utf-8", errors="replace").split("\n")
    return _file_cache[p]

def locate(path, anchor):
    """返回 (start, end, level) 或 None。"""
    ls = lines_of(path)
    for i, ln in enumerate(ls, 1):
        m = re.match(r"^(#{1,4})\s+(.+?)\s*$", ln)
        if m and m.group(2).strip() == anchor:
            level = len(m.group(1))
            for j in range(i, len(ls)):
                m2 = re.match(r"^(#{1,%d})\s" % level, ls[j])
                if m2:
                    return i, j, level
            return i, len(ls), level
    return None

def prose_of(ls, s, e):
    seg = ls[s-1:e]
    prose = [l.strip() for l in seg if len(l.strip()) > 12 and not l.strip().startswith("#") and not l.strip().startswith("| ---")]
    fence = False
    code = 0
    for l in seg:
        if l.strip().startswith("```"):
            fence = not fence; continue
        if fence: code += 1
    return prose, code

# follow_up 转换（自然且必要的最小上下文）
FOLLOWUP = {
    "SQLite 目录下出现的 -wal 和 -shm 文件是什么？能直接删吗？": {
        "ctx": [
            {"role": "user", "content": "SQLite 开启 WAL 后并发行为到底改了什么？", "mode": "knowledge"},
            {"role": "assistant", "content": "（上一轮介绍了 WAL 模式如何把写操作先落到独立的 WAL 文件、读写不再互斥。）", "mode": "knowledge"},
        ],
        "q": "那目录下多出来的 -wal 和 -shm 文件是什么？能直接删吗？",
    }
}

OUT = HERE.parent
records = []
sections = []
sec_index = {}
sec_map = {}
rejects = []
for (topic, fkey, anchor, question, cat, diff, aliases, subject, boundary, intent, diag) in S:
    path = FILES[fkey]
    loc = locate(path, anchor)
    if not loc:
        rejects.append({"idea": question[:60], "kind": "anchor_missing",
                        "detail": f"锚点『{anchor}』在 {Path(path).name} 中未找到（人工核对该文件标题后弃用此条）",
                        "topic": topic})
        continue
    s_line, e_line, level = loc
    ls = lines_of(path)
    prose, code = prose_of(ls, s_line, e_line)
    if len(prose) < 3 and code < 8:
        rejects.append({"idea": question[:60], "kind": "thin_section",
                        "detail": f"小节『{anchor}』正文过薄（正文行 {len(prose)}），不足以支撑问题",
                        "topic": topic})
        continue
    key = (path, s_line, e_line)
    if key not in sec_index:
        sec_index[key] = "sec-%03d" % (len(sec_index) + 1)
        sec_map[key] = []
    if len(sec_map[key]) >= 2:
        rejects.append({"idea": question[:60], "kind": "section_quota",
                        "detail": f"小节『{anchor}』已达每小节 2 题上限", "topic": topic})
        continue
    fu = FOLLOWUP.get(question)
    if fu:
        question = fu["q"]
        cat = "follow_up"
    qid = "seed-%06d" % (len(records) + 1)
    sec_map[key].append(qid)
    text_head = prose[0][:36] if prose else "以代码示例为主"
    records.append({
        "id": qid,
        "question": question,
        "category": cat,
        "topic": topic,
        "difficulty": diff,
        "expected_mode": "knowledge",
        "expected_source_path": path,
        "expected_start_line": s_line,
        "expected_end_line": e_line,
        "expected_evidence_type": "note",
        "normalized_subject": subject,
        "answer_boundary": boundary,
        "source_support_summary": f"小节『{anchor}』（第{s_line}-{e_line}行）以『{text_head}…』起笔，共正文 {len(prose)} 行、代码 {code} 行，围绕{subject}展开，可支撑上述边界。",
        "aliases": aliases,
        "dialogue_context": (fu["ctx"] if fu else []),
        "why_this_is_a_real_user_question": intent,
        "diagnostic_value": diag,
        "risk_notes": [],
    })

# source-map
for (path, s_line, e_line), qids in sec_map.items():
    ls = lines_of(path)
    prose, _ = prose_of(ls, s_line, e_line)
    topic = next(r["topic"] for r in records if r["expected_source_path"] == path and r["expected_start_line"] == s_line)
    sections.append({
        "id": sec_index[(path, s_line, e_line)],
        "topic": topic,
        "source_path": path,
        "start_line": s_line, "end_line": e_line,
        "source_type": "note",
        "actual_concepts": [r["normalized_subject"] for r in records if r["expected_source_path"] == path and r["expected_start_line"] == s_line],
        "why_selected": f"完整正文的专题小节（正文 {len(prose)} 行），直接讲解所列概念，非目录/标题句/时间戳/README/meta 内容。",
        "question_ids": qids,
        "risk_notes": [],
    })
sections.sort(key=lambda x: x["id"])

with (OUT / "seed-eval-candidates.jsonl").open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
with (OUT / "source-map.jsonl").open("w", encoding="utf-8") as f:
    for r in sections:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# 补充主动放弃的类别（人工判定）
extra_rejects = [
 {"idea": "『两种格式，四点六倍』小节出对比题", "kind": "document_structure", "topic": "persistence",
  "detail": "r2 红队确认的反例模式：标题为行文碎片（对比对象不成立）；同小节改出『归档产物也是一个 plist』这条自然题"},
 {"idea": "WWDC 10254『Swift concurrency: Behind the scenes』出题", "kind": "insufficient_evidence", "topic": "swift-interop",
  "detail": "该文件仅 57 行且逐字稿压在超长单行里（行号风险）；swift-interop 改用 tips 专题与 10133 场次（已用于 r3 提升题，不重复）"},
 {"idea": "tips《静态库和动态库对比》《Mach-O可执行文件》出题", "kind": "concept_duplicate", "topic": "build-startup",
  "detail": "与 Obsidian《iOS 静态库与动态库》《iOS Mach-O》同主题，后者正文更完整"},
 {"idea": "tips《使用偏好设置、属性列表、归档解档保存数据、恢复数据》出题", "kind": "concept_duplicate", "topic": "persistence",
  "detail": "与 per2/per3 两个 Obsidian 专题重复覆盖"},
 {"idea": "《CocoaPods的安装与使用》《使用CocoaPods创建公开、私有pod》出题", "kind": "unnatural_question", "topic": "build-startup",
  "detail": "安装操作步骤类内容，难以形成不看笔记也会自然提出的技术问题"},
 {"idea": "《LLDB的使用》出题", "kind": "unnatural_question", "topic": "build-startup",
  "detail": "命令清单型内容，问题会退化为工具手册查询"},
 {"idea": "meta/ 工作文档（PROJECT_STATUS.md 等）出题", "kind": "document_structure", "topic": "build-startup",
  "detail": "仓库维护文档非技术资料；r2 巡检已标记其入库风险"},
 {"idea": "知识卡片（knowledge_cards/）出题", "kind": "document_structure", "topic": "全部",
  "detail": "任务禁止从知识卡片出题；本轮未打开该目录"},
 {"idea": "《NSURLSession的使用（一）》4.x 小节出题", "kind": "unnatural_question", "topic": "network",
  "detail": "新建工程/逐步截图类教程内容，技术意图由 net2 的 API 小节覆盖"},
 {"idea": "『今天还有输出的』『iOS 侧没有这张表』『Xcode 自己怎么填』等小节", "kind": "unnatural_question", "topic": "build-startup",
  "detail": "行文碎片标题，无法在不编造的前提下改写为自然独立问题"},
]
with (OUT / "rejected-seed-ideas.jsonl").open("w", encoding="utf-8") as f:
    for i, r in enumerate(rejects + extra_rejects, 1):
        r["id"] = "rej-%03d" % i
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print("seeds:", len(records), dict(Counter(r["topic"] for r in records)))
print("categories:", dict(Counter(r["category"] for r in records)))
print("sections:", len(sections))
print("rejected auto:", len(rejects), "| total:", len(rejects) + len(extra_rejects))
for r in rejects:
    print("  AUTO-REJECT:", r["kind"], "|", r["detail"][:70])
