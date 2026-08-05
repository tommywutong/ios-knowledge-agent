import argparse
import hashlib
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ioskb import freshness
from ioskb.cli import cmd_sync


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "notes"
        self.source.mkdir()
        self.cfg = {
            "sources": [
                {
                    "name": "notes",
                    "path": str(self.source),
                    "type": "note",
                    "include": ["**/*.md"],
                }
            ]
        }
        self.con = sqlite3.connect(":memory:")
        self.con.execute(
            "CREATE TABLE files(path TEXT PRIMARY KEY, source TEXT, hash TEXT, mtime REAL, nchunks INT)"
        )

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    @staticmethod
    def digest(text):
        return hashlib.sha256(text.encode()).hexdigest()

    def add_indexed(self, path, digest, source="notes"):
        self.con.execute(
            "INSERT INTO files VALUES(?,?,?,?,?)", (str(path), source, digest, 0.0, 1)
        )

    def test_lists_added_modified_and_deleted_files(self):
        unchanged = self.source / "unchanged.md"
        modified = self.source / "modified.md"
        added = self.source / "added.md"
        deleted = self.source / "deleted.md"
        unchanged.write_text("same", encoding="utf-8")
        modified.write_text("new", encoding="utf-8")
        added.write_text("added", encoding="utf-8")
        self.add_indexed(unchanged.resolve(), self.digest("same"))
        self.add_indexed(modified.resolve(), self.digest("old"))
        self.add_indexed(deleted.resolve(), self.digest("gone"))

        report = freshness.inspect_freshness(self.cfg, self.con, check_upstreams=False)

        self.assertEqual((report.added, report.modified, report.deleted), (1, 1, 1))
        self.assertEqual(
            {(change.status, Path(change.path).name) for change in report.changes},
            {("added", "added.md"), ("modified", "modified.md"), ("deleted", "deleted.md")},
        )
        self.assertFalse(report.clean)

    def test_missing_source_root_is_unavailable_not_mass_deletion(self):
        missing = self.root / "unmounted"
        cfg = {"sources": [{"name": "notes", "path": str(missing), "type": "note"}]}
        self.add_indexed((missing / "saved.md").resolve(), self.digest("saved"))

        changes = freshness.inspect_sources(cfg, self.con)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].status, "unavailable")
        self.assertNotEqual(changes[0].status, "deleted")

    def test_selected_sources_limit_upstream_discovery(self):
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        cfg = {
            "sources": [
                {"name": "repo-a", "path": str(repo)},
                {"name": "repo-b", "path": str(repo)},
                {"name": "notes", "path": str(self.source)},
            ]
        }
        self.assertEqual(freshness.discover_upstream_repositories(cfg), (repo.resolve(),))
        self.assertEqual(freshness.discover_upstream_repositories(cfg, {"notes"}), ())

    def test_docx_database_key_matches_nested_converted_path(self):
        source = self.source / "nested" / "lesson.docx"
        source.parent.mkdir()
        source.touch()
        with patch.object(freshness, "ROOT", self.root):
            key = freshness.indexed_path_for(self.cfg["sources"][0], source)

        self.assertEqual(
            key,
            str((self.root / "data/converted/notes/nested/lesson.md").resolve()),
        )

    def test_upstream_check_is_read_only_ls_remote_comparison(self):
        calls = []

        def fake_git(repo, *args, timeout=20):
            calls.append(args)
            if args == ("rev-parse", "HEAD"):
                return subprocess.CompletedProcess([], 0, "local\n", "")
            return subprocess.CompletedProcess([], 0, "remote\tHEAD\n", "")

        with patch.object(freshness, "_git", side_effect=fake_git):
            result = freshness.inspect_upstream(self.root)

        self.assertEqual(result.status, "update_available")
        self.assertEqual(calls, [("rev-parse", "HEAD"), ("ls-remote", "origin", "HEAD")])

    def test_upstream_check_reports_matching_heads(self):
        def fake_git(repo, *args, timeout=20):
            output = "same\n" if args == ("rev-parse", "HEAD") else "same\tHEAD\n"
            return subprocess.CompletedProcess([], 0, output, "")

        with patch.object(freshness, "_git", side_effect=fake_git):
            result = freshness.inspect_upstream(self.root)

        self.assertEqual(result.status, "up_to_date")

    def test_pull_refuses_dirty_mirror_before_network(self):
        dirty = subprocess.CompletedProcess([], 0, " M local.md\n", "")
        with patch.object(freshness, "_git", return_value=dirty) as git:
            with self.assertRaises(RuntimeError):
                freshness.pull_upstream(self.root)

        git.assert_called_once_with(self.root, "status", "--porcelain")

    def test_clean_report_serializes_counts(self):
        note = self.source / "same.md"
        note.write_text("same", encoding="utf-8")
        self.add_indexed(note.resolve(), self.digest("same"))

        report = freshness.inspect_freshness(self.cfg, self.con, check_upstreams=False)

        self.assertTrue(report.clean)
        self.assertEqual(
            report.as_dict()["counts"],
            {"added": 0, "modified": 0, "deleted": 0, "unavailable": 0},
        )

    def test_readonly_database_cannot_be_written(self):
        db_path = self.root / "index.sqlite"
        writable = sqlite3.connect(db_path)
        writable.execute("CREATE TABLE sample(value TEXT)")
        writable.commit()
        writable.close()

        con = freshness.open_readonly_db({"db_path": str(db_path)})
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("INSERT INTO sample VALUES('no')")
        con.close()


class SyncSafetyTests(unittest.TestCase):
    def args(self, **overrides):
        values = {
            "source": None,
            "skip_upstreams": True,
            "dry_run": True,
            "pull_upstreams": False,
            "no_embed": False,
            "prepare_cloud": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    @patch("ioskb.cli.cmd_index")
    @patch("ioskb.freshness.inspect_freshness")
    @patch("ioskb.freshness.open_readonly_db")
    @patch("ioskb.cli.load_config")
    def test_dry_run_never_indexes(self, load_config, open_readonly_db, inspect, cmd_index):
        load_config.return_value = {"sources": []}
        inspect.return_value = freshness.FreshnessReport((), ())
        open_readonly_db.return_value.close.return_value = None

        cmd_sync(self.args())

        cmd_index.assert_not_called()

    @patch("ioskb.freshness.open_readonly_db")
    @patch("ioskb.cli.load_config")
    def test_cloud_prepare_rejects_no_embed_before_opening_database(
        self, load_config, open_readonly_db
    ):
        load_config.return_value = {"sources": []}

        with self.assertRaises(SystemExit):
            cmd_sync(self.args(dry_run=False, prepare_cloud=True, no_embed=True))

        open_readonly_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
