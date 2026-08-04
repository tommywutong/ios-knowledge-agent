import unittest
from unittest.mock import patch

from ioskb.cards import _source_index, _validate_card
from ioskb.retrieve import search


class FakeEmbedder:
    def encode(self, texts):
        return [[0.0, 0.0]]


class EvidenceBoundaryTests(unittest.TestCase):
    @patch("ioskb.retrieve.db.get_chunks")
    @patch("ioskb.retrieve.db.vec_search")
    @patch("ioskb.retrieve.db.fts_search")
    def test_search_can_exclude_generated_cards(self, fts_search, vec_search, get_chunks):
        fts_search.return_value = [(1, 0, -2.0), (2, 1, -1.0)]
        vec_search.return_value = []
        get_chunks.return_value = {
            1: {
                "id": 1,
                "file_path": "/tmp/card.md",
                "source": "knowledge-cards",
                "type": "card",
                "title_path": "卡片",
                "start_line": 1,
                "end_line": 10,
                "text": "二次总结",
            },
            2: {
                "id": 2,
                "file_path": "/tmp/original.md",
                "source": "notes",
                "type": "note",
                "title_path": "原文",
                "start_line": 20,
                "end_line": 30,
                "text": "原始资料",
            },
        }
        cfg = {
            "retrieval": {
                "fts_top": 10,
                "vector_top": 10,
                "final_top": 8,
                "max_per_file": 2,
                "min_keyword_coverage": 0,
                "type_weights": {"card": 2.0},
            }
        }

        results = search(None, cfg, "问题", exclude_types={"card"})

        self.assertEqual([row["type"] for row in results], ["note"])
        fts_search.assert_called_once_with(None, "问题", 40)

    @patch("ioskb.retrieve.db.get_chunks")
    @patch("ioskb.retrieve.db.vec_search")
    @patch("ioskb.retrieve.db.fts_search")
    def test_search_rejects_weak_vector_and_partial_keyword_match(
        self, fts_search, vec_search, get_chunks
    ):
        fts_search.return_value = [(1, 0, -1.0)]
        vec_search.return_value = [(1, 0, 0.95)]
        get_chunks.return_value = {
            1: {
                "id": 1,
                "file_path": "/资料/番茄工作法.md",
                "source": "blogs",
                "type": "blog",
                "title_path": "番茄工作法",
                "start_line": 1,
                "end_line": 10,
                "text": "番茄计时可以帮助集中注意力。",
            }
        }
        cfg = {
            "retrieval": {
                "fts_top": 10,
                "vector_top": 10,
                "final_top": 8,
                "max_per_file": 2,
                "max_vector_distance": 0.8,
                "min_keyword_coverage": 0.55,
                "type_weights": {},
            }
        }

        self.assertEqual(search(None, cfg, "如何做番茄炒蛋", FakeEmbedder()), [])

    @patch("ioskb.retrieve.db.get_chunks")
    @patch("ioskb.retrieve.db.vec_search")
    @patch("ioskb.retrieve.db.fts_search")
    def test_search_rejects_competing_platform_question(
        self, fts_search, vec_search, get_chunks
    ):
        cfg = {"retrieval": {}}

        self.assertEqual(search(None, cfg, "Android Handler 如何工作", FakeEmbedder()), [])
        fts_search.assert_not_called()
        vec_search.assert_not_called()
        get_chunks.assert_not_called()

    def test_card_source_index_is_programmatically_grounded(self):
        chunks = [
            {
                "file_path": "/资料/RunLoop.md",
                "title_path": "休眠与唤醒",
                "start_line": 12,
                "end_line": 28,
            },
            {
                "file_path": "/源码/CFRunLoop.c",
                "title_path": "__CFRunLoopRun",
                "start_line": 100,
                "end_line": 140,
            },
        ]

        index = _source_index("结论 [2]，背景 [1][2]。", chunks)

        self.assertIn("[1] /资料/RunLoop.md › 休眠与唤醒（第12-28行）", index)
        self.assertIn("[2] /源码/CFRunLoop.c › __CFRunLoopRun（第100-140行）", index)

    def test_card_source_index_rejects_unknown_reference(self):
        with self.assertRaisesRegex(ValueError, "不存在"):
            _source_index(
                "错误引用 [2]",
                [
                    {
                        "file_path": "/资料/a.md",
                        "title_path": "",
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
            )

    def test_card_validation_rejects_unsupported_inference(self):
        content = """# weak
## 一句话总结
结论 [1]。
## 核心原理
原理 [1]。
## 关键细节与易错点
细节 [1]。
## 高频追问
材料中未直接解释，但可以合理推断 [1]。
"""
        with self.assertRaisesRegex(ValueError, "未获材料支持"):
            _validate_card(
                content,
                [
                    {
                        "file_path": "/资料/a.md",
                        "title_path": "",
                        "start_line": 1,
                        "end_line": 2,
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
