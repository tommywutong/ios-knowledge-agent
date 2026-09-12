"""Prepare, fetch, and verify long-running MiMo handoff branches.

The command deliberately keeps a MiMo branch separate from the checkout that
Codex is using.  It verifies a small, machine-readable run manifest before any
task-specific validator is run; it never merges, resets, or deletes a user's
worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "RUN_MANIFEST.json"
MANIFEST_DIGEST_NAME = "RUN_MANIFEST.sha256"
SCHEMA_VERSION = "mimo-handoff/v1"
RUN_STATES = {"RUNNING", "READY_FOR_CODEX", "PARTIAL", "BLOCKED", "FAILED", "DONE"}
TASK_STATES = {"READY_FOR_MIMO", "READY_FOR_CODEX", "DONE", "NEEDS_REWRITE", "BLOCKED"}
SAFE_RELATIVE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
SAFE_BATCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
SAFE_BRANCH = re.compile(r"^mimo/[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
SAFE_REMOTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,40}$")
SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@-]{0,200}$")
SENSITIVE_NAME = re.compile(r"(?:^|/)(?:\.env(?:\.|$)|.*(?:token|secret|credential|cookie|private[-_.]?key).*)$", re.I)
ALLOWED_SUFFIXES = {".json", ".jsonl", ".md", ".txt"}
# A new MiMo branch may carry its deterministic runner before it lands on the
# receiver's default branch. These files are accepted only when their remote
# blobs exactly match the receiver's already-loaded local copies.
BOOTSTRAP_PATHS = frozenset(
    {
        "scripts/mimo_handoff.py",
        "scripts/prepare_mimo_batch.py",
        "scripts/validate_mimo_batch.py",
        "tests/test_mimo_handoff.py",
        "tests/test_validate_mimo_batch.py",
    }
)
# A batch can be prepared and pushed before the receiving checkout has merged
# its first commit. These files are immutable input assets, not MiMo output.
# They may cross that initial Git boundary only if the receiver already has an
# identical trusted local copy.
STATIC_BATCH_FILENAMES = frozenset(
    {
        "BATCH_MANIFEST.json",
        "EXCLUDED_INPUTS.jsonl",
        "MIMO_PROMPT.txt",
        "SCHEMA.md",
    }
)
MANIFEST_FIELDS = {
    "schema_version",
    "batch_id",
    "branch",
    "base_ref",
    "base_ref_name",
    "pilot_dir",
    "queue_file",
    "state",
    "attempt",
    "prompt_version",
    "input_manifest_required",
    "started_at",
    "updated_at",
    "queue_sha256",
    "tasks",
    "allowed_mutations",
}
TASK_FIELDS = {"task_id", "status", "output", "output_sha256", "inputs"}
INPUT_FIELDS = {"path", "sha256"}
IMMUTABLE_MANIFEST_FIELDS = (
    "schema_version",
    "batch_id",
    "branch",
    "base_ref",
    "base_ref_name",
    "pilot_dir",
    "queue_file",
    "attempt",
    "prompt_version",
    "input_manifest_required",
    "started_at",
    "allowed_mutations",
)


class HandoffError(ValueError):
    """A user-fixable handoff contract error."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise HandoffError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def _run_git_bytes(*args: str, cwd: Path = ROOT) -> bytes:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise HandoffError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_object(payload: bytes, *, source: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise HandoffError(f"{source} must contain a JSON object")
    return value


def _relative_path(value: str, *, field: str, root: Path) -> Path:
    if not isinstance(value, str) or not value or not SAFE_RELATIVE.fullmatch(value):
        raise HandoffError(f"{field} must be a repository-relative path")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise HandoffError(f"{field} must not escape the repository")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise HandoffError(f"{field} must remain inside the repository") from exc
    return candidate


