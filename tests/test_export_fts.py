import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ioskb.export_fts import safe_json_line, stable_fts_id, tier1_score, export


SCRIPT = Path(__file__).parents[1] / "scripts" / "build_fts_v2_import.py"
SPEC = importlib.util.spec_from_file_location("build_fts_v2_import", SCRIPT)
BUILD_FTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_FTS)


class FtsExportTests(unittest.TestCase):
    def test_stable_id_reuses_vector_id(self):
        self.assertTrue(stable_fts_id("notes", "/a.md", 2).startswith("f1-"))
        self.assertTrue(stable_fts_id("notes", "/a.md", 2, True).startswith("v1-"))
        self.assertEqual(stable_fts_id("notes", "/a.md", 2), stable_fts_id("notes", "/a.md", 2))

    def test_tier1_selects_ios_api_and_rejects_noise(self):
        score, reason = tier1_score(
            "/documentation/UIKit/UIViewController.md",
            "UIViewController lifecycle",
            "UIViewController on iOS coordinates UIKit view presentation and appearance callbacks. " * 3,
        )
        self.assertGreater(score, 0)
        self.assertEqual(reason, "selected")
        _, reason = tier1_score("/repo/LICENSE.md", "License", "legal text " * 30)
        self.assertEqual(reason, "metadata_path")
        _, reason = tier1_score(
            "/documentation/Security/Keychain.md",
            "Keychain Services",
            "The iOS Security framework stores credentials in the Keychain. " * 3,
        )
        self.assertEqual(reason, "selected")
        _, reason = tier1_score("/repo/random.md", "misc", "generic server documentation " * 10)
        self.assertEqual(reason, "weak_ios_signal")

    def test_export_preserves_tier0_and_excludes_cards(self):
        con = sqlite3.connect(":memory:")
        con.execute(
            "CREATE TABLE chunks(id INTEGER PRIMARY KEY, source, type, file_path, title_path, "
            "start_line, end_line, text, vectorized)"
        )
        con.executemany(
            "INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?)",
            [
                (1, "core", "doc", "/core.md", "UIKit", 1, 3, "UIKit iOS evidence " * 10, 1),
                (2, "core", "card", "/card.md", "Card", 1, 3, "UIKit iOS card " * 10, 1),
                (3, "bulk", "doc", "/documentation/uikit/api.md", "UIView API", 1, 3, "UIView UIKit iOS API " * 10, 0),
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fts.ndjson"
            manifest = export({}, con, output, tier1_limit=10, per_file_limit=2)
            records = [json.loads(line) for line in output.read_text().splitlines()]
        con.close()
        self.assertEqual(manifest["counts"]["tier0"], 1)
        self.assertEqual(manifest["counts"]["tier1"], 1)
        self.assertEqual([record["tier"] for record in records], [0, 1])
        self.assertNotIn("card", [record["metadata"]["type"] for record in records])

    def test_unicode_separators_and_sql_atomic_table(self):
        line = safe_json_line({"text": "a\u2028b\u2029c"})
        self.assertNotIn("\u2028", line)
        self.assertEqual(json.loads(line)["text"], "a\u2028b\u2029c")
        self.assertNotIn("\u2028", BUILD_FTS.sql("a\u2028b"))
        self.assertIn("ios_ask_fts_v2_next", BUILD_FTS.SCHEMA)
        self.assertIn("ios_ask_fts_v2_neighbors_next", BUILD_FTS.SCHEMA)
        self.assertIn("ios_ask_fts_v2", BUILD_FTS.FINALIZE)
        self.assertNotIn("DROP TABLE IF EXISTS ios_ask_fts;", BUILD_FTS.FINALIZE)

    def test_sql_size_limit(self):
        record = {
            "id": "f1-test", "file_key": "k1-test", "chunk_ordinal": 1,
            "content_hash": "hash", "tier": 1, "metadata": {"text": "UIKit iOS " * 50},
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ndjson"
            source.write_text(json.dumps(record) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                BUILD_FTS.build(source, Path(tmp) / "sql", max_bytes=32)

    def test_generated_sql_executes_and_keeps_neighbor_lookup(self):
        record = {
            "id": "f1-test",
            "file_key": "k1-test",
            "chunk_ordinal": 3,
            "content_hash": "hash",
            "tier": 1,
            "metadata": {
                "source": "bulk",
                "type": "doc",
                "path": "/documentation/UIKit/Test.md",
                "title_path": "UIView",
                "lines": "10-20",
                "text": "UIKit view lifecycle evidence",
                "authority": "official",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ndjson"
            output = Path(tmp) / "sql"
            source.write_text(json.dumps(record) + "\n", encoding="utf-8")
            BUILD_FTS.build(source, output)
            con = sqlite3.connect(":memory:")
            for sql_file in sorted(output.glob("*.sql")):
                con.executescript(sql_file.read_text(encoding="utf-8"))
            self.assertEqual(con.execute("SELECT COUNT(*) FROM ios_ask_fts_v2").fetchone()[0], 1)
            self.assertEqual(
                con.execute(
                    "SELECT fts_rowid FROM ios_ask_fts_v2_neighbors "
                    "WHERE file_key=? AND chunk_ordinal BETWEEN ? AND ?",
                    ("k1-test", 2, 4),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                con.execute(
                    "SELECT chunk_id FROM ios_ask_fts_v2 WHERE ios_ask_fts_v2 MATCH ?",
                    ('"uikit"',),
                ).fetchone()[0],
                "f1-test",
            )
            con.close()

    def test_sql_limit_preserves_tier0_before_truncating_tier1(self):
        base = {
            "id": "v1-core",
            "file_key": "k1-core",
            "chunk_ordinal": 1,
            "content_hash": "core",
            "tier": 0,
            "metadata": {"source": "core", "type": "doc", "text": "UIKit core evidence"},
        }
        extra = {
            **base,
            "id": "f1-extra",
            "file_key": "k1-extra",
            "content_hash": "extra",
            "tier": 1,
            "metadata": {"source": "bulk", "type": "doc", "text": "UIKit extra evidence"},
        }
        minimum = len(BUILD_FTS.SCHEMA.encode()) + len(BUILD_FTS.FINALIZE.encode())
        core_bytes = len(BUILD_FTS.statement(base, 1).encode())
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ndjson"
            source.write_text(
                "\n".join(json.dumps(record) for record in (base, extra)) + "\n",
                encoding="utf-8",
            )
            manifest = BUILD_FTS.build(
                source, Path(tmp) / "sql", max_bytes=minimum + core_bytes
            )
        self.assertEqual(manifest["rows"], 1)
        self.assertEqual(manifest["by_tier"], {"0": 1})
        self.assertEqual(manifest["dropped_for_size"], 1)

    def test_tier1_source_cap_preserves_multiple_fts_sources(self):
        def row(index, source):
            return (
                index,
                source,
                "doc",
                f"/{source}/{index}.md",
                "UIKit API",
                1,
                4,
                f"UIKit iOS UIViewController lifecycle evidence {index} " * 4,
                0,
            )

        con = sqlite3.connect(":memory:")
        con.execute(
            "CREATE TABLE chunks(id INTEGER PRIMARY KEY, source, type, file_path, title_path, "
            "start_line, end_line, text, vectorized)"
        )
        con.executemany(
            "INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?)",
            [row(index, "archive") for index in range(1, 5)]
            + [row(index, "bulk") for index in range(10, 12)],
        )
        with tempfile.TemporaryDirectory() as tmp:
            manifest = export(
                {},
                con,
                Path(tmp) / "fts.ndjson",
                tier1_limit=4,
                per_file_limit=24,
                tier1_per_source_limit=2,
            )
        con.close()
        self.assertEqual(manifest["counts"]["tier1"], 4)
        self.assertEqual(manifest["selected_by_source"]["archive"], 2)
        self.assertEqual(manifest["selected_by_source"]["bulk"], 2)

    def test_total_capacity_preserves_tier0_and_contracts_tier1(self):
        con = sqlite3.connect(":memory:")
        con.execute(
            "CREATE TABLE chunks(id INTEGER PRIMARY KEY, source, type, file_path, title_path, "
            "start_line, end_line, text, vectorized)"
        )
        rows = [
            (
                index,
                "core" if index <= 3 else "bulk",
                "doc",
                f"/{index}.md",
                "UIKit API",
                1,
                4,
                f"UIKit iOS UIViewController lifecycle evidence {index} " * 4,
                1 if index <= 3 else 0,
            )
            for index in range(1, 7)
        ]
        con.executemany("INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?)", rows)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = export(
                {},
                con,
                Path(tmp) / "fts.ndjson",
                tier1_limit=10,
                total_limit=5,
            )
        con.close()
        self.assertEqual(manifest["counts"]["tier0"], 3)
        self.assertEqual(manifest["counts"]["tier1"], 2)
        self.assertEqual(manifest["effective_tier1_limit"], 2)
        self.assertEqual(manifest["counts"]["exported"], 5)

    def test_sql_builder_can_partition_a_large_export_without_overlap(self):
        def record(index):
            return {
                "id": f"f1-{index}",
                "file_key": f"k1-{index}",
                "chunk_ordinal": 1,
                "content_hash": f"hash-{index}",
                "tier": 1,
                "metadata": {"source": "bulk", "type": "doc", "text": "UIKit evidence"},
            }

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.ndjson"
            source.write_text(
                "\n".join(json.dumps(record(index)) for index in range(5)) + "\n",
                encoding="utf-8",
            )
            first = BUILD_FTS.build(source, Path(tmp) / "first", max_rows=3)
            second = BUILD_FTS.build(source, Path(tmp) / "second", start_row=3)
            self.assertEqual(first["rows"], 3)
            self.assertEqual(second["rows"], 2)
            self.assertEqual(first["start_row"], 0)
            self.assertEqual(second["start_row"], 3)


if __name__ == "__main__":
    unittest.main()
