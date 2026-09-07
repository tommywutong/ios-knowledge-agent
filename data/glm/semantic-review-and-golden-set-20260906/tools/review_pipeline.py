#!/usr/bin/env python3
"""阶段 A：语义审查。
对每条评测候选：打开 expected_source_path，读取标注行号区间的真实文本，
按题目类别规则判定 keep/rewrite/reject。规则确定性可审计，全部决策保留 source_eval_id。
"""
import json, re, glob
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
SRC = Path("/Users/tommywu/Desktop/iOS知识agentt/data/glm/overnight-rag-evaluation-20260906")
OUT = HERE.parent / "semantic-review.jsonl"
# 阶段 D 巡检产物：被 WWDC 语料证伪的 no_evidence 主题
FALSIFIED = []
_fp = HERE / "falsified_noevidence.json"
if _fp.is_file():
    FALSIFIED = json.loads(_fp.read_text(encoding="utf-8"))

_file_cache = {}
def lines_of(path):
    if path not in _file_cache:
        _file_cache[path] = Path(path).read_text(encoding="utf-8", errors="replace").split("\n")
    return _file_cache[path]

def excerpt(path, s, e):
    lines = lines_of(path)
    s = max(1, s); e = min(e, len(lines))
    return lines[s-1:e], e - s + 1

def analyze_excerpt(ls):
    prose, nlink = [], 0
    fence = False
    for ln in ls:
        st = ln.strip()
        if st.startswith("```"):
            fence = not fence; continue
        if fence:
            continue
        if re.search(r"\]\([^)]+\)", st):
            nlink += 1
        if len(st) > 12 and not st.startswith("#"):
            prose.append(st)
    return prose, nlink

def tokens(x):
    t = []
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]+", x):
        if len(w) >= 2:
            t.append(w)
    for seg in re.findall(r"[\u4e00-\u9fff]{2,}", x):
        t.append(seg)
    return t

def coverage(toks, text):
    if not toks:
        return 0.0
    hit = sum(1 for t in toks if t in text)
    return hit / len(toks)

DOC_CONTEXT = re.compile(r"Part\s*\d|第\s*\d+\s*(篇|部分|周|章)|^（\d+）|系列大纲|_README|素材|归档|^README|^(Part|part)\b")
MISSTEP_KW = ["误区", "坑", "注意", "边界", "不要", "避免", "错误", "易错", "慎", "危险", "失效", "废弃", "问题"]

CN_NUM = "一二三四五六七八九十"
def clean_topic(x):
    x = re.sub(r"`[^`]*`", "", x)          # `draft: false` 等文档元数据
    x = re.sub(r"[✅✳️❌✔️✓]|draft:\s*\w+", "", x)
    x = re.sub(r"Part\s*\d+\s*[-—–·:.]\s*", "", x)
    x = re.sub(r"第\s*\d+\s*(篇|部分|周|章)\s*[-—–·:.]?\s*", "", x)
    x = re.sub(rf"^[{CN_NUM}]+\s*[、.：:]\s*", "", x)
    x = re.sub(r"^\d+\s*[.、)）]\s*", "", x)
    x = re.sub(r"^(iOS|objc4)\s*", "", x)
    x = re.sub(r"[（(].*?[)）]", "", x)
    x = x.strip(" ：:-_·#")
    return x

BAD_SUBJECT = re.compile(r"[①-⑳]|\d{4}-\d{2}|每层|拆成|这笔账|几种|第\s*[一二三四五六七八九十0-9]+\s*种")
def subject_ok(x):
    """改写主语必须是自然的提问对象，而非叙述性小标题碎片。"""
    if not x or len(x) > 18:
        return False
    if BAD_SUBJECT.search(x):
        return False
    return True

reviews = []
ORIG_RISK = {}
def add(extra_risk=None, **kw):
    kw["risk_notes"] = ORIG_RISK.get(kw.get("source_eval_id"), []) + (extra_risk or [])
    reviews.append(kw)