def _pilot_dir_from_manifest(manifest: dict[str, Any], root: Path) -> tuple[Path, str]:
    raw = manifest.get("pilot_dir")
    relative = _relative_path(raw, field="pilot_dir", root=root)
    if not str(relative).startswith("data/glm/"):
        raise HandoffError("pilot_dir must be under data/glm/")
    return root / relative, str(relative)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HandoffError(f"missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise HandoffError(f"invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise HandoffError(f"{path} must contain a JSON object")
    return value


def _write_manifest(path: Path, manifest: dict[str, Any]) -> str:
    """Write manifest and its sidecar digest atomically."""
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    sidecar = path.with_name(MANIFEST_DIGEST_NAME)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(f"{digest}  {MANIFEST_NAME}\n")
        temporary_digest = Path(handle.name)
    os.replace(temporary_digest, sidecar)
    return digest


def _verify_manifest_digest(path: Path) -> str:
    sidecar = path.with_name(MANIFEST_DIGEST_NAME)
    try:
        line = sidecar.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise HandoffError(f"missing manifest digest {sidecar}") from exc
    match = re.fullmatch(r"([0-9a-f]{64})\s+\*?RUN_MANIFEST\.json", line)
    if not match:
        raise HandoffError(f"invalid manifest digest file {sidecar}")
    actual = _sha256(path)
    if actual != match.group(1):
        raise HandoffError(f"manifest SHA mismatch (declared={match.group(1)}, actual={actual})")
    return actual


def _queue_statuses(queue_text: str) -> dict[str, str]:
    sections = _queue_sections(queue_text)
    statuses: dict[str, str] = {}
    for task_id, section in sections.items():
        matches = re.findall(r"(?m)^- status: `([^`]+)`\s*$", section)
        if len(matches) != 1:
            raise HandoffError(f"{task_id}: queue must contain exactly one status")
        if matches[0] not in TASK_STATES:
            raise HandoffError(f"{task_id}: invalid queue status {matches[0]!r}")
        statuses[task_id] = matches[0]
    return statuses


def _queue_sections(queue_text: str) -> dict[str, str]:
    sections = re.split(r"(?m)^## (task-[A-Za-z0-9._-]+)\s*$", queue_text)
    result: dict[str, str] = {}
    for index in range(1, len(sections), 2):
        task_id = sections[index]
        if task_id in result:
            raise HandoffError(f"duplicate queue task heading: {task_id}")
        result[task_id] = sections[index + 1]
    return result


def _queue_contract(queue_text: str) -> str:
    """Remove only mutable handoff metadata from the queue contract."""
    mutable = re.compile(r"^- (?:status|output_sha256|note|codex_note):")
    return "\n".join(
        line for line in queue_text.splitlines() if not mutable.match(line)
    ).rstrip() + "\n"


def _input_paths(section: str, *, pilot_dir: Path, root: Path) -> list[dict[str, str]]:
    line = re.search(r"(?m)^- input:\s*(.+)$", section)
    if not line:
        return []
    values = re.findall(r"`([^`]+)`", line.group(1))
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        candidate = Path(value)
        # Existing queue entries historically used both pilot-relative and
        # repository-relative paths. Canonicalize both to repository-relative.
        path = (pilot_dir / candidate) if (pilot_dir / candidate).is_file() else (root / candidate)
        if not path.is_file():
            raise HandoffError(f"input does not exist: {value}")
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError as exc:
            raise HandoffError(f"input escapes repository: {value}") from exc
        relative_text = str(relative)
        _relative_path(relative_text, field="input", root=root)
        if not relative_text.startswith("data/glm/") or SENSITIVE_NAME.search(relative_text):
            raise HandoffError(f"input must be a non-sensitive data/glm path: {relative_text}")
        if relative_text not in seen:
            seen.add(relative_text)
            result.append({"path": relative_text, "sha256": _sha256(resolved)})
    return result


def _ensure_manifest_task_inputs(manifest: dict[str, Any], *, root: Path) -> None:
    """Require immutable input hashes for all declared tasks."""
    for task in manifest.get("tasks", []):
        if not task.get("inputs"):
            raise HandoffError(f"{task['task_id']}: manifest must declare immutable inputs")


def _manifest_tasks(
    manifest: dict[str, Any], *, path_root: Path = ROOT, input_root: Path = ROOT
) -> list[dict[str, Any]]:
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise HandoffError("manifest tasks must be a non-empty array")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise HandoffError("each manifest task must be an object")
        unknown = set(task) - TASK_FIELDS
        if unknown:
            raise HandoffError(f"manifest task contains unknown fields: {sorted(unknown)}")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"task-[A-Za-z0-9._-]+", task_id):
            raise HandoffError("task_id must use the task-... form")
        if task_id in seen:
            raise HandoffError(f"duplicate manifest task {task_id}")
        seen.add(task_id)
        status = task.get("status")
        if status not in TASK_STATES:
            raise HandoffError(f"{task_id}: invalid task status")
        output = _relative_path(str(task.get("output", "")), field=f"{task_id}.output", root=path_root)
        if output.suffix.lower() not in ALLOWED_SUFFIXES or SENSITIVE_NAME.search(str(output)):
            raise HandoffError(f"{task_id}.output is not an allowed handoff file")
        inputs = task.get("inputs", [])
        if not isinstance(inputs, list):
            raise HandoffError(f"{task_id}.inputs must be an array")
        for item in inputs:
            if not isinstance(item, dict):
                raise HandoffError(f"{task_id}.inputs entries must be objects")
            unknown_input = set(item) - INPUT_FIELDS
            if unknown_input:
                raise HandoffError(
                    f"{task_id}.inputs entry contains unknown fields: {sorted(unknown_input)}"
                )
            input_path = item.get("path")
            _relative_path(str(input_path or ""), field=f"{task_id}.inputs.path", root=input_root)
            if not str(input_path).startswith("data/glm/") or SENSITIVE_NAME.search(str(input_path)):
                raise HandoffError(f"{task_id}.inputs.path must be under data/glm/")
            if not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
                raise HandoffError(f"{task_id}.inputs.sha256 must be 64 lowercase hex characters")
        item = dict(task)
        item["output"] = str(output)
        result.append(item)
    return result


