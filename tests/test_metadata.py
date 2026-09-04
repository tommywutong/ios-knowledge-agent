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
        self.assertEqual(meta["authority"], "unverified_note")

    def test_does_not_invent_versions(self):
        meta = export_metadata("/资料/weak.md", "weak", "weak 引用不会增加引用计数")
        self.assertNotIn("ios_version", meta)
        self.assertNotIn("swift_version", meta)
        self.assertEqual(meta["topic"], "内存管理")

    def test_marks_official_and_reviewed_note_authority(self):
        official = export_metadata(
            "/资料/apple.md", "API", "Reference", source="archive", ctype="doc"
        )
        reviewed = export_metadata(
            "/笔记/weak.md",
            "weak",
            "**来源**: 官方　**confidence**: 0.90",
            source="obsidian-ios",
            ctype="note",
        )

        self.assertEqual(official["authority"], "official")
        self.assertEqual(reviewed["authority"], "reviewed_note")
        self.assertEqual(reviewed["confidence"], 0.9)

    def test_downgrades_bulk_community_and_marks_open_source(self):
        community = export_metadata(
            "/data/repos/apple-docs-vault/oss/iOS-Weekly/objc-runtime.md",
            "objc_msgSend",
            "社区文章正文",
            source="apple-docs-bulk",
            ctype="doc",
        )
        open_source = export_metadata(
            "/data/repos/apple-docs-vault/oss/libdispatch/src/queue.c",
            "dispatch_async",
            "libdispatch source",
            source="apple-docs-bulk",
            ctype="doc",
        )

        self.assertEqual(community["authority"], "community")
        self.assertEqual(open_source["authority"], "primary_source")


if __name__ == "__main__":
    unittest.main()
