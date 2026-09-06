#!/usr/bin/env python3
"""只读构建语料标题索引：obsidian + tips + 面试文章的 md 标题（层级/文本/行号）。"""
import json, re
from pathlib import Path

ROOT = Path("/Users/tommywu/Desktop/iOS知识agentt")
OUT = ROOT / "data/glm/overnight-rag-evaluation-20260906/tools/corpus_index.json"

DIRS = [
    ("/Users/tommywu/Obsidian/iOS/20 专题笔记", "obsidian-ios"),
    ("/Users/tommywu/Desktop/26暑期内容/tips-master/sources", "summer2026"),
    ("/Users/tommywu/Desktop/26暑期内容/awesome-ios-interview-main/articles/ios-advanced", "summer2026"),
]
heading_re = re.compile(r"^(#{1,4})\s+(.+?)\s*$")

files = []
for d, source in DIRS:
    for p in sorted(Path(d).rglob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.split("\n")
        headings = []
        fence = False
        for i, ln in enumerate(lines, 1):
            if ln.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            m = heading_re.match(ln)
            if m:
                headings.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": i})
        files.append({
            "path": str(p), "source": source, "nlines": len(lines),
            "headings": headings,
        })

OUT.write_text(json.dumps(files, ensure_ascii=False, indent=0), encoding="utf-8")
n_head = sum(len(f["headings"]) for f in files)
print(f"files: {len(files)}, headings: {n_head}")
for f in files[:5]:
    print(f["path"], len(f["headings"]))
