import unittest

from ioskb.metadata import export_metadata


class ExportMetadataTests(unittest.TestCase):
    def test_keeps_explicit_versions_and_code_language(self):
        meta = export_metadata(
            "/资料/Actor.swift",
            "Swift Concurrency › MainActor",
            "iOS 17 introduces an API available with Swift 5.9.",
        )
        self.assertEqual(meta["ios_version"], "17")
        self.assertEqual(meta["swift_version"], "5.9")
        self.assertEqual(meta["language"], "Swift")
        self.assertEqual(meta["section"], "MainActor")

    def test_does_not_invent_versions(self):
        meta = export_metadata("/资料/weak.md", "weak", "weak 引用不会增加引用计数")
        self.assertNotIn("ios_version", meta)
        self.assertNotIn("swift_version", meta)
        self.assertEqual(meta["topic"], "内存管理")


if __name__ == "__main__":
    unittest.main()
