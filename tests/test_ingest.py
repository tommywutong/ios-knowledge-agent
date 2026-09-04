import tempfile
import unittest
from pathlib import Path

from ioskb.ingest import file_chunks, iter_source_files


class SourceIngestTests(unittest.TestCase):
    def test_content_filter_keeps_ios_blog_and_rejects_life_blog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blogs = root / "blogs" / "zh"
            blogs.mkdir(parents=True)
            ios_post = blogs / "runtime.md"
            life_post = blogs / "dinner.md"
            ios_post.write_text("Objective-C runtime message dispatch", encoding="utf-8")
            life_post.write_text("今天做番茄炒蛋。", encoding="utf-8")
            source = {
                "path": str(root),
                "include": ["blogs/**/*.md"],
                "content_filter": {
                    "globs": ["blogs/**/*.md"],
                    "include_any": ["objective-c", "swift"],
                },
            }

            self.assertEqual(iter_source_files(source), [ios_post])

    def test_swift_and_assembly_are_ingested_as_source_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swift = root / "Example.swift"
            assembly = root / "objc-msg-arm64.S"
            swift.write_text("func answer() -> Int {\n    42\n}\n", encoding="utf-8")
            assembly.write_text("_objc_msgSend:\n    ret\n", encoding="utf-8")
            source = {"name": "labs", "path": str(root), "type": "source_code"}
            chunking = {"code_max_lines": 120, "code_min_lines": 25}

            for path in (swift, assembly):
                display, chunks = file_chunks(source, path, chunking)
                self.assertEqual(display, str(path.resolve()))
                self.assertTrue(chunks)
                self.assertTrue(all(chunk["type"] == "source_code" for chunk in chunks))
                self.assertTrue(all(chunk["source"] == "labs" for chunk in chunks))

    def test_recursive_exclude_keeps_source_learning_workspace_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lab = root / "MemoryMapLab" / "experiment.m"
            source_learning = root / "ios-source-learning" / "runtime" / "objc.m"
            lab.parent.mkdir(parents=True)
            source_learning.parent.mkdir(parents=True)
            lab.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            source_learning.write_text("int internal(void) { return 0; }\n", encoding="utf-8")
            source = {
                "path": str(root),
                "include": ["**/*.m"],
                "exclude": ["ios-source-learning/**"],
            }

            self.assertEqual(iter_source_files(source), [lab])


if __name__ == "__main__":
    unittest.main()