def validate_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    unknown = set(manifest) - MANIFEST_FIELDS
    if unknown:
        raise HandoffError(f"manifest contains unknown fields: {sorted(unknown)}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise HandoffError(f"unsupported manifest schema: {manifest.get('schema_version')!r}")
    batch_id = manifest.get("batch_id")
    if not isinstance(batch_id, str) or not SAFE_BATCH.fullmatch(batch_id):
        raise HandoffError("batch_id contains unsafe characters")
    branch = manifest.get("branch")
    if not isinstance(branch, str) or not SAFE_BRANCH.fullmatch(branch):
        raise HandoffError("branch must use the dedicated mimo/<batch> namespace")
    state = manifest.get("state")
    if state not in RUN_STATES:
        raise HandoffError(f"invalid run state: {state!r}")
    attempt = manifest.get("attempt", 1)
    if not isinstance(attempt, int) or attempt < 1:
        raise HandoffError("attempt must be a positive integer")
    pilot_dir, pilot_relative = _pilot_dir_from_manifest(manifest, root)
    if pilot_relative.rstrip("/").split("/")[-1] != batch_id:
        raise HandoffError("batch_id must match the final pilot_dir component")
    queue_name = manifest.get("queue_file", "TASK_QUEUE.md")
    queue_relative = _relative_path(str(queue_name), field="queue_file", root=pilot_dir)
    if queue_relative != Path("TASK_QUEUE.md"):
        raise HandoffError("queue_file must be TASK_QUEUE.md inside pilot_dir")
    pilot_root = (root / pilot_relative).resolve()
    tasks = _manifest_tasks(manifest, path_root=pilot_root, input_root=root)
    if manifest.get("input_manifest_required", False):
        _ensure_manifest_task_inputs({"tasks": tasks}, root=root)
    for task in tasks:
        output_path = (pilot_root / task["output"]).resolve()
        try:
            output_path.relative_to(pilot_root)
        except ValueError as exc:
            raise HandoffError(f"{task['task_id']}.output must remain inside pilot_dir") from exc
    copy = dict(manifest)
    copy["pilot_dir"] = pilot_relative
    copy["queue_file"] = str(queue_relative)
    copy["tasks"] = tasks
    return copy


def _manifest_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest": {field: manifest.get(field) for field in IMMUTABLE_MANIFEST_FIELDS},
        "tasks": [
            {
                "task_id": task["task_id"],
                "output": task["output"],
                "inputs": task.get("inputs", []),
            }
            for task in manifest["tasks"]
        ],
    }


def _assert_trusted_contract(
    trusted: dict[str, Any],
    candidate: dict[str, Any],
    *,
    trusted_queue: str,
    candidate_queue: str,
) -> None:
    if _manifest_contract(candidate) != _manifest_contract(trusted):
        raise HandoffError(
            "remote manifest changes the trusted batch, base, task, output, input, or allowlist contract"
        )
    if _queue_contract(candidate_queue) != _queue_contract(trusted_queue):
        raise HandoffError("remote queue changes the trusted task definitions")
    transitions = {
        "READY_FOR_MIMO": {"READY_FOR_MIMO", "READY_FOR_CODEX", "BLOCKED"},
        "NEEDS_REWRITE": {"NEEDS_REWRITE", "READY_FOR_CODEX", "BLOCKED"},
        "READY_FOR_CODEX": {"READY_FOR_CODEX"},
        "DONE": {"DONE"},
        "BLOCKED": {"BLOCKED"},
    }
    candidate_by_id = {task["task_id"]: task for task in candidate["tasks"]}
    for task in trusted["tasks"]:
        new_status = candidate_by_id[task["task_id"]]["status"]
        if new_status not in transitions[task["status"]]:
            raise HandoffError(
                f"{task['task_id']}: remote status transition {task['status']} -> {new_status} is not allowed"
            )


def _assert_manifest_queue_contract(
    manifest: dict[str, Any], queue_text: str, *, root: Path
) -> None:
    sections = _queue_sections(queue_text)
    tasks = {task["task_id"]: task for task in manifest["tasks"]}
    if set(sections) != set(tasks):
        missing = sorted(set(tasks) - set(sections))
        extra = sorted(set(sections) - set(tasks))
        raise HandoffError(
            f"queue/manifest task mismatch (missing={missing}, extra={extra})"
        )
    pilot_dir = root / manifest["pilot_dir"]
    for task_id, task in tasks.items():
        outputs = re.findall(
            r"(?m)^- output: `?([^`\n]+)`?\s*$", sections[task_id]
        )
        if len(outputs) != 1 or outputs[0].strip() != task["output"]:
            raise HandoffError(
                f"{task_id}: queue output does not match the trusted manifest"
            )
        if task.get("inputs"):
            queue_inputs = _input_paths(
                sections[task_id], pilot_dir=pilot_dir, root=root
            )
            expected_paths = [item["path"] for item in task["inputs"]]
            actual_paths = [item["path"] for item in queue_inputs]
            if actual_paths != expected_paths:
                raise HandoffError(
                    f"{task_id}: queue inputs do not match the trusted manifest"
                )


