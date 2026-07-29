import copy
import json
import re
from datetime import datetime

from .config import resolve_path
from .llm import chat_with_usage, get_client
from .qa import build_context
from .retrieve import search

CARD_SYSTEM_PROMPT = """你是一名 iOS 底层知识的总结者，为学习者 TommyWu 生成"专题知识卡片"。
卡片是把多个来源（个人笔记、Apple 官方文档、WWDC 逐字稿、博客、objc4 等源码）交叉消化后的复习材料，
读者会用它做系统复习和面试准备。

要求：
1. 内容只能来自提供的编号材料，每个论点标注来源编号 [n]；材料没讲到的不要写，宁缺毋滥。
2. 多个来源互相印证时合并表述并同时标注；说法冲突时明确指出冲突双方及编号。
3. 准确性优先于覆盖面；术语用行业标准中文说法，首次出现附英文原词。
4. 输出为 Markdown，严格使用给定的章节结构，不加多余前后缀。
5. 不要自行编写来源索引；程序会根据正文实际使用的编号附加原始文件、标题和行号。
6. 禁止写“合理推断”、经验补充或模型常识。某个追问没有材料直接支持时，明确写“本卡片材料不足”，不要猜测回答。"""

REQUIRED_HEADINGS = (
    "## 一句话总结",
    "## 核心原理",
    "## 关键细节与易错点",
    "## 高频追问",
)
UNSUPPORTED_MARKERS = ("合理推断", "根据常识", "材料中未直接解释，但")


def _card_prompt(name, context):
    return (
        f"主题：{name}\n\n以下是知识库中与该主题相关的材料：\n\n<materials>\n{context}\n</materials>\n\n"
        f"请严格按以下结构生成知识卡片：\n"
        f"# {name}\n"
        f"## 一句话总结\n"
        f"## 核心原理\n"
        f"## 关键细节与易错点\n"
        f"## 高频追问\n（面试中围绕该主题的典型追问及基于材料的回答要点）"
    )


def load_card_topics(cfg):
    cards_cfg = cfg["cards"]
    if cards_cfg.get("topics_file"):
        import yaml

        path = resolve_path(cards_cfg["topics_file"])
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("topics", [])
    return cards_cfg.get("topics", [])


def _source_index(content, chunks):
    refs = sorted({int(n) for n in re.findall(r"(?<!\!)\[(\d+)\]", content)})
    invalid = [n for n in refs if n < 1 or n > len(chunks)]
    if invalid:
        raise ValueError(f"正文引用了不存在的来源编号：{invalid}")
    if not refs:
        raise ValueError("正文没有任何 [n] 原始来源引用")
    lines = ["## 原始资料索引", ""]
    for n in refs:
        c = chunks[n - 1]
        title = c["title_path"] or "(全文)"
        lines.append(
            f"[{n}] {c['file_path']} › {title}"
            f"（第{c['start_line']}-{c['end_line']}行）"
        )
    return "\n".join(lines)


def _validate_card(content, chunks):
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in content]
    if missing:
        raise ValueError(f"缺少固定章节：{'、'.join(missing)}")
    unsupported = [marker for marker in UNSUPPORTED_MARKERS if marker in content]
    if unsupported:
        raise ValueError(f"包含未获材料支持的推断标记：{'、'.join(unsupported)}")
    return _source_index(content, chunks)


