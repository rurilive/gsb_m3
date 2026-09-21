"""scrape 的行为基线：锁住正则版提取的对外语义与已知局限。

这里的断言描述的是现状，不是理想状态。逐条对应 README 的"已知局限"：
实现新解析器时不要改这个文件，也不要顺手"修"出不一样的结果。
"""

import unittest

from taglens import (BadTagName, TaglensError, extract_all, extract_text,
                     find_all, find_first, get_attr, inner_html, strip_tags)

PAGE = '''<!DOCTYPE html>
<html lang="zh">
<body>
  <h1 id="title">抓取小工具</h1>
  <div class="card">
    <p>第一段 <b>加粗</b> 收尾</p>
    <p class="note">第二段 &amp; 实体</p>
  </div>
  <!-- 注释里也塞了一对 <p>假段落</p> -->
</body>
</html>
'''

NESTED = '<div id="outer"><div id="inner">内层</div>尾部</div>'
TRICKY_ATTR = '<a title="1 > 2" href="/x">去</a>'


class ExtractTextTest(unittest.TestCase):
    def test_first_match_only(self):
        self.assertEqual(extract_text(PAGE, "p"), "第一段 加粗 收尾")

    def test_case_insensitive(self):
        self.assertEqual(extract_text(PAGE, "H1"), "抓取小工具")

    def test_entities_and_whitespace(self):
        self.assertEqual(extract_text(PAGE, "p"), "第一段 加粗 收尾")
        self.assertEqual(extract_all(PAGE, "p")[1], "第二段 & 实体")

    def test_empty_element(self):
        self.assertEqual(extract_text("<p></p>", "p"), "")

    def test_missing_tag(self):
        self.assertIsNone(extract_text(PAGE, "h2"))

    def test_unclosed_tag_is_absent(self):
        # 已知局限：找不到闭合标签就当没有
        self.assertIsNone(extract_text("<p>没闭合就走", "p"))


class ExtractAllTest(unittest.TestCase):
    def test_document_order(self):
        self.assertEqual(
            extract_all(PAGE, "p"),
            ["第一段 加粗 收尾", "第二段 & 实体", "假段落"])

    def test_comment_blind(self):
        # 已知局限：不认注释，注释里的同名标签照样算
        self.assertIn("假段落", extract_all(PAGE, "p"))

    def test_none_found(self):
        self.assertEqual(extract_all(PAGE, "section"), [])


class FindTest(unittest.TestCase):
    def test_find_first_returns_slices(self):
        attrs, inner = find_first(PAGE, "div")
        self.assertEqual(attrs, ' class="card"')
        self.assertIn("第一段", inner)

    def test_find_all_order(self):
        got = find_all(PAGE, "p")
        self.assertEqual(len(got), 3)
        self.assertEqual(got[1][1], "第二段 &amp; 实体")

    def test_nested_same_tag_stops_early(self):
        # 已知局限：非贪婪在内层闭合处收工
        self.assertEqual(extract_text(NESTED, "div"), "内层")

    def test_tricky_attribute_truncates(self):
        # 已知局限：属性值里的 > 截断开始标签，属性与正文一起错位
        attrs, inner = find_first(TRICKY_ATTR, "a")
        self.assertEqual(attrs, ' title="1 ')
        self.assertEqual(inner, ' 2" href="/x">去')


class InnerHtmlTest(unittest.TestCase):
    def test_raw_inner(self):
        self.assertEqual(inner_html(PAGE, "p"), "第一段 <b>加粗</b> 收尾")

    def test_missing(self):
        self.assertIsNone(inner_html(PAGE, "h3"))


class AttrTest(unittest.TestCase):
    def test_quoted_value(self):
        self.assertEqual(get_attr(PAGE, "h1", "id"), "title")

    def test_absent_value(self):
        self.assertIsNone(get_attr(PAGE, "p", "class"))

    def test_only_first_match(self):
        self.assertIsNone(get_attr(PAGE, "div", "id"))

    def test_entity_in_value(self):
        got = get_attr('<a href="/x?a=1&amp;b=2">去</a>', "a", "href")
        self.assertEqual(got, "/x?a=1&b=2")

    def test_empty_name(self):
        with self.assertRaises(TypeError):
            get_attr(PAGE, "a", "")


class StripTagsTest(unittest.TestCase):
    def test_removes_markup_only(self):
        self.assertEqual(strip_tags("<p>a<b>b</b></p>"), "ab")

    def test_keeps_entities_and_space(self):
        self.assertEqual(strip_tags("a &amp; b"), "a &amp; b")

    def test_bad_type(self):
        with self.assertRaises(TypeError):
            strip_tags(None)


class ErrorTest(unittest.TestCase):
    def test_bad_tag_names(self):
        for bad in ("", "1p", "p body", "p!"):
            with self.assertRaises(BadTagName):
                extract_text(PAGE, bad)

    def test_bad_tag_name_carries_tag(self):
        try:
            extract_text(PAGE, "1p")
        except TaglensError as exc:
            self.assertIsInstance(exc, ValueError)
            self.assertEqual(exc.tag, "1p")
        else:
            self.fail("应当抛 BadTagName")

    def test_html_type(self):
        with self.assertRaises(TypeError):
            extract_text(None, "p")

    def test_tag_type(self):
        with self.assertRaises(TypeError):
            extract_text(PAGE, 3)


if __name__ == "__main__":
    unittest.main()
