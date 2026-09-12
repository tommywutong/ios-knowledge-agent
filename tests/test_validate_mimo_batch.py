import unittest

from scripts import validate_mimo_batch


class MimoQualityBatchTests(unittest.TestCase):
    def test_empty_queue_value_does_not_consume_the_next_field(self):
        section = "- output_sha256:\n- note: waiting\n"
        self.assertEqual(
            "", validate_mimo_batch._queue_value(section, "output_sha256", required=False)
        )
        self.assertEqual("waiting", validate_mimo_batch._queue_value(section, "note"))

    def test_current_generated_batch_passes_structural_validation(self):
        summary = validate_mimo_batch.validate_batch(
            validate_mimo_batch.ROOT / "data/glm/mimo-quality-20260913"
        )
        self.assertEqual("mimo-quality-20260913", summary["batch_id"])
        self.assertEqual(28, summary["selected_task_count"])
        self.assertEqual(28, summary["missing_output_count"])

    def test_output_text_rejects_paths_credentials_and_line_ranges(self):
        for text in ("/Users/example/private.md", "token=not-allowed", "第 3-8 行"):
            with self.assertRaises(validate_mimo_batch.BatchValidationError):
                validate_mimo_batch._bounded_string(text, field="test", low=1, high=240)


if __name__ == "__main__":
    unittest.main()