def verify_run(
    manifest_path: Path,
    *,
    root: Path = ROOT,
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> dict[str, Any]:
    manifest_sha = _verify_manifest_digest(manifest_path)
    manifest = validate_manifest(_read_json(manifest_path), root=root)
    pilot_dir = root / manifest["pilot_dir"]
    queue = pilot_dir / manifest["queue_file"]
    if not queue.is_file():
        raise HandoffError(f"missing queue file {queue}")
    queue_sha = _sha256(queue)
    declared_queue_sha = manifest.get("queue_sha256")
    if declared_queue_sha != queue_sha:
        raise HandoffError(f"queue SHA mismatch (declared={declared_queue_sha!r}, actual={queue_sha})")
    queue_text = queue.read_text(encoding="utf-8")
    statuses = _queue_statuses(queue_text)
    if not statuses:
        raise HandoffError("TASK_QUEUE.md contains no task statuses")
    _assert_manifest_queue_contract(manifest, queue_text, root=root)
    task_ids = [task["task_id"] for task in manifest["tasks"]]
    if set(statuses) != set(task_ids):
        missing = sorted(set(task_ids) - set(statuses))
        extra = sorted(set(statuses) - set(task_ids))
        raise HandoffError(
            f"queue/manifest task mismatch (missing={missing}, extra={extra})"
        )
    details: list[dict[str, Any]] = []
    for task in manifest["tasks"]:
        task_id = task["task_id"]
        queue_status = statuses.get(task_id)
        if queue_status is None:
            raise HandoffError(f"{task_id} is missing from TASK_QUEUE.md")
        if queue_status != task["status"]:
            raise HandoffError(f"{task_id}: manifest status {task['status']} != queue status {queue_status}")
        for item in task.get("inputs", []):
            input_path = root / item["path"]
            if not input_path.is_file():
                raise HandoffError(f"{task_id}: missing input {item['path']}")
            actual_input_sha = _sha256(input_path)
            if actual_input_sha != item.get("sha256"):
                raise HandoffError(f"{task_id}: input SHA mismatch for {item['path']}")
        output = pilot_dir / task["output"]
        output_exists = output.is_file()
        actual_sha = _sha256(output) if output_exists else None
        declared_sha = task.get("output_sha256")
        if declared_sha is not None and (not re.fullmatch(r"[0-9a-f]{64}", str(declared_sha))):
            raise HandoffError(f"{task_id}: output_sha256 must be 64 lowercase hex characters")
        if declared_sha and actual_sha != declared_sha:
            raise HandoffError(f"{task_id}: output SHA mismatch (declared={declared_sha}, actual={actual_sha})")
        if task["status"] in {"READY_FOR_CODEX", "DONE", "NEEDS_REWRITE"} and not output_exists:
            raise HandoffError(f"{task_id}: {task['status']} requires an output file")
        details.append({"task_id": task_id, "status": queue_status, "output": task["output"], "sha256": actual_sha})
    if base_ref or head_ref:
        base = base_ref or manifest.get("base_ref")
        head = head_ref or "HEAD"
        if not isinstance(base, str) or not base:
            raise HandoffError("base_ref is required for branch scope verification")
        allowed_paths = {
            f"{manifest['pilot_dir'].rstrip('/')}/{MANIFEST_NAME}",
            f"{manifest['pilot_dir'].rstrip('/')}/{MANIFEST_DIGEST_NAME}",
            f"{manifest['pilot_dir'].rstrip('/')}/{manifest['queue_file']}",
        }
        allowed_paths.update(
            f"{manifest['pilot_dir'].rstrip('/')}/{task['output']}" for task in manifest["tasks"]
        )
        allowed_paths.update(
            f"{manifest['pilot_dir'].rstrip('/')}/codex-feedback-{task['task_id']}.md"
            for task in manifest["tasks"]
        )
        frozen_inputs = {
            item["path"] for task in manifest["tasks"] for item in task.get("inputs", [])
        }
        _verify_git_scope(
            base,
            head,
            manifest["pilot_dir"],
            allowed_paths=allowed_paths,
            forbidden_paths=frozen_inputs,
            root=root,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": manifest["batch_id"],
        "branch": manifest["branch"],
        "state": manifest["state"],
        "attempt": manifest["attempt"],
        "pilot_dir": manifest["pilot_dir"],
        "queue_sha256": queue_sha,
        "manifest_sha256": manifest_sha,
        "tasks": details,
    }


def _verify_git_scope(
    base: str,
    head: str,
    pilot_relative: str,
    *,
    allowed_paths: set[str] | None = None,
    forbidden_paths: set[str] | None = None,
    bootstrap_paths: set[str] | None = None,
    root: Path = ROOT,
) -> None:
    # Resolving refs through git avoids treating user-provided text as a shell command.
    for name, value in (("base_ref", base), ("head_ref", head)):
        if not SAFE_REF.fullmatch(value) or ".." in value:
            raise HandoffError(f"{name} contains unsafe git ref characters")
    _run_git("rev-parse", "--verify", f"{base}^{{commit}}", cwd=root)
    _run_git("rev-parse", "--verify", f"{head}^{{commit}}", cwd=root)
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=root, check=False)
    if ancestry.returncode:
        raise HandoffError(f"{head} is not based on {base}; refusing stale or unrelated handoff")
    changed = _run_git("diff", "--name-status", f"{base}...{head}", cwd=root)
    prefix = pilot_relative.rstrip("/") + "/"
    violations: list[str] = []
    for line in changed.splitlines():
        if not line:
            continue
        fields = line.split("\t")
        status, paths = fields[0], fields[1:]
        if status[:1] in {"D", "R", "C"}:
            violations.append(line)
            continue
        if any(
            not path.startswith(prefix)
            and (bootstrap_paths is None or path not in bootstrap_paths)
            for path in paths
        ):
            violations.append(line)
            continue
        if forbidden_paths is not None and any(path in forbidden_paths for path in paths):
            violations.append(line)
            continue
        if allowed_paths is not None and any(path not in allowed_paths for path in paths):
            violations.append(line)
            continue
        if any(SENSITIVE_NAME.search(path) for path in paths):
            violations.append(line)
    if violations:
        raise HandoffError("branch changes outside the handoff allowlist: " + "; ".join(violations[:8]))
    links = _run_git("ls-tree", "-r", "--full-tree", head, "--", pilot_relative, cwd=root)
    for line in links.splitlines():
        mode, _, path = line.partition("\t")
        if mode.startswith("120000") or SENSITIVE_NAME.search(path):
            raise HandoffError(f"unsafe tree entry in handoff branch: {path}")


