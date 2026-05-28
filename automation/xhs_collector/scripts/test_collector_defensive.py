#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""畸形 API 载荷回归测试 — 任何输入均不得抛异常。"""

import unittest

import collector as c


class TestDefensiveHelpers(unittest.TestCase):
    def test_safe_dict(self):
        self.assertEqual(c.safe_dict({"a": 1}), {"a": 1})
        self.assertEqual(c.safe_dict(None), {})
        self.assertEqual(c.safe_dict([]), {})

    def test_safe_list(self):
        self.assertEqual(c.safe_list([1]), [1])
        self.assertEqual(c.safe_list(None), [])
        self.assertEqual(c.safe_list("x"), [])

    def test_parse_json_payload(self):
        self.assertEqual(c.parse_json_payload('{"a":1}'), {"a": 1})
        self.assertEqual(c.parse_json_payload({"a": 1}), {"a": 1})
        self.assertIsNone(c.parse_json_payload("not json"))
        self.assertIsNone(c.parse_json_payload(None))
        self.assertIsNone(c.parse_json_payload(123))

    def test_safe_get_nested(self):
        self.assertEqual(c.safe_get_nested({"a": {"b": 1}}, "a", "b"), 1)
        self.assertEqual(c.safe_get_nested({"a": None}, "a", "b", default="x"), "x")
        self.assertEqual(c.safe_get_nested(None, "a", default="x"), "x")


class TestCallCozeWorkflow(unittest.TestCase):
    def test_malformed_api_body(self):
        cases = [
            None,
            [],
            "",
            {"code": 0, "data": {"already": "dict"}},
            {"code": 0, "data": "not-json"},
            {"code": 1, "msg": "err"},
        ]
        for body in cases:
            with self.subTest(body=body):
                out = c.normalize_workflow_response(body)
                # must not raise; dict or None only
                self.assertTrue(out is None or isinstance(out, dict))


class TestSearchNotes(unittest.TestCase):
    def test_bad_shapes(self):
        for data in [None, {}, {"output": None}, {"output": {}}, {"output": {"items": None}}]:
            with self.subTest(data=data):
                items = c.extract_search_items(data)
                self.assertIsInstance(items, list)


class TestParseNoteDetail(unittest.TestCase):
    def test_bad_shapes(self):
        cases = [
            None,
            {},
            {"data": None},
            {"data": 123},
            {"data": "not-json"},
            {"data": "{}\n"},
            {"data": '[{"fields": null}]\n[]'},
            {"data": '[{"fields": {"标题": "t"}}]\n{"comments": null}'},
            {"data": '[{"fields": {"标题": "t"}}]\n{"comments": [{"user_info": null}]}'},
        ]
        for detail in cases:
            with self.subTest(detail=detail):
                result = c.parse_note_detail(detail)
                self.assertIsInstance(result, dict)
                for key in c.NOTE_DETAIL_DEFAULTS:
                    self.assertIn(key, result)


class TestGenerateMarkdown(unittest.TestCase):
    def test_sparse_notes(self):
        md = c.generate_markdown("kw", [{}], "2026-01-01")
        self.assertIn("小红书爆款采集", md)

    def test_none_fields(self):
        notes = [{"title": None, "author": None, "comments": None}]
        md = c.generate_markdown("kw", notes, "2026-01-01")
        self.assertIsInstance(md, str)


class TestBuildNoteFromSearchItem(unittest.TestCase):
    def test_garbage_item(self):
        for item in [None, {}, {"note_card": None}, {"url": None}]:
            with self.subTest(item=item):
                detail, url = c.build_fallback_detail_from_item(item)
                self.assertIsInstance(detail, dict)
                self.assertTrue(url is None or isinstance(url, str))


if __name__ == "__main__":
    unittest.main()
