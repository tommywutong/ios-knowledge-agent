import re

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_OBJC_SIG = re.compile(r"^[-+]\s*\(")
_C_SIG = re.compile(r"^[A-Za-z_].*\)\s*\{?\s*$")


def markdown_chunks(text, max_chars):
    lines = text.split("\n")
    sections = []
    stack = []
    in_fence = False
    sec_start = 0
    cur_title = ""

    def close(end_idx):
        while end_idx >= sec_start and not lines[end_idx].strip():
            end_idx -= 1
        if end_idx >= sec_start:
            sections.append((sec_start, end_idx, cur_title))

    for idx, line in enumerate(lines):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING.match(line)
        if m:
            close(idx - 1)
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2).strip()))
            cur_title = " › ".join(t for _, t in stack)
            sec_start = idx
    close(len(lines) - 1)

    chunks = []
    for s, e, title in sections:
        seg = lines[s : e + 1]
        seg_text = "\n".join(seg)
        if not seg_text.strip():
            continue
        if len(seg_text) <= max_chars:
            chunks.append(
                {"title_path": title, "start_line": s + 1, "end_line": e + 1, "text": seg_text}
            )
        else:
            for gs, ge in _pack_paragraphs(seg, max_chars):
                sub = "\n".join(seg[gs : ge + 1])
                if not sub.strip():
                    continue
                if len(sub) <= max_chars:
                    chunks.append(
                        {
                            "title_path": title,
                            "start_line": s + gs + 1,
                            "end_line": s + ge + 1,
                            "text": sub,
                        }
                    )
                    continue
                # Imported documents can contain either one enormous physical
                # line (common in WWDC transcripts) or enough blank lines that
                # paragraph grouping's size estimate crosses the hard limit.
                # Repack the exact line range as a final, lossless guard.
                for ps, pe, piece in _split_line_range(seg, gs, ge, max_chars):
                    if not piece.strip():
                        continue
                    chunks.append(
                        {
                            "title_path": title,
                            "start_line": s + ps + 1,
                            "end_line": s + pe + 1,
                            "text": piece,
                        }
                    )
    return chunks


def _split_line_range(lines, start, end, max_chars):
    """Repack a line range so every returned text is within max_chars."""
    groups = []
    current = []
    current_start = None
    current_size = 0

    def flush(last_idx):
        nonlocal current, current_start, current_size
        if current:
            groups.append((current_start, last_idx, "\n".join(current)))
        current = []
        current_start = None
        current_size = 0

    for idx in range(start, end + 1):
        line = lines[idx]
        if len(line) > max_chars:
            flush(idx - 1)
            groups.extend((idx, idx, piece) for piece in _split_long_line(line, max_chars))
            continue
        added = len(line) + (1 if current else 0)
        if current and current_size + added > max_chars:
            flush(idx - 1)
            added = len(line)
        if current_start is None:
            current_start = idx
        current.append(line)
        current_size += added
    flush(end)
    return groups


def _split_long_line(line, max_chars):
    """Split one physical line without dropping text or exceeding max_chars."""
    pieces = []
    start = 0
    while start < len(line):
        stop = min(start + max_chars, len(line))
        if stop < len(line):
            # Prefer a natural boundary in the latter half of the window. Keep
            # the boundary character so concatenating pieces reproduces input.
            floor = start + max_chars // 2
            candidates = []
            for mark in ("。", "！", "？", ". ", "! ", "? ", "; ", "；", " "):
                pos = line.rfind(mark, floor, stop)
                if pos >= floor and pos + len(mark) <= stop:
                    candidates.append(pos + len(mark))
            natural = max(candidates, default=-1)
            if natural > start:
                stop = natural
        piece = line[start:stop]
        if piece:
            pieces.append(piece)
        start = stop
    return pieces


def _pack_paragraphs(lines, max_chars):
    paras = []
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].strip():
            i += 1
            continue
        start = i
        in_fence = False
        while i < n:
            if _FENCE.match(lines[i]):
                in_fence = not in_fence
            if not lines[i].strip() and not in_fence:
                break
            i += 1
        paras.append((start, i - 1))

    groups = []
    cur = None  # [start, end, size]
    for s, e in paras:
        size = sum(len(lines[j]) + 1 for j in range(s, e + 1))
        if size > max_chars:
            if cur:
                groups.append((cur[0], cur[1]))
                cur = None
            hs, hsize = s, 0
            for j in range(s, e + 1):
                hsize += len(lines[j]) + 1
                if hsize > max_chars and j > hs:
                    groups.append((hs, j - 1))
                    hs, hsize = j, len(lines[j]) + 1
            groups.append((hs, e))
            continue
        if cur and cur[2] + size > max_chars:
            groups.append((cur[0], cur[1]))
            cur = None
        if cur is None:
            cur = [s, e, size]
        else:
            cur[1], cur[2] = e, cur[2] + size
    if cur:
        groups.append((cur[0], cur[1]))
    return groups


def code_chunks(text, max_lines, min_lines):
    lines = text.split("\n")
    chunks = []

    def flush(start, end):
        seg = lines[start : end + 1]
        seg_text = "\n".join(seg)
        if not seg_text.strip():
            return
        title = ""
        for l in seg:
            if _OBJC_SIG.match(l) or _C_SIG.match(l):
                title = l.strip()[:80]
                break
        chunks.append(
            {"title_path": title, "start_line": start + 1, "end_line": end + 1, "text": seg_text}
        )

    start, count = 0, 0
    for idx, line in enumerate(lines):
        is_sig = bool(_OBJC_SIG.match(line) or _C_SIG.match(line))
        if count >= max_lines or (is_sig and count >= min_lines):
            if idx > start:
                flush(start, idx - 1)
            start, count = idx, 0
        count += 1
    if start < len(lines):
        flush(start, len(lines) - 1)
    return chunks
