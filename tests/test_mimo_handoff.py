import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import mimo_handoff


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class MimoHandoffTests(unittest.TestCase):
    def _fixture(self) -> tuple[Path, Path, dict]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".git").mkdir()
        (root / "config.yaml").write_text("{}\n", encoding="utf-8")
        pilot = root / "data" / "glm" / "batch-1"
        pilot.mkdir(parents=True)
        queue = pilot / "TASK_QUEUE.md"
        queue.write_text("## task-001\n- status: `READY_FOR_CODEX`\n- output: `result.jsonl`\n", encoding="utf-8")
        output = pilot / "result.jsonl"
        output.write_text('{"id":"1"}\n', encoding="utf-8")
        manifest = {
            "schema_version": mimo_handoff.SCHEMA_VERSION,
            "batch_id": "batch-1",
            "branch": "mimo/batch-1",
            "base_ref": "origin/main",
            "pilot_dir": "data/glm/batch-1",
            "queue_file": "TASK_QUEUE.md",
            "state": "READY_FOR_CODEX",
            "attempt": 1,
            "prompt_version": "mimo-handoff-v1",
            "queue_sha256": _sha(queue),
            "tasks": [{
                "task_id": "task-001",
                "status": "READY_FOR_CODEX",
                "output": "result.jsonl",
                "output_sha256": _sha(output),
            }],
        }
        path = pilot / "RUN_MANIFEST.json"
        mimo_handoff._write_manifest(path, manifest)
        self.addCleanup(temp.cleanup)
        return root, path, manifest

    def test_verify_checks_queue_and_output_hashes(self) -> None:
        root, path, _ = self._fixture()
        summary = mimo_handoff.verify_run(path, root=root)
        self.assertEqual("batch-1", summary["batch_id"])
        self.assertEqual("READY_FOR_CODEX", summary["tasks"][0]["status"])

    def test_checkpoint_refreshes_status_and_hashes_atomically(self) -> None:
        root, path, _ = self._fixture()
        queue = root / "data/glm/batch-1/TASK_QUEUE.md"
        queue.write_text("## task-001\n- status: `DONE`\n- output: `result.jsonl`\n", encoding="utf-8")
        summary = mimo_handoff.checkpoint_manifest(path, root=root)
        self.assertEqual("DONE", summary["state"])
        self.assertEqual("DONE", summary["tasks"][0]["status"])
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(_sha(queue), saved["queue_sha256"])

    def test_manifest_rejects_absolute_or_outside_output(self) -> None:
        root, path, manifest = self._fixture()
        manifest["tasks"][0]["output"] = "../secret.jsonl"
        with self.assertRaises(mimo_handoff.HandoffError):
            mimo_handoff.validate_manifest(manifest, root=root)

    def test_manifest_rejects_wrong_queue_hash(self) -> None:
        root, path, manifest = self._fixture()
        manifest["queue_sha256"] = "0" * 64
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(mimo_handoff.HandoffError):
            mimo_handoff.verify_run(path, root=root)

    def test_manifest_digest_sidecar_is_required(self) -> None:
        root, path, _ = self._fixture()
        path.with_name("RUN_MANIFEST.sha256").unlink()
        with self.assertRaises(mimo_handoff.HandoffError):
            mimo_handoff.verify_run(path, root=root)

    def test_manifest_rejects_output_not_declared_by_queue(self) -> None:
        root, path, manifest = self._fixture()
        trusted = mimo_handoff.validate_manifest(manifest, root=root)
        manifest["tasks"][0]["output"] = "unlisted.jsonl"
        manifest["queue_sha256"] = _sha(root / "data/glm/batch-1/TASK_QUEUE.md")
        output = root / "data/glm/batch-1/unlisted.jsonl"
        output.write_text("{}\n", encoding="utf-8")
        manifest["tasks"][0]["output_sha256"] = _sha(output)
        mimo_handoff._write_manifest(path, manifest)
        with self.assertRaisesRegex(mimo_handoff.HandoffError, "queue output"):
            mimo_handoff.verify_run(path, root=root)
        candidate = mimo_handoff.validate_manifest(manifest, root=root)
        queue = (root / "data/glm/batch-1/TASK_QUEUE.md").read_text(encoding="utf-8")
        with self.assertRaises(mimo_handoff.HandoffError):
            mimo_handoff._assert_trusted_contract(
                trusted, candidate, trusted_queue=queue, candidate_queue=queue
            )

    def test_queue_and_manifest_task_sets_must_match(self) -> None:
        root, path, manifest = self._fixture()
        queue = root / "data/glm/batch-1/TASK_QUEUE.md"
        queue.write_text(
            queue.read_text(encoding="utf-8")
            + "\n## task-999\n- status: `READY_FOR_MIMO`\n- output: `extra.jsonl`\n",
            encoding="utf-8",
        )
        manifest["queue_sha256"] = _sha(queue)
        mimo_handoff._write_manifest(path, manifest)
        with self.assertRaisesRegex(mimo_handoff.HandoffError, "task mismatch"):
            mimo_handoff.verify_run(path, root=root)

    def test_trusted_contract_rejects_input_hash_changes(self) -> None:
        root, _, manifest = self._fixture()
        input_path = root / "data/glm/input.jsonl"
        input_path.write_text("{}\n", encoding="utf-8")
        manifest["tasks"][0]["inputs"] = [
            {"path": "data/glm/input.jsonl", "sha256": _sha(input_path)}
        ]
        trusted = mimo_handoff.validate_manifest(manifest, root=root)
        candidate = json.loads(json.dumps(trusted))
        candidate["tasks"][0]["inputs"][0]["sha256"] = "0" * 64
        queue = (root / "data/glm/batch-1/TASK_QUEUE.md").read_text(encoding="utf-8")
        with self.assertRaisesRegex(mimo_handoff.HandoffError, "trusted"):
            mimo_handoff._assert_trusted_contract(
                trusted, candidate, trusted_queue=queue, candidate_queue=queue
            )

    def test_bootstrap_blob_must_match_the_local_trusted_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.name", "Test")
            _git(root, "config", "user.email", "test@example.invalid")
            helper = root / "scripts/mimo_handoff.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("trusted helper\n", encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-m", "base")
            _git(root, "switch", "-c", "mimo/bootstrap")
            _git(root, "commit", "--allow-empty", "-m", "branch")
            head = _git(root, "rev-parse", "HEAD")
            mimo_handoff._verify_bootstrap_blobs(root, head, {"scripts/mimo_handoff.py"})
            helper.write_text("untrusted helper\n", encoding="utf-8")
            with self.assertRaisesRegex(mimo_handoff.HandoffError, "differs"):
                mimo_handoff._verify_bootstrap_blobs(root, head, {"scripts/mimo_handoff.py"})

    def test_static_first_commit_assets_must_match_local_trust(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _git(root, "init", "-b", "main")
            _git(root, "config", "user.name", "Test")
            _git(root, "config", "user.email", "test@example.invalid")
            asset = root / "data/glm/batch-1/inputs/task-001.jsonl"
            asset.parent.mkdir(parents=True)
            asset.write_text('{"id":"trusted"}\n', encoding="utf-8")
            _git(root, "add", ".")
            _git(root, "commit", "-m", "batch assets")
            head = _git(root, "rev-parse", "HEAD")
            trusted = {
                "pilot_dir": "data/glm/batch-1",
                "tasks": [{"inputs": [{"path": "data/glm/batch-1/inputs/task-001.jsonl"}]}],
            }
            paths = mimo_handoff._trusted_static_paths(trusted, root=root)
            mimo_handoff._verify_bootstrap_blobs(root, head, paths)
            asset.write_text('{"id":"changed"}\n', encoding="utf-8")
            with self.assertRaisesRegex(mimo_handoff.HandoffError, "differs"):
                mimo_handoff._verify_bootstrap_blobs(root, head, paths)

    def _git_handoff(self) -> tuple[Path, Path, Path, Path, str]:
        temporary = tempfile.TemporaryDirectory()
        sandbox = Path(temporary.name)
        self.addCleanup(temporary.cleanup)
        remote = sandbox / "remote.git"
        seed = sandbox / "seed"
        receiver = sandbox / "receiver"
        worker = sandbox / "worker"
        remote.mkdir()
        seed.mkdir()
        _git(remote, "init", "--bare")
        _git(seed, "init", "-b", "main")
        _git(seed, "config", "user.name", "Test")
        _git(seed, "config", "user.email", "test@example.invalid")
        (seed / "config.yaml").write_text("{}\n", encoding="utf-8")
        pilot = seed / "data/glm/batch-1"
        pilot.mkdir(parents=True)
        (pilot / "input.jsonl").write_text('{"id":"1"}\n', encoding="utf-8")
        queue_text = (
            "# Queue\n\n"
            "## task-001\n\n"
            "- status: `READY_FOR_MIMO`\n"
            "- input: `data/glm/batch-1/input.jsonl`\n"
            "- output: `result.jsonl`\n"
            "- objective: Preserve this frozen task definition.\n"
        )
        (pilot / "TASK_QUEUE.md").write_text(queue_text, encoding="utf-8")
        _git(seed, "add", ".")
        _git(seed, "commit", "-m", "base")
        base = _git(seed, "rev-parse", "HEAD")
        _git(seed, "remote", "add", "origin", str(remote))
        _git(seed, "push", "origin", "main")
        _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(sandbox, "clone", str(remote), str(receiver))
        _git(sandbox, "clone", str(remote), str(worker))
        for repo in (receiver, worker):
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.invalid")

        trusted = {
            "schema_version": mimo_handoff.SCHEMA_VERSION,
            "batch_id": "batch-1",
            "branch": "mimo/batch-1",
            "base_ref": base,
            "base_ref_name": "origin/main",
            "pilot_dir": "data/glm/batch-1",
            "queue_file": "TASK_QUEUE.md",
            "state": "RUNNING",
            "attempt": 1,
            "prompt_version": "mimo-handoff-v1",
            "input_manifest_required": True,
            "started_at": "2026-09-12T00:00:00Z",
            "updated_at": "2026-09-12T00:00:00Z",
            "queue_sha256": _sha(receiver / "data/glm/batch-1/TASK_QUEUE.md"),
            "allowed_mutations": [
                "RUN_MANIFEST.json",
                "RUN_MANIFEST.sha256",
                "TASK_QUEUE.md",
                "*.jsonl",
                "codex-feedback-*.md",
            ],
            "tasks": [
                {
                    "task_id": "task-001",
                    "status": "READY_FOR_MIMO",
                    "output": "result.jsonl",
                    "output_sha256": None,
                    "inputs": [
                        {
                            "path": "data/glm/batch-1/input.jsonl",
                            "sha256": _sha(receiver / "data/glm/batch-1/input.jsonl"),
                        }
                    ],
                }
            ],
        }
        trust_dir = receiver / ".trusted"
        trust_dir.mkdir()
        trusted_path = trust_dir / "RUN_MANIFEST.json"
        mimo_handoff._write_manifest(trusted_path, trusted)

        _git(worker, "switch", "-c", "mimo/batch-1")
        worker_pilot = worker / "data/glm/batch-1"
        output = worker_pilot / "result.jsonl"
        output.write_text('{"id":"1","review":"candidate"}\n', encoding="utf-8")
        ready_queue = queue_text.replace("READY_FOR_MIMO", "READY_FOR_CODEX")
        (worker_pilot / "TASK_QUEUE.md").write_text(ready_queue, encoding="utf-8")
        candidate = json.loads(json.dumps(trusted))
        candidate["state"] = "READY_FOR_CODEX"
        candidate["updated_at"] = "2026-09-12T01:00:00Z"
        candidate["queue_sha256"] = _sha(worker_pilot / "TASK_QUEUE.md")
        candidate["tasks"][0]["status"] = "READY_FOR_CODEX"
        candidate["tasks"][0]["output_sha256"] = _sha(output)
        mimo_handoff._write_manifest(worker_pilot / "RUN_MANIFEST.json", candidate)
        _git(worker, "add", "data/glm/batch-1")
        _git(worker, "commit", "-m", "mimo checkpoint")
        _git(worker, "push", "-u", "origin", "mimo/batch-1")
        return receiver, worker, trusted_path, sandbox, base

    def test_real_git_push_fetch_and_worktree_uses_local_trust(self) -> None:
        receiver, _, trusted_path, sandbox, base = self._git_handoff()
        checkout = sandbox / "accepted"
        summary = mimo_handoff.fetch_branch(
            "mimo/batch-1",
            trusted_manifest_path=trusted_path,
            remote="origin",
            checkout_dir=checkout,
            base_ref=base,
            root=receiver,
        )
        self.assertEqual("READY_FOR_CODEX", summary["state"])
        self.assertTrue((checkout / "data/glm/batch-1/result.jsonl").is_file())

    def test_real_git_fetch_rejects_remote_contract_expansion_before_checkout(self) -> None:
        receiver, worker, trusted_path, sandbox, _ = self._git_handoff()
        pilot = worker / "data/glm/batch-1"
        manifest = json.loads((pilot / "RUN_MANIFEST.json").read_text(encoding="utf-8"))
        manifest["allowed_mutations"].append("scripts/**")
        manifest["tasks"][0]["output"] = "extra.jsonl"
        manifest["tasks"][0]["inputs"][0]["sha256"] = "0" * 64
        (pilot / "extra.jsonl").write_text("{}\n", encoding="utf-8")
        manifest["tasks"][0]["output_sha256"] = _sha(pilot / "extra.jsonl")
        queue = (pilot / "TASK_QUEUE.md").read_text(encoding="utf-8")
        (pilot / "TASK_QUEUE.md").write_text(
            queue.replace("result.jsonl", "extra.jsonl").replace(
                "Preserve this frozen task definition", "Expanded remote task definition"
            ),
            encoding="utf-8",
        )
        manifest["queue_sha256"] = _sha(pilot / "TASK_QUEUE.md")
        mimo_handoff._write_manifest(pilot / "RUN_MANIFEST.json", manifest)
        marker = sandbox / "remote-code-ran"
        remote_script = worker / "scripts/mimo_handoff.py"
        remote_script.parent.mkdir(parents=True, exist_ok=True)
        remote_script.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
            encoding="utf-8",
        )
        _git(worker, "add", ".")
        _git(worker, "commit", "-m", "expand remote contract")
        _git(worker, "push", "origin", "mimo/batch-1")

        checkout = sandbox / "rejected"
        with self.assertRaisesRegex(mimo_handoff.HandoffError, "trusted"):
            mimo_handoff.fetch_branch(
                "mimo/batch-1",
                trusted_manifest_path=trusted_path,
                remote="origin",
                checkout_dir=checkout,
                root=receiver,
            )
        self.assertFalse(checkout.exists())
        self.assertFalse(marker.exists())

    def test_real_git_fetch_accepts_only_matching_first_commit_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            remote, seed, receiver, worker = (
                sandbox / "remote.git",
                sandbox / "seed",
                sandbox / "receiver",
                sandbox / "worker",
            )
            remote.mkdir()
            seed.mkdir()
            _git(remote, "init", "--bare")
            _git(seed, "init", "-b", "main")
            _git(seed, "config", "user.name", "Test")
            _git(seed, "config", "user.email", "test@example.invalid")
            (seed / "config.yaml").write_text("{}\n", encoding="utf-8")
            _git(seed, "add", ".")
            _git(seed, "commit", "-m", "base")
            base = _git(seed, "rev-parse", "HEAD")
            _git(seed, "remote", "add", "origin", str(remote))
            _git(seed, "push", "origin", "main")
            _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
            _git(sandbox, "clone", str(remote), str(receiver))
            _git(sandbox, "clone", str(remote), str(worker))
            for repo in (receiver, worker):
                _git(repo, "config", "user.name", "Test")
                _git(repo, "config", "user.email", "test@example.invalid")

            pilot_relative = "data/glm/batch-1"
            queue_text = "## task-001\n- status: `READY_FOR_MIMO`\n- input: `data/glm/batch-1/inputs/task-001.jsonl`\n- output: `outputs/task-001.jsonl`\n"
            input_payload = '{"id":"frozen"}\n'
            for repo in (receiver, worker):
                pilot = repo / pilot_relative
                (pilot / "inputs").mkdir(parents=True)
                (pilot / "inputs/task-001.jsonl").write_text(input_payload, encoding="utf-8")
                (pilot / "TASK_QUEUE.md").write_text(queue_text, encoding="utf-8")
                for name in mimo_handoff.STATIC_BATCH_FILENAMES:
                    if name != "TASK_QUEUE.md":
                        (pilot / name).write_text("trusted\n", encoding="utf-8")

            trusted = {
                "schema_version": mimo_handoff.SCHEMA_VERSION,
                "batch_id": "batch-1",
                "branch": "mimo/batch-1",
                "base_ref": base,
                "base_ref_name": "origin/main",
                "pilot_dir": pilot_relative,
                "queue_file": "TASK_QUEUE.md",
                "state": "RUNNING",
                "attempt": 1,
                "prompt_version": "test",
                "input_manifest_required": True,
                "started_at": "2026-09-12T00:00:00Z",
                "updated_at": "2026-09-12T00:00:00Z",
                "queue_sha256": _sha(receiver / pilot_relative / "TASK_QUEUE.md"),
                "allowed_mutations": [],
                "tasks": [{"task_id": "task-001", "status": "READY_FOR_MIMO", "output": "outputs/task-001.jsonl", "output_sha256": None, "inputs": [{"path": f"{pilot_relative}/inputs/task-001.jsonl", "sha256": _sha(receiver / pilot_relative / "inputs/task-001.jsonl")}]}],
            }
            trusted_path = receiver / ".trusted/RUN_MANIFEST.json"
            trusted_path.parent.mkdir()
            mimo_handoff._write_manifest(trusted_path, trusted)

            _git(worker, "switch", "-c", "mimo/batch-1")
            output = worker / pilot_relative / "outputs/task-001.jsonl"
            output.parent.mkdir()
            output.write_text('{"id":"candidate"}\n', encoding="utf-8")
            ready_queue = queue_text.replace("READY_FOR_MIMO", "READY_FOR_CODEX")
            (worker / pilot_relative / "TASK_QUEUE.md").write_text(ready_queue, encoding="utf-8")
            candidate = json.loads(json.dumps(trusted))
            candidate["state"] = "READY_FOR_CODEX"
            candidate["updated_at"] = "2026-09-12T01:00:00Z"
            candidate["queue_sha256"] = _sha(worker / pilot_relative / "TASK_QUEUE.md")
            candidate["tasks"][0]["status"] = "READY_FOR_CODEX"
            candidate["tasks"][0]["output_sha256"] = _sha(output)
            mimo_handoff._write_manifest(worker / pilot_relative / "RUN_MANIFEST.json", candidate)
            _git(worker, "add", pilot_relative)
            _git(worker, "commit", "-m", "first MiMo batch checkpoint")
            _git(worker, "push", "-u", "origin", "mimo/batch-1")

            checkout = sandbox / "accepted"
            summary = mimo_handoff.fetch_branch("mimo/batch-1", trusted_manifest_path=trusted_path, checkout_dir=checkout, root=receiver)
            self.assertEqual("READY_FOR_CODEX", summary["state"])
            self.assertTrue((checkout / pilot_relative / "outputs/task-001.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
