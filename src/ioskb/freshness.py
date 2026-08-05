"""Read-only corpus freshness inspection and safe local sync helpers."""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ROOT, resolve_path
from .ingest import iter_source_files


@dataclass(frozen=True)
class FileChange:
    source: str
    status: str
    path: str


@dataclass(frozen=True)
class UpstreamStatus:
    path: str
    status: str
    local_head: str | None = None
    remote_head: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class FreshnessReport:
    changes: tuple[FileChange, ...]
    upstreams: tuple[UpstreamStatus, ...]

    @property
    def added(self) -> int:
        return sum(change.status == "added" for change in self.changes)

    @property
    def modified(self) -> int:
        return sum(change.status == "modified" for change in self.changes)

    @property
    def deleted(self) -> int:
        return sum(change.status == "deleted" for change in self.changes)

    @property
    def unavailable(self) -> int:
        return sum(change.status == "unavailable" for change in self.changes)

    @property
    def clean(self) -> bool:
        return not self.changes and all(item.status == "up_to_date" for item in self.upstreams)

    def as_dict(self) -> dict:
        return {
            "clean": self.clean,
            "counts": {
                "added": self.added,
                "modified": self.modified,
                "deleted": self.deleted,
                "unavailable": self.unavailable,
            },
            "changes": [asdict(change) for change in self.changes],
            "upstreams": [asdict(upstream) for upstream in self.upstreams],
        }


def open_readonly_db(cfg: dict) -> sqlite3.Connection:
    """Open the existing index in SQLite read-only/query-only mode."""
    path = resolve_path(cfg["db_path"])
    if not path.is_file():
        raise SystemExit(f"本地索引不存在：{path}，请先运行 ioskb index。")
    con = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    return con


def indexed_path_for(source_cfg: dict, source_path: Path) -> str:
    """Return the database key used by ``file_chunks`` without converting DOCX."""
    if source_path.suffix.lower() != ".docx":
        return str(source_path.resolve())
    base = resolve_path(source_cfg["path"])
    converted = (
        ROOT
        / "data"
        / "converted"
        / source_cfg["name"]
        / source_path.relative_to(base).with_suffix(".md")
    )
    return str(converted.resolve())


def inspect_sources(cfg: dict, con, source_names: set[str] | None = None) -> tuple[FileChange, ...]:
    """Compare source bytes with stored hashes without chunking or loading embeddings."""
    changes: list[FileChange] = []
    selected = [
        source
        for source in cfg["sources"]
        if source_names is None or source["name"] in source_names
    ]
    for source in selected:
        name = source["name"]
        base = resolve_path(source["path"])
        if not base.exists():
            # A missing source root is not treated as mass deletion. Indexing follows
            # the same safety rule; freshness still makes the unavailable path visible.
            changes.append(FileChange(name, "unavailable", str(base)))
            continue
        disk_keys: set[str] = set()
        for path in iter_source_files(source):
            key = indexed_path_for(source, path)
            disk_keys.add(key)
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                changes.append(FileChange(name, "unavailable", str(path.resolve())))
                continue
            row = con.execute("SELECT hash FROM files WHERE path = ?", (key,)).fetchone()
            if row is None:
                changes.append(FileChange(name, "added", str(path.resolve())))
            elif row[0] != digest:
                changes.append(FileChange(name, "modified", str(path.resolve())))

        indexed = {
            row[0]
            for row in con.execute("SELECT path FROM files WHERE source = ?", (name,))
        }
        for path in sorted(indexed - disk_keys):
            changes.append(FileChange(name, "deleted", path))
    return tuple(sorted(changes, key=lambda item: (item.source, item.status, item.path)))


def discover_upstream_repositories(
    cfg: dict, source_names: set[str] | None = None
) -> tuple[Path, ...]:
    """Find distinct configured source roots that are Git repositories."""
    repositories = {
        base.resolve()
        for source in cfg["sources"]
        if source_names is None or source["name"] in source_names
        if (base := resolve_path(source["path"])).is_dir() and (base / ".git").exists()
    }
    return tuple(sorted(repositories))


def _git(repo: Path, *args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def inspect_upstream(repo: Path) -> UpstreamStatus:
    """Compare local HEAD with origin's HEAD without fetch/pull or local ref writes."""
    try:
        local = _git(repo, "rev-parse", "HEAD")
    except subprocess.TimeoutExpired:
        return UpstreamStatus(str(repo), "unavailable", detail="检查本地 HEAD 超时")
    if local.returncode:
        return UpstreamStatus(str(repo), "unavailable", detail="无法读取本地 HEAD")
    local_head = local.stdout.strip()
    try:
        remote = _git(repo, "ls-remote", "origin", "HEAD")
    except subprocess.TimeoutExpired:
        return UpstreamStatus(
            str(repo), "unavailable", local_head=local_head, detail="检查远端超时"
        )
    if remote.returncode or not remote.stdout.strip():
        return UpstreamStatus(
            str(repo), "unavailable", local_head=local_head, detail="无法访问 origin/HEAD"
        )
    remote_head = remote.stdout.split()[0]
    status = "up_to_date" if local_head == remote_head else "update_available"
    return UpstreamStatus(str(repo), status, local_head=local_head, remote_head=remote_head)


def inspect_freshness(
    cfg: dict,
    con,
    *,
    source_names: set[str] | None = None,
    check_upstreams: bool = True,
) -> FreshnessReport:
    changes = inspect_sources(cfg, con, source_names)
    upstreams = ()
    if check_upstreams:
        upstreams = tuple(
            inspect_upstream(repo)
            for repo in discover_upstream_repositories(cfg, source_names)
        )
    return FreshnessReport(changes=changes, upstreams=upstreams)


def pull_upstream(repo: Path) -> None:
    """Fast-forward a clean mirror repository, refusing ambiguous local state."""
    try:
        dirty = _git(repo, "status", "--porcelain")
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"检查上游镜像超时：{repo}") from exc
    if dirty.returncode or dirty.stdout.strip():
        raise RuntimeError(f"上游镜像存在本地改动，拒绝拉取：{repo}")
    try:
        result = _git(repo, "pull", "--ff-only", timeout=180)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"上游镜像拉取超时：{repo}") from exc
    if result.returncode:
        raise RuntimeError(f"上游镜像无法快进：{repo}")
