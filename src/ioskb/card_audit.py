"""知识卡片的机械审计：结构、引用编号、原始路径和行号边界。"""

import re
from pathlib import Path

from .cards import REQUIRED_HEADINGS, UNSUPPORTED_MARKERS
from .config import resolve_path

INDEX_HEADING = "## 原始资料索引"
INDEX_LINE = re.compile(r"^\[(\d+)\] (.+?) › .+（第(\d+)-(\d+)行）$")
INLINE_REF = re.compile(r"(?<!\!)\[(\d+)\]")


def audit_cards(cfg):
    root = resolve_path(cfg["cards"]["output_dir"])
    errors = []
    checked = 0
    line_counts = {}

    for path in sorted(root.rglob("*.md")):
        checked += 1
        text = path.read_text(encoding="utf-8")
        if INDEX_HEADING not in text:
            errors.append(f"{path}: 缺少原始资料索引")
            continue
        body, index_text = text.split(INDEX_HEADING, 1)
        missing = [heading for heading in REQUIRED_HEADINGS if heading not in body]
        if missing:
            errors.append(f"{path}: 缺少章节 {'、'.join(missing)}")
        for marker in UNSUPPORTED_MARKERS:
            if marker in body:
                errors.append(f"{path}: 包含未获材料支持的推断标记 {marker}")

        body_refs = {int(n) for n in INLINE_REF.findall(body)}
        index_entries = {}
        for line in index_text.splitlines():
            if not line.startswith("["):
                continue
            match = INDEX_LINE.match(line)
            if not match:
                errors.append(f"{path}: 无法解析来源行 {line}")
                continue
            n, raw_path, start, end = match.groups()
            n, start, end = int(n), int(start), int(end)
            index_entries[n] = (raw_path, start, end)
            source_path = Path(raw_path)
            if not source_path.is_absolute() or not source_path.exists():
                errors.append(f"{path}: 原始路径不存在 {raw_path}")
                continue
            if source_path.is_relative_to(root):
                errors.append(f"{path}: 来源错误地指向知识卡片 {raw_path}")
            if start < 1 or end < start:
                errors.append(f"{path}: 非法行号 {start}-{end}")
                continue
            if source_path.suffix.lower() in {".md", ".h", ".m", ".mm", ".c", ".cpp", ".swift", ".s"}:
                if source_path not in line_counts:
                    with open(source_path, encoding="utf-8", errors="replace") as f:
                        line_counts[source_path] = sum(1 for _ in f)
                if end > line_counts[source_path]:
                    errors.append(
                        f"{path}: 行号超出原文件 {raw_path} "
                        f"{end}>{line_counts[source_path]}"
                    )

        if not body_refs:
            errors.append(f"{path}: 正文没有来源编号")
        missing_entries = sorted(body_refs - set(index_entries))
        extra_entries = sorted(set(index_entries) - body_refs)
        if missing_entries:
            errors.append(f"{path}: 正文编号缺少索引 {missing_entries}")
        if extra_entries:
            errors.append(f"{path}: 索引含未使用编号 {extra_entries}")

    return checked, errors
