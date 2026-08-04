import subprocess
from fnmatch import fnmatch

from .chunker import code_chunks, markdown_chunks
from .config import ROOT, resolve_path

_CODE_SUFFIXES = {".h", ".m", ".mm", ".c", ".cpp", ".swift", ".s"}


def iter_source_files(source_cfg):
    base = resolve_path(source_cfg["path"])
    if not base.exists():
        return []
    excludes = source_cfg.get("exclude") or []
    found = set()
    for pattern in source_cfg.get("include", ["**/*"]):
        for p in base.glob(pattern):
            if not p.is_file():
                continue
            rel = p.relative_to(base)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if any(fnmatch(rel.as_posix(), pat) for pat in excludes):
                continue
            if not _content_allowed(source_cfg, rel, p):
                continue
            found.add(p)
    return sorted(found)


def _content_allowed(source_cfg, relative_path, path):
    """Apply an optional conservative domain filter to selected source files."""
    rule = source_cfg.get("content_filter") or {}
    globs = rule.get("globs") or []
    relative = relative_path.as_posix()
    if not rule or (globs and not any(fnmatch(relative, glob) for glob in globs)):
        return True

    searchable = f"{relative}\n{_read(path)[:12000]}".lower()
    if any(str(term).lower() in searchable for term in rule.get("exclude_any") or []):
        return False
    required = [str(term).lower() for term in rule.get("include_any") or []]
    return not required or any(term in searchable for term in required)


def file_chunks(source_cfg, path, chunking_cfg):
    base = resolve_path(source_cfg["path"])
    rel = path.relative_to(base).as_posix()
    ftype = source_cfg["type"]
    for prefix, t in (source_cfg.get("type_overrides") or {}).items():
        if rel.startswith(prefix):
            ftype = t
            break

    suffix = path.suffix.lower()
    display = str(path.resolve())
    if suffix == ".md":
        chunks = markdown_chunks(_read(path), chunking_cfg["max_chars"])
    elif suffix == ".docx":
        conv = _convert_docx(source_cfg["name"], base, path)
        if conv is None:
            return display, []
        display = str(conv.resolve())
        chunks = markdown_chunks(_read(conv), chunking_cfg["max_chars"])
    elif suffix in _CODE_SUFFIXES:
        chunks = code_chunks(
            _read(path), chunking_cfg["code_max_lines"], chunking_cfg["code_min_lines"]
        )
    else:
        return display, []

    for c in chunks:
        c["source"] = source_cfg["name"]
        c["type"] = ftype
        c["file_path"] = display
    return display, chunks


def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _convert_docx(source_name, base, path):
    out = ROOT / "data" / "converted" / source_name / path.relative_to(base).with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.stat().st_mtime < path.stat().st_mtime:
        try:
            subprocess.run(
                ["pandoc", "-f", "docx", "-t", "gfm", "--wrap=none", "-o", str(out), str(path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"警告：pandoc 转换失败，跳过 {path}: {e}")
            return None
    return out
