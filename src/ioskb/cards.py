import copy
from datetime import datetime

from .config import resolve_path
from .llm import chat, get_client
from .qa import build_context
from .retrieve import search

CARD_SYSTEM_PROMPT = """你是一名 iOS 底层知识的总结者，为学习者 TommyWu 生成"专题知识卡片"。
卡片是把多个来源（个人笔记、Apple 官方文档、WWDC 逐字稿、博客、objc4 等源码）交叉消化后的复习材料，
读者会用它做系统复习和面试准备。

要求：
1. 内容只能来自提供的编号材料，每个论点标注来源编号 [n]；材料没讲到的不要写，宁缺毋滥。
2. 多个来源互相印证时合并表述并同时标注；说法冲突时明确指出冲突双方及编号。
3. 准确性优先于覆盖面；术语用行业标准中文说法，首次出现附英文原词。
4. 输出为 Markdown，严格使用给定的章节结构，不加多余前后缀。"""


def _card_prompt(name, context):
    return (
        f"主题：{name}\n\n以下是知识库中与该主题相关的材料：\n\n<materials>\n{context}\n</materials>\n\n"
        f"请严格按以下结构生成知识卡片：\n"
        f"# {name}\n"
        f"## 一句话总结\n"
        f"## 核心原理\n"
        f"## 关键细节与易错点\n"
        f"## 高频追问\n（面试中围绕该主题的典型追问及基于材料的回答要点）\n"
        f"## 来源索引\n（只列出正文实际引用过的编号，每行：[n] 文件路径 › 标题路径）"
    )


def generate_cards(cfg, con, embedder, topics=None, provider=None):
    all_topics = cfg["cards"]["topics"]
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

    for topic in all_topics:
        name = topic["name"]
        queries = topic["queries"]
        print(f"[{name}] 检索材料（{len(queries)} 个查询）...")
        q_cfg = copy.deepcopy(cfg)
        q_cfg["retrieval"]["final_top"] = per_topic // len(queries) + 4

        seen, chunks = set(), []
        for q in queries:
            for c in search(con, q_cfg, q, embedder):
                key = c.get("id") or (c["file_path"], c["start_line"])
                if key not in seen:
                    seen.add(key)
                    chunks.append(c)
        chunks = chunks[:per_topic]
        if not chunks:
            print(f"[{name}] 没检索到材料，跳过。")
            continue

        print(f"[{name}] {len(chunks)} 块材料，调用 {provider_name} 生成卡片...")
        messages = [
            {"role": "system", "content": CARD_SYSTEM_PROMPT},
            {"role": "user", "content": _card_prompt(name, build_context(chunks))},
        ]
        content = chat(client, model, messages)

        front = (
            f"---\ntopic: {name}\n"
            f"generated_at: {datetime.now().isoformat(timespec='seconds')}\n"
            f"provider: {provider_name}\n---\n\n"
        )
        out_path = out_dir / f"{name}.md"
        out_path.write_text(front + content.strip() + "\n", encoding="utf-8")
        print(f"[{name}] 已写入 {out_path}")

    print("卡片生成完毕。提醒：运行 `ioskb index --source knowledge-cards` 可把新卡片纳入索引。")
