import tempfile
import unittest
from pathlib import Path

from ioskb.ingest import file_chunks


class SourceIngestTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