def _write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def generate_cards(cfg, con, embedder, topics=None, provider=None, overwrite=False):
    all_topics = load_card_topics(cfg)
    if topics:
        wanted = set(topics)
        all_topics = [t for t in all_topics if t["name"] in wanted]
        missing = wanted - {t["name"] for t in all_topics}
        if missing:
            print(f"警告：config.yaml 的 cards.topics 中找不到主题：{'、'.join(sorted(missing))}")
    if not all_topics:
        print("没有要生成的主题。")
        return

    per_topic = cfg["cards"]["chunks_per_topic"]
    out_dir = resolve_path(cfg["cards"]["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    client, model = get_client(cfg, provider)
    provider_name = provider or cfg["llm"]["provider"]
    report_path = out_dir / "_generation_report.json"
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provider": provider_name,
        "model": model,
        "cards": [],
        "totals": {},
    }

    for topic in all_topics:
        name = topic["name"]
        group = topic.get("group", "未分类")
        queries = topic["queries"]
        group_dir = out_dir / group
        group_dir.mkdir(parents=True, exist_ok=True)
        out_path = group_dir / f"{name}.md"
        if out_path.exists() and not overwrite:
            print(f"[{name}] 已存在，跳过（使用 --force 可重新生成）。")
            report["cards"].append({"topic": name, "group": group, "status": "skipped"})
            continue

        print(f"[{name}] 检索材料（{len(queries)} 个查询）...")
        q_cfg = copy.deepcopy(cfg)
        q_cfg["retrieval"]["final_top"] = per_topic // len(queries) + 4

        seen, chunks = set(), []
        for q in queries:
            for c in search(con, q_cfg, q, embedder, exclude_types={"card"}):
                key = c.get("id") or (c["file_path"], c["start_line"])
                if key not in seen:
                    seen.add(key)
                    chunks.append(c)
        chunks = chunks[:per_topic]
        if not chunks:
            print(f"[{name}] 没检索到材料，跳过。")
            report["cards"].append(
                {"topic": name, "group": group, "status": "no_materials"}
            )
            continue

        print(f"[{name}] {len(chunks)} 块材料，调用 {provider_name} 生成卡片...")
        messages = [
            {"role": "system", "content": CARD_SYSTEM_PROMPT},
            {"role": "user", "content": _card_prompt(name, build_context(chunks))},
        ]
        total_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
        }
        error = None
        for attempt in range(1, 3):
            try:
                content, usage = chat_with_usage(client, model, messages)
                for key, value in usage.items():
                    total_usage[key] += value
                provenance = _validate_card(content, chunks)
                error = None
                break
            except Exception as e:
                error = e
                if attempt == 1:
                    print(f"[{name}] 首次结果未通过校验，自动重试：{e}")
                    messages[-1]["content"] += (
                        "\n\n上一次结果未通过程序校验。请特别确保固定章节完整、"
                        "所有事实都有材料直接支持，绝不写合理推断。"
                    )
        if error is not None:
            e = error
            print(f"[{name}] 生成失败：{e}")
            report["cards"].append(
                {
                    "topic": name,
                    "group": group,
                    "status": "error",
                    "error": str(e),
                    **total_usage,
                }
            )
            _write_json(report_path, report)
            continue

        front = (
            f"---\ntopic: {name}\n"
            f"group: {group}\n"
            f"generated_at: {datetime.now().isoformat(timespec='seconds')}\n"
            f"provider: {provider_name}\n---\n\n"
        )
        card_text = front + content.strip() + "\n\n" + provenance + "\n"
        tmp_path = out_path.with_suffix(".md.tmp")
        tmp_path.write_text(card_text, encoding="utf-8")
        tmp_path.replace(out_path)
        entry = {
            "topic": name,
            "group": group,
            "status": "generated",
            "path": str(out_path),
            "materials": len(chunks),
            **total_usage,
        }
        report["cards"].append(entry)
        _write_json(report_path, report)
        print(
            f"[{name}] 已写入 {out_path}；"
            f"token={total_usage['total_tokens']} "
            f"（输入 {total_usage['prompt_tokens']} / 输出 {total_usage['completion_tokens']}）"
        )

    generated = [c for c in report["cards"] if c["status"] == "generated"]
    report["totals"] = {
        "generated": len(generated),
        "skipped": sum(c["status"] == "skipped" for c in report["cards"]),
        "errors": sum(c["status"] == "error" for c in report["cards"]),
        "prompt_tokens": sum(c.get("prompt_tokens", 0) for c in generated),
        "completion_tokens": sum(c.get("completion_tokens", 0) for c in generated),
        "total_tokens": sum(c.get("total_tokens", 0) for c in generated),
    }
    _write_json(report_path, report)
    totals = report["totals"]
    print(
        "卡片生成完毕："
        f"{totals['generated']} 张成功，{totals['skipped']} 张跳过，"
        f"{totals['errors']} 张失败，实际 token={totals['total_tokens']}。"
    )
    print("提醒：运行 `ioskb index --source knowledge-cards` 可把新卡片纳入索引。")