def _git_blob(root: Path, ref: str, path: str) -> bytes:
    _relative_path(path, field="git blob path", root=root)
    return _run_git_bytes("show", f"{ref}:{path}", cwd=root)


def _verify_bootstrap_blobs(root: Path, head: str, paths: set[str]) -> None:
    """Accept initial helper files only when the remote cannot alter them."""
    for relative in sorted(paths):
        local = root / relative
        if not local.is_file():
            raise HandoffError(f"trusted bootstrap file is missing locally: {relative}")
        if _git_blob(root, head, relative) != local.read_bytes():
            raise HandoffError(f"remote bootstrap file differs from trusted local copy: {relative}")


def _trusted_static_paths(trusted: dict[str, Any], *, root: Path) -> set[str]:
    """Return fixed first-commit assets already available to the receiver."""
    pilot = trusted["pilot_dir"].rstrip("/")
    paths = {
        item["path"] for task in trusted["tasks"] for item in task.get("inputs", [])
    }
    for name in STATIC_BATCH_FILENAMES:
        candidate = f"{pilot}/{name}"
        if (root / candidate).is_file():
            paths.add(candidate)
    for relative in paths:
        if not (root / relative).is_file():
            raise HandoffError(f"trusted static batch file is missing locally: {relative}")
    return paths


def _verify_manifest_digest_payload(manifest_payload: bytes, digest_payload: bytes) -> str:
    try:
        line = digest_payload.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise HandoffError("remote manifest digest is not UTF-8") from exc
    match = re.fullmatch(r"([0-9a-f]{64})\s+\*?RUN_MANIFEST\.json", line)
    if not match:
        raise HandoffError("invalid remote manifest digest")
    actual = _sha256_bytes(manifest_payload)
    if actual != match.group(1):
        raise HandoffError(
            f"remote manifest SHA mismatch (declared={match.group(1)}, actual={actual})"
        )
    return actual


