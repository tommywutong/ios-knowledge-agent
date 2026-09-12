import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import receive_mimo_quality_batch


class ReceiveMimoQualityBatchTests(unittest.TestCase):
    def test_completed_handoff_requires_full_batch_validation(self):
        handoff = {"checkout_dir": "/tmp/mimo-worktree", "pilot_dir": "data/glm/mimo-quality-20260913", "tasks": [{"status": "READY_FOR_CODEX"}]}
        with patch.object(receive_mimo_quality_batch.mimo_handoff, "fetch_branch", return_value=handoff), patch.object(receive_mimo_quality_batch.validate_mimo_batch, "validate_batch", return_value={"valid_output_count": 1}) as validate:
            result = receive_mimo_quality_batch.receive_batch(branch="mimo/mimo-quality-20260913", trusted_manifest=Path("trusted.json"), checkout_dir=Path("/tmp/mimo-worktree"))
        self.assertTrue(result["complete"])
        self.assertTrue(validate.call_args.kwargs["require_complete"])

    def test_partial_handoff_keeps_checkpoint_validation_incremental(self):
        handoff = {"checkout_dir": "/tmp/mimo-worktree", "pilot_dir": "data/glm/mimo-quality-20260913", "tasks": [{"status": "READY_FOR_MIMO"}]}
        with patch.object(receive_mimo_quality_batch.mimo_handoff, "fetch_branch", return_value=handoff), patch.object(receive_mimo_quality_batch.validate_mimo_batch, "validate_batch", return_value={"valid_output_count": 0}) as validate:
            result = receive_mimo_quality_batch.receive_batch(branch="mimo/mimo-quality-20260913", trusted_manifest=Path("trusted.json"), checkout_dir=Path("/tmp/mimo-worktree"))
        self.assertFalse(result["complete"])
        self.assertFalse(validate.call_args.kwargs["require_complete"])


if __name__ == "__main__":
    unittest.main()