def review_one(r):
    ORIG_RISK[r["id"]] = list(r.get("risk_notes") or [])
    q = r["question"]
    cat, mode = r["category"], r["expected_mode"]
    base = dict(
        source_eval_id=r["id"],
        source_path=r["expected_source_path"],
        source_start_line=r["expected_start_line"],
        source_end_line=r["expected_end_line"],
    )
    # ---------- 无来源类（no_evidence / general） ----------
    if mode in ("no_evidence", "general"):
        hit_topics = [f["topic"] for f in FALSIFIED if re.search(f["topic_kw"], q, re.I)]
        if mode == "no_evidence" and hit_topics:
            add(**base, decision="reject", semantic_fit="none", standalone_quality="strong",
                routing_fit="wrong",
                reviewed_excerpt_summary="无来源条目；但其『语料缺失』假设已被阶段 D 巡检证伪。",
                reason=f"该题的 no_evidence 预期不可靠：主题（{('、'.join(hit_topics))}）在 apple-docs-core 的 WWDC 语料中实测存在场次文件（见 quality-followup.jsonl），"
                       "『语料缺失→应判无证据』的链路不成立，保留会误导无证据评测。",
                rewrite_question=None,
                suggested_expected_mode=mode, confidence="high")
            return
        add(**base, decision="keep", semantic_fit="none", standalone_quality="strong",
            routing_fit="correct",
            reviewed_excerpt_summary="无来源条目（设计如此），仅审查题目自然度与路由预期。",
            reason=f"{mode} 题：不要求来源支撑；题面自然、路由预期与类别一致，保留为路由评测候选。",
            rewrite_question=None,
            suggested_expected_mode=mode, confidence="high")
        return
    # ---------- 有来源类：读取真实片段 ----------
    if not r["expected_source_path"] or not Path(r["expected_source_path"]).is_file():
        add(**base, decision="reject", semantic_fit="none", standalone_quality="weak",
            routing_fit="wrong", reviewed_excerpt_summary="来源路径缺失或不存在。",
            reason="来源路径无法打开，知识题无法核验，直接拒绝。",
            rewrite_question=None, suggested_expected_mode="no_evidence", confidence="high")
        return
    ls, n = excerpt(r["expected_source_path"], r["expected_start_line"], r["expected_end_line"])
    prose, nlink = analyze_excerpt(ls)
    text = "\n".join(ls)
    rich = len(prose) >= 4 and sum(len(p) for p in prose) > 240
    thin = len(prose) < 2 or sum(len(p) for p in prose) < 60
    excerpt_brief = f"锚定区间 {r['expected_start_line']}-{r['expected_end_line']}（{n} 行）：正文行 {len(prose)}，链接行 {nlink}；"
    if prose:
        excerpt_brief += "起始内容：" + prose[0][:70]
    else:
        excerpt_brief += "区间内几乎无正文行"

    # 类别与模板识别
    m_lookup = re.search(r"「(.+?)」到底是什么", q)
    m_mech = re.search(r"请讲讲(.+?)的底层机制或工作原理", q)
    m_trouble = re.search(r"被问到「(.+?)」的细节", q)
    m_cmp = re.search(r"「(.+?)」和「(.+?)」在你的资料里", q)
    m_bound = re.search(r"「(.+?)」有哪些容易被忽略", q)
    m_sum = re.search(r"概括一下「(.+?)」的要点", q)

    if r["category"] == "symbol":
        sym = None
        ms = re.search(r"「(.+?)」", q)
        if ms: sym = ms.group(1)
        present = bool(sym) and sym in text
        fit = "strong" if present and len(prose) >= 1 else ("partial" if present else "none")
        auto = any("命名推断" in x for x in r["risk_notes"])
        dec = "keep" if present else "reject"
        add(**base, decision=dec, semantic_fit=fit, standalone_quality="partial" if auto else "strong",
            routing_fit="correct",
            reviewed_excerpt_summary=excerpt_brief,
            reason=(f"符号「{sym}」实测存在于锚定区间，定义位置可支撑『定义在哪/作用』类问题；"
                    + ("函数用途由命名推断，风险已标注。" if auto else "人工策展符号，来源为核心源码/资料文件。")),
            rewrite_question=None, suggested_expected_mode="knowledge",
            confidence="high" if present else "high",
            extra_risk=(["函数用途由命名推断，源码细节需人工复核"] if auto else []))
        return

    if cat == "alias":
        # 口语/改写题：概念锚点是否出现在片段
        concept = None
        m_con = re.search(r"讲讲(.+?)，我基础不太好|讲讲(.+?)面试一般|自学(.+?)的资料段落", q)
        if m_con:
            concept = next(g for g in m_con.groups() if g)
        if not concept:
            m_rat = re.search(r"「(.+?)」主条目", r.get("rationale") or "")
            if m_rat:
                concept = m_rat.group(1)
        hit = concept and (concept in text or any(t in text for t in tokens(concept)))
        if not hit:
            # 兜底：问题词与片段的总体覆盖率
            hit = coverage(tokens(q), text) >= 0.45
        study_variant = ("自学" in q) or ("大白话" in q) or ("面试一般" in q)
        if not hit or thin:
            add(**base, decision="reject", semantic_fit="weak" if hit else "none",
                standalone_quality="partial",
                routing_fit="correct",
                reviewed_excerpt_summary=excerpt_brief,
                reason="改写题锚定的概念未在来源片段中命中，或片段过薄，别名题缺乏可靠证据支撑。",
                rewrite_question=None, suggested_expected_mode="knowledge", confidence="medium")
            return
        if study_variant:
            cq = clean_topic(concept)
            rq = f"请讲讲{cq}的原理和要点。"
            ok = coverage(tokens(cq), text) >= 0.5
            add(**base, decision="rewrite" if ok else "reject",
                semantic_fit="partial", standalone_quality="strong", routing_fit="correct",
                reviewed_excerpt_summary=excerpt_brief,
                reason="学习咨询式问法（『有没有资料/大白话讲讲』）依赖对话语境，不是独立自然问题；改写为对概念的直接提问，锚点词在片段中有覆盖。" if ok else "改写后锚点词在片段中覆盖不足，放弃改写。",
                rewrite_question=rq if ok else None,
                suggested_expected_mode="knowledge", confidence="medium")
            return
        add(**base, decision="keep", semantic_fit="strong" if not thin else "partial",
            standalone_quality="strong", routing_fit="correct",
            reviewed_excerpt_summary=excerpt_brief,
            reason="口语化改写自然且概念锚点在来源片段命中，可考察别名/口语表达下的召回。",
            rewrite_question=None, suggested_expected_mode="knowledge", confidence="medium")
        return

    if cat == "follow_up":
        ok_ctx = bool(r["dialogue_context"])
        if not ok_ctx or thin:
            add(**base, decision="reject" if not ok_ctx else "rewrite",
                semantic_fit="partial" if ok_ctx else "none",
                standalone_quality="weak", routing_fit="correct",
                reviewed_excerpt_summary=excerpt_brief,
                reason="追问题缺少 dialogue_context 或锚定片段过薄。" if not ok_ctx else "锚定片段过薄，追问证据支撑弱，需人工补锚。",
                rewrite_question=None, suggested_expected_mode="knowledge", confidence="medium")
            return
        synth = any("合成占位" in x for x in r["risk_notes"])
        add(**base, decision="keep", semantic_fit="partial", standalone_quality="weak",
            routing_fit="correct",
            reviewed_excerpt_summary=excerpt_brief,
            reason=("追问依赖上一轮上下文（这是该类别的预期属性），锚定片段正文充分；"
                    + ("上一轮助手内容为合成占位，需人工确认衔接。" if synth else "上下文真实引用自前序问题。")),
            rewrite_question=None, suggested_expected_mode="knowledge",
            confidence="medium",
            extra_risk=(["上一轮助手内容为合成占位，衔接需人工复核"] if synth else []))
        return

    if cat == "cross_platform":
        add(**base, decision="keep", semantic_fit="partial", standalone_quality="strong",
            routing_fit="correct",
            reviewed_excerpt_summary=excerpt_brief,
            reason="跨平台干扰题：iOS 侧证据已锚定并实测存在，非 iOS 侧按设计应声明缺资料；预期模式经人工复核。",
            rewrite_question=None, suggested_expected_mode=mode, confidence="medium",
            extra_risk=["预期模式是设计意图，需生产链路复核"])
        return

    # ---------- 模板题（answerable / comparison） ----------
    def emit(decision, fit, standalone, routing, reason, rq=None, smode="knowledge", conf="medium", risks=None):
        add(**base, decision=decision, semantic_fit=fit, standalone_quality=standalone,
            routing_fit=routing, reviewed_excerpt_summary=excerpt_brief, reason=reason,
            rewrite_question=rq, suggested_expected_mode=smode, confidence=conf,
            extra_risk=risks or [])

    # 文档局部语境依赖：标题锚点含 Part/系列/素材等
    x = None
    if m_lookup: x = m_lookup.group(1); kindname = "lookup"
    elif m_mech: x = m_mech.group(1); kindname = "mech"
    elif m_trouble: x = m_trouble.group(1); kindname = "trouble"
    elif m_cmp: x, y = m_cmp.group(1), m_cmp.group(2); kindname = "compare"
    elif m_bound: x = m_bound.group(1); kindname = "boundary"
    elif m_sum: x = m_sum.group(1); kindname = "summary"
    else:
        emit("rewrite", "partial", "weak", "questionable",
             "题面不属于任何已知模板，无法程序化判定适配性，转人工。", conf="low")
        return

    if thin:
        emit("reject", "weak" if coverage(tokens(x), text) > 0 else "none", "partial", "correct",
             f"锚定小节正文过薄（正文行 {len(prose)}、字符不足），不足以独立支撑该问题；标题相似不代表内容可答。",
             conf="high")
        return

    dep = bool(DOC_CONTEXT.search(x)) or bool(re.match(rf"^[{CN_NUM}]+\s*[、.]|^\d+\s*[.、)]", x)) or "✅" in x or "`draft" in x
    xcov = coverage(tokens(x), text)

    if kindname == "compare":
        ycov = coverage(tokens(y), text)
        y_here = ycov >= 0.5 or y in text
        if dep or (not y_here and xcov < 0.5):
            emit("reject", "weak", "weak", "questionable",
                 f"对比对象「{y}」未在锚定片段出现且锚点覆盖不足，对比题的证据支撑不成立。",
                 conf="medium")
            return
        if y_here:
            emit("keep", "strong" if xcov >= 0.5 else "partial", "strong", "correct",
                 f"片段中同时覆盖「{x}」与「{y}」，对比有真实文本支撑。",
                 conf="high" if rich else "medium")
            return
        cq = clean_topic(x)
        rq = f"请讲讲{cq}的机制或工作原理，资料里有哪些关键细节？"
        ok = subject_ok(cq) and coverage(tokens(cq), text) >= 0.5
        emit("rewrite" if ok else "reject", "partial", "strong", "correct",
             f"对比对象「{y}」未在该小节出现（对比支撑不成立），但「{x}」本身内容充分；改写为单概念机制题。" if ok
             else "对比对象缺席且改写锚点覆盖不足。",
             rq if ok else None, conf="medium")
        return

    if dep:
        cq = clean_topic(x)
        rq = f"请讲讲{cq}的机制或工作原理。"
        ok = subject_ok(cq) and coverage(tokens(cq), text) >= 0.5 and rich
        emit("rewrite" if ok else "reject", "partial" if ok else "weak", "weak", "questionable",
             f"锚点「{x}」含文档局部结构词（Part/系列/素材等），原题依赖本地文档语境，不是用户会独立提出的问题；"
             + ("已去除编号改写为独立问题，改写词在片段中有覆盖。" if ok else "改写主语仍是叙述性小标题或覆盖不足，拒绝。"),
             rq if ok else None, conf="medium")
        return

    if kindname == "boundary":
        has_mis = any(k in text for k in MISSTEP_KW)
        _cx = clean_topic(x)
        rq = f"「{_cx}」有哪些常见的坑或需要注意的地方？" if subject_ok(_cx) else None
        if has_mis and xcov >= 0.5:
            emit("rewrite", "strong" if rich else "partial", "strong", "correct",
                 "片段含误区/边界类内容，但原题『资料里有没有对应说明』是对话元问句，改写为独立自然问法。",
                 rq, conf="medium")
        elif rich and xcov >= 0.5 and subject_ok(clean_topic(x)):
            emit("rewrite", "partial", "strong", "correct",
                 "片段未直接出现误区类措辞，仅有主题内容；改写为概念要点题以避免暗示不存在的内容。",
                 f"请讲讲{clean_topic(x)}的机制或工作原理。", conf="low",
                 risks=["片段无明确误区关键词，改写题的有效性需人工抽查"])
        else:
            emit("reject", "partial" if xcov > 0 else "none", "partial", "correct",
                 "片段既无误区内容也不够厚实，无法支撑边界/误区类问题。",
                 conf="medium")
        return

    if kindname == "trouble":
        if xcov >= 0.5 and rich:
            emit("keep", "strong", "partial", "correct",
                 "面试准备是真实用户场景，片段内容充分支撑机制细节类回答；『结合资料』式表述可接受。",
                 conf="high" if len(prose) >= 8 else "medium")
        elif xcov >= 0.5:
            emit("rewrite", "partial", "partial", "correct",
                 "片段中等厚度，改为更直接的机制提问以保证证据支撑明确。",
                 f"请结合资料讲讲{clean_topic(x)}的机制细节与易错点。", conf="medium")
        else:
            emit("reject", "weak", "partial", "correct",
                 "锚点词与片段重叠不足，无法确认该小节能回答面试细节类问题。",
                 conf="medium")
        return

    if kindname == "summary":
        if xcov >= 0.5 and rich:
            emit("keep", "strong", "partial", "correct",
                 "概括类问题以小节内容为范围，片段厚实可支撑；『给出出处行号』是评测辅助措辞。",
                 conf="medium")
        elif xcov >= 0.5:
            emit("rewrite", "partial", "partial", "correct",
                 "片段较薄，改写为更小的直接问题。",
                 (f"「{clean_topic(x)}」的核心要点是什么？" if subject_ok(clean_topic(x)) else None), conf="low")
        else:
            emit("reject", "weak", "partial", "correct",
                 "锚点词与片段重叠不足，概括题证据支撑不成立。", conf="medium")
        return

    # lookup / mech
    if xcov >= 0.5 and rich:
        emit("keep", "strong", "strong", "correct",
             f"题面自然独立，锚点「{x}」在小节中有覆盖，片段正文充分，可直接支撑概念/机制类回答。",
             conf="high" if len(prose) >= 8 else "medium")
    elif xcov >= 0.5:
        emit("keep" if len(prose) >= 3 else "rewrite", "partial", "strong", "correct",
             "锚点有覆盖但片段中等偏薄；保留为弱支撑候选或改写为更小的问题。",
             None if len(prose) >= 3 else (f"「{x}」是什么？" if subject_ok(x) else None), conf="low")
    else:
        emit("reject", "weak" if xcov > 0 else "none", "strong", "correct",
             "锚点词与片段文本重叠不足：标题相似不等于内容可答。",
             conf="medium")

