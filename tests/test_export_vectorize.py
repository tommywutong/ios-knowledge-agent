import json
import unittest

from ioskb.export_vectorize import stable_vector_id


class VectorizeExportTests(unittest.TestCase):
    def test_vector_id_is_stable_and_bounded(self):
        first = stable_vector_id("notes", "/资料/weak.md", 3)
        second = stable_vector_id("notes", "/资料/weak.md", 3)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("v1-"))
        self.assertLessEqual(len(first), 64)
        self.assertNotEqual(first, stable_vector_id("notes", "/资料/weak.md", 4))

    def test_export_escapes_unicode_line_separators(self):
        line = json.dumps({"text": "标题\u2028下一行\u2029"}, ensure_ascii=False)
        safe = line.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        self.assertNotIn("\u2028", safe)
        self.assertNotIn("\u2029", safe)
        self.assertEqual(json.loads(safe)["text"], "标题\u2028下一行\u2029")


if __name__ == "__main__":
    unittest.main()
