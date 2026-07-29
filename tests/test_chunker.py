import unittest

from ioskb.chunker import markdown_chunks


class MarkdownChunkTests(unittest.TestCase):
    def test_splits_oversized_single_line_without_losing_text(self):
        heading = "# Transcript"
        long_line = ("Swift concurrency keeps mutable state isolated. " * 120).strip()
        text = f"{heading}\n{long_line}"

        chunks = markdown_chunks(text, max_chars=160)

        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk["text"]) <= 160 for chunk in chunks))
        line_chunks = [chunk for chunk in chunks if chunk["start_line"] == 2]
        self.assertGreater(len(line_chunks), 1)
        self.assertTrue(all(chunk["end_line"] == 2 for chunk in line_chunks))
        self.assertEqual("".join(chunk["text"] for chunk in line_chunks), long_line)
        self.assertTrue(all(chunk["title_path"] == "Transcript" for chunk in chunks))

    def test_repackages_multiline_group_that_exceeds_limit_via_blank_lines(self):
        text = "# Notes\n" + ("a" * 70) + ("\n" * 40) + ("b" * 70)

        chunks = markdown_chunks(text, max_chars=100)

        self.assertTrue(chunks)
        self.assertTrue(all(len(chunk["text"]) <= 100 for chunk in chunks))
        self.assertTrue(all(chunk["title_path"] == "Notes" for chunk in chunks))

    def test_natural_boundary_at_window_edge_does_not_exceed_limit(self):
        long_line = ("a" * 100) + " " + ("b" * 100)

        chunks = markdown_chunks(long_line, max_chars=100)

        self.assertTrue(all(len(chunk["text"]) <= 100 for chunk in chunks))
        self.assertEqual("".join(chunk["text"] for chunk in chunks), long_line)


if __name__ == "__main__":
    unittest.main()