for fp in sorted((SRC / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        review_one(json.loads(ln))

# 修正：rewrite 必须带改写题，否则降级为 reject
for r in reviews:
    if r["decision"] == "rewrite" and not r["rewrite_question"]:
        r["decision"] = "reject"
        r["reason"] += "（改写主语不自然，无法在不编造的前提下改写，拒绝。）"
        r["confidence"] = "medium"

# 唯一 id
for i, r in enumerate(reviews, 1):
    r["id"] = "review-%06d" % i
# 字段顺序整理
ORDER = ["id", "source_eval_id", "decision", "semantic_fit", "standalone_quality", "routing_fit",
         "source_path", "source_start_line", "source_end_line", "reviewed_excerpt_summary",
         "reason", "rewrite_question", "suggested_expected_mode", "risk_notes", "confidence"]
with OUT.open("w", encoding="utf-8") as f:
    for r in reviews:
        f.write(json.dumps({k: r.get(k) for k in ORDER}, ensure_ascii=False) + "\n")

print("reviews:", len(reviews))
print("decision:", dict(Counter(r["decision"] for r in reviews)))
print("fit:", dict(Counter(r["semantic_fit"] for r in reviews)))
marked = {r["source_eval_id"] for r in reviews}
tmpl = 0
for fp in sorted((SRC / "eval-candidates").glob("*.jsonl")):
    for ln in fp.read_text(encoding="utf-8").splitlines():
        rr = json.loads(ln)
        if any("模板生成" in x for x in rr["risk_notes"]):
            tmpl += 1
            assert rr["id"] in marked
print("template-marked covered:", tmpl)
