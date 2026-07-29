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
        fts_search.return_value = [(1, 0), (2, 1)]
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
                "type_weights": {"card": 2.0},
            }
        }

        results = search(None, cfg, "问题", exclude_types={"card"})

        self.assertEqual([row["type"] for row in results], ["note"])
        fts_search.assert_called_once_with(None, "问题", 40)

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