def _remote_preflight(
    *,
    root: Path,
    head: str,
    trusted_base: str,
    trusted: dict[str, Any],
    trusted_queue: str,
) -> dict[str, Any]:
    pilot = trusted["pilot_dir"].rstrip("/")
    manifest_relative = f"{pilot}/{MANIFEST_NAME}"
    digest_relative = f"{pilot}/{MANIFEST_DIGEST_NAME}"
    queue_relative = f"{pilot}/{trusted['queue_file']}"
    manifest_payload = _git_blob(root, head, manifest_relative)
    manifest_sha = _verify_manifest_digest_payload(
        manifest_payload, _git_blob(root, head, digest_relative)
    )
    candidate = validate_manifest(
        _json_object(manifest_payload, source=f"{head}:{manifest_relative}"), root=root
    )
    if not isinstance(candidate.get("queue_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", candidate["queue_sha256"]
    ):
        raise HandoffError("remote queue_sha256 must be 64 lowercase hex characters")
    try:
        candidate_queue = _git_blob(root, head, queue_relative).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HandoffError("remote queue is not UTF-8") from exc
    _assert_trusted_contract(
        trusted,
        candidate,
        trusted_queue=trusted_queue,
        candidate_queue=candidate_queue,
    )

    task_ids = [task["task_id"] for task in trusted["tasks"]]
    statuses = _queue_statuses(candidate_queue)
    if set(statuses) != set(task_ids):
        missing = sorted(set(task_ids) - set(statuses))
        extra = sorted(set(statuses) - set(task_ids))
        raise HandoffError(
            f"remote queue/manifest task mismatch (missing={missing}, extra={extra})"
        )
    queue_sha = _sha256_bytes(candidate_queue.encode("utf-8"))
    if candidate.get("queue_sha256") != queue_sha:
        raise HandoffError("remote queue SHA does not match RUN_MANIFEST.json")

    allowed_paths = {manifest_relative, digest_relative, queue_relative}
    allowed_paths.update(f"{pilot}/{task['output']}" for task in trusted["tasks"])
    allowed_paths.update(
        f"{pilot}/codex-feedback-{task['task_id']}.md" for task in trusted["tasks"]
    )
    frozen_inputs = {
        item["path"] for task in trusted["tasks"] for item in task.get("inputs", [])
    }
    trusted_static = _trusted_static_paths(trusted, root=root)
    changed_paths = set(
        _run_git("diff", "--name-only", f"{trusted_base}...{head}", cwd=root).splitlines()
    )
    changed_bootstrap = changed_paths & set(BOOTSTRAP_PATHS)
    _verify_bootstrap_blobs(root, head, changed_bootstrap)
    changed_static = changed_paths & trusted_static
    _verify_bootstrap_blobs(root, head, changed_static)
    _verify_git_scope(
        trusted_base,
        head,
        pilot,
        allowed_paths=allowed_paths | changed_bootstrap | changed_static,
        forbidden_paths=frozen_inputs - trusted_static,
        bootstrap_paths=changed_bootstrap,
        root=root,
    )

    details: list[dict[str, Any]] = []
    for task in candidate["tasks"]:
        task_id = task["task_id"]
        if statuses[task_id] != task["status"]:
            raise HandoffError(
                f"{task_id}: remote manifest status {task['status']} != queue status {statuses[task_id]}"
            )
        for item in task.get("inputs", []):
            if _sha256_bytes(_git_blob(root, head, item["path"])) != item["sha256"]:
                raise HandoffError(f"{task_id}: frozen input changed: {item['path']}")
        declared_sha = task.get("output_sha256")
        if declared_sha is not None and not re.fullmatch(r"[0-9a-f]{64}", str(declared_sha)):
            raise HandoffError(
                f"{task_id}: remote output_sha256 must be 64 lowercase hex characters"
            )
        output_sha = None
        output_path = f"{pilot}/{task['output']}"
        object_type = _run_git(
            "cat-file", "-t", f"{head}:{output_path}", cwd=root, check=False
        )
        if object_type:
            if object_type != "blob":
                raise HandoffError(f"{task_id}: remote output must be a regular blob")
            output_sha = _sha256_bytes(_git_blob(root, head, output_path))
        elif task["status"] in {"READY_FOR_CODEX", "DONE", "NEEDS_REWRITE"}:
            raise HandoffError(f"{task_id}: {task['status']} requires an output file")
        if declared_sha != output_sha:
            raise HandoffError(
                f"{task_id}: remote output SHA mismatch (declared={declared_sha}, actual={output_sha})"
            )
        details.append(
            {
                "task_id": task_id,
                "status": task["status"],
                "output": task["output"],
                "sha256": output_sha,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": candidate["batch_id"],
        "branch": candidate["branch"],
        "state": candidate["state"],
        "attempt": candidate["attempt"],
        "pilot_dir": candidate["pilot_dir"],
        "queue_sha256": queue_sha,
        "manifest_sha256": manifest_sha,
        "tasks": details,
    }


def initialize_manifest(
    pilot_dir: Path,
    *,
    batch_id: str,
    branch: str,
    base_ref: str,
    prompt_version: str,
    attempt: int = 1,
) -> Path:
    pilot_dir = pilot_dir.resolve()
    pilot_relative = pilot_dir.relative_to(ROOT.resolve())
    resolved_base = _run_git("rev-parse", "--verify", f"{base_ref}^{{commit}}", cwd=ROOT)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "branch": branch,
        "base_ref": resolved_base,
        "base_ref_name": base_ref,
        "pilot_dir": str(pilot_relative),
        "queue_file": "TASK_QUEUE.md",
        "state": "RUNNING",
        "attempt": attempt,
        "prompt_version": prompt_version,
        "input_manifest_required": True,
        "started_at": _utc_now(),
        "updated_at": _utc_now(),
        "queue_sha256": _sha256(pilot_dir / "TASK_QUEUE.md"),
        "tasks": [],
        "allowed_mutations": ["RUN_MANIFEST.json", "RUN_MANIFEST.sha256", "TASK_QUEUE.md", "*.jsonl", "codex-feedback-*.md"],
    }
    queue_path = pilot_dir / "TASK_QUEUE.md"
    queue_text = queue_path.read_text(encoding="utf-8")
    statuses = _queue_statuses(queue_text)
    sections = _queue_sections(queue_text)
    for task_id, status in statuses.items():
        section = re.search(rf"(?ms)^## {re.escape(task_id)}\s*$.*?(?=^## |\Z)", (pilot_dir / "TASK_QUEUE.md").read_text(encoding="utf-8"))
        output_match = re.search(r"(?m)^- output: `?([^`\n]+)`?\s*$", section.group(0) if section else "")
        if not output_match:
            continue
        output = output_match.group(1).strip()
        output_path = pilot_dir / output
        manifest["tasks"].append({
            "task_id": task_id,
            "status": status,
            "output": output,
            "output_sha256": _sha256(output_path) if output_path.is_file() else None,
            "inputs": _input_paths(sections.get(task_id, ""), pilot_dir=pilot_dir, root=ROOT),
        })
    path = pilot_dir / MANIFEST_NAME
    if path.exists():
        raise HandoffError(f"manifest already exists: {path}")
    _write_manifest(path, manifest)
    return path


def checkpoint_manifest(
    manifest_path: Path,
    *,
    state: str | None = None,
    refresh_inputs: bool = False,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Refresh queue/output hashes after a MiMo checkpoint, atomically."""
    raw = _read_json(manifest_path)
    manifest = validate_manifest(raw, root=root)
    pilot_dir = root / manifest["pilot_dir"]
    queue_path = pilot_dir / manifest["queue_file"]
    queue_text = queue_path.read_text(encoding="utf-8")
    statuses = _queue_statuses(queue_text)
    sections = _queue_sections(queue_text)
    task_by_id = {task["task_id"]: task for task in manifest["tasks"]}
    if set(statuses) != set(task_by_id):
        missing = sorted(set(task_by_id) - set(statuses))
        extra = sorted(set(statuses) - set(task_by_id))
        raise HandoffError(f"queue/manifest task mismatch (missing={missing}, extra={extra})")
    for task_id, task in task_by_id.items():
        task["status"] = statuses[task_id]
        if refresh_inputs:
            for item in task.get("inputs", []):
                input_path = root / item["path"]
                if not input_path.is_file():
                    raise HandoffError(f"{task_id}: missing input {item['path']}")
                item["sha256"] = _sha256(input_path)
        output = pilot_dir / task["output"]
        task["output_sha256"] = _sha256(output) if output.is_file() else None
        if "inputs" not in task:
            task["inputs"] = _input_paths(
                sections.get(task_id, ""), pilot_dir=pilot_dir, root=root
            )
    if state is None:
        values = set(statuses.values())
        if values <= {"DONE"}:
            state = "DONE"
        elif values & {"READY_FOR_MIMO", "NEEDS_REWRITE", "BLOCKED"}:
            state = "PARTIAL"
        else:
            state = "READY_FOR_CODEX"
    if state not in RUN_STATES:
        raise HandoffError(f"invalid checkpoint state: {state!r}")
    manifest["state"] = state
    manifest["updated_at"] = _utc_now()
    manifest["queue_sha256"] = _sha256(queue_path)
    manifest["tasks"] = list(task_by_id.values())
    _write_manifest(manifest_path, manifest)
    return verify_run(manifest_path, root=root)


def fetch_branch(
    branch: str,
    *,
    trusted_manifest_path: Path,
    remote: str = "origin",
    checkout_dir: Path | None = None,
    base_ref: str | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    if not SAFE_BRANCH.fullmatch(branch):
        raise HandoffError("branch must use the dedicated mimo/<batch> namespace")
    if not SAFE_REMOTE.fullmatch(remote):
        raise HandoffError("remote contains unsafe characters")
    trusted_manifest_path = trusted_manifest_path.resolve()
    trusted_root = _infer_root(trusted_manifest_path)
    _verify_manifest_digest(trusted_manifest_path)
    trusted = validate_manifest(_read_json(trusted_manifest_path), root=trusted_root)
    if trusted["branch"] != branch:
        raise HandoffError(
            f"requested branch {branch!r} does not match trusted manifest {trusted['branch']!r}"
        )
    trusted_queue_path = trusted_root / trusted["pilot_dir"] / trusted["queue_file"]
    trusted_queue = trusted_queue_path.read_text(encoding="utf-8")
    trusted_statuses = _queue_statuses(trusted_queue)
    trusted_task_ids = {task["task_id"] for task in trusted["tasks"]}
    if set(trusted_statuses) != trusted_task_ids:
        raise HandoffError("trusted queue and manifest do not declare the same task set")
    _assert_manifest_queue_contract(trusted, trusted_queue, root=trusted_root)
    trusted_base = _run_git(
        "rev-parse", "--verify", f"{base_ref or 'HEAD'}^{{commit}}", cwd=root
    )
    manifest_origin_base = trusted.get("base_ref")
    if not isinstance(manifest_origin_base, str) or not re.fullmatch(
        r"[0-9a-f]{40}", manifest_origin_base
    ):
        raise HandoffError("trusted manifest base_ref must be a frozen 40-character commit")
    origin_ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", manifest_origin_base, trusted_base],
        cwd=root,
        check=False,
    )
    if origin_ancestry.returncode:
        raise HandoffError(
            "trusted checkout base is not descended from the manifest origin base"
        )
    remote_ref = f"refs/remotes/{remote}/{branch}"
    _run_git("fetch", "--no-tags", remote, f"refs/heads/{branch}:{remote_ref}", cwd=root)
    head = _run_git("rev-parse", "--verify", f"{remote_ref}^{{commit}}", cwd=root)
    summary = _remote_preflight(
        root=root,
        head=head,
        trusted_base=trusted_base,
        trusted=trusted,
        trusted_queue=trusted_queue,
    )
    if checkout_dir is None:
        summary.update(
            {"branch": branch, "remote": remote, "head": head, "checkout_dir": None}
        )
        return summary
    destination = checkout_dir.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise HandoffError(f"checkout_dir must be empty: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run_git("worktree", "add", "--detach", str(destination), head, cwd=root)
    manifest_path = destination / trusted["pilot_dir"] / MANIFEST_NAME
    if not manifest_path.exists():
        raise HandoffError("fetched branch has no RUN_MANIFEST.json at the trusted path")
    candidate = validate_manifest(_read_json(manifest_path), root=destination)
    candidate_queue = (
        destination / candidate["pilot_dir"] / candidate["queue_file"]
    ).read_text(encoding="utf-8")
    _assert_trusted_contract(
        trusted,
        candidate,
        trusted_queue=trusted_queue,
        candidate_queue=candidate_queue,
    )
    # `_remote_preflight` above performed the scope check using the receiver's
    # trusted copies. Repeating it in the remote worktree would self-trust the
    # bootstrap files that were just fetched.
    verify_run(manifest_path, root=destination)
    summary.update({"branch": branch, "remote": remote, "head": head, "checkout_dir": str(destination)})
    return summary


def _cmd_init(args: argparse.Namespace) -> int:
    path = initialize_manifest(
        Path(args.pilot_dir),
        batch_id=args.batch_id,
        branch=args.branch,
        base_ref=args.base_ref,
        prompt_version=args.prompt_version,
        attempt=args.attempt,
    )
    print(path)
    return 0


def _infer_root(manifest_path: Path) -> Path:
    resolved = manifest_path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / "config.yaml").is_file() and (candidate / ".git").exists():
            return candidate
    return ROOT


def _cmd_verify(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    summary = verify_run(manifest_path, root=_infer_root(manifest_path), base_ref=args.base_ref, head_ref=args.head_ref)
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else f"MiMo handoff verified: {summary['batch_id']} ({len(summary['tasks'])} tasks)")
    return 0


def _cmd_checkpoint(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    summary = checkpoint_manifest(
        manifest_path,
        state=args.state,
        refresh_inputs=args.refresh_inputs,
        root=_infer_root(manifest_path),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else f"MiMo checkpoint recorded: {summary['batch_id']} ({summary['state']})")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    summary = fetch_branch(
        args.branch,
        trusted_manifest_path=Path(args.trusted_manifest),
        remote=args.remote,
        checkout_dir=Path(args.checkout_dir) if args.checkout_dir else None,
        base_ref=args.base_ref,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="write a run manifest for a prepared pilot directory")
    init.add_argument("--pilot-dir", required=True, type=Path)
    init.add_argument("--batch-id", required=True)
    init.add_argument("--branch", required=True)
    init.add_argument("--base-ref", default="origin/main")
    init.add_argument("--prompt-version", default="mimo-handoff-v1")
    init.add_argument("--attempt", type=int, default=1)
    init.set_defaults(func=_cmd_init)
    verify = sub.add_parser("verify", help="verify a manifest, queue, hashes, and optional git scope")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("--base-ref")
    verify.add_argument("--head-ref")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=_cmd_verify)
    checkpoint = sub.add_parser("checkpoint", help="atomically refresh manifest status and hashes")
    checkpoint.add_argument("manifest", type=Path)
    checkpoint.add_argument("--state", choices=sorted(RUN_STATES))
    checkpoint.add_argument(
        "--refresh-inputs",
        action="store_true",
        help="refresh input SHAs after an intentional Codex-side derived-file update",
    )
    checkpoint.add_argument("--json", action="store_true")
    checkpoint.set_defaults(func=_cmd_checkpoint)
    fetch = sub.add_parser("fetch", help="fetch a dedicated branch and optionally create an isolated worktree")
    fetch.add_argument("--branch", required=True)
    fetch.add_argument("--trusted-manifest", required=True, type=Path)
    fetch.add_argument("--remote", default="origin")
    fetch.add_argument("--base-ref")
    fetch.add_argument("--checkout-dir", type=Path)
    fetch.set_defaults(func=_cmd_fetch)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (HandoffError, OSError, subprocess.SubprocessError) as exc:
        print(f"MiMo handoff rejected: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
