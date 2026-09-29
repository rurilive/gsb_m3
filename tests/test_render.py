"""stanza 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from stanza.render import Renderer, render
from stanza import Renderer as ExportedRenderer


class TestRenderer(unittest.TestCase):
    def test_replaces_single_placeholder(self):
        self.assertEqual(Renderer({"name": "world"}).render("hello {{ name }}"), "hello world")

    def test_replaces_multiple_placeholders(self):
        renderer = Renderer({"a": "1", "b": "2"})
        self.assertEqual(renderer.render("{{ a }}-{{ b }}-{{ a }}"), "1-2-1")

    def test_placeholder_without_spaces(self):
        self.assertEqual(Renderer({"x": "ok"}).render("{{x}}"), "ok")

    def test_missing_key_becomes_empty(self):
        self.assertEqual(Renderer({"x": "ok"}).render("[{{ y }}]"), "[]")

    def test_text_without_placeholders_is_unchanged(self):
        self.assertEqual(Renderer({"x": "ok"}).render("plain text"), "plain text")

    def test_value_is_inserted_verbatim(self):
        renderer = Renderer({"html": "<b>&</b>"})
        self.assertEqual(renderer.render("{{ html }}"), "<b>&</b>")

    def test_non_string_value_is_stringified(self):
        self.assertEqual(Renderer({"n": 42}).render("n={{ n }}"), "n=42")

    def test_context_property_is_a_copy(self):
        renderer = Renderer({"x": "ok"})
        snapshot = renderer.context
        snapshot["x"] = "changed"
        self.assertEqual(renderer.render("{{ x }}"), "ok")

    def test_render_is_repeatable(self):
        renderer = Renderer({"x": "ok"})
        self.assertEqual(renderer.render("{{ x }}"), "ok")
        self.assertEqual(renderer.render("{{ x }}"), "ok")

    def test_module_level_render_helper(self):
        self.assertEqual(render("hi {{ who }}", {"who": "there"}), "hi there")

    def test_module_level_render_defaults_to_empty_context(self):
        self.assertEqual(render("hi {{ who }}"), "hi ")

    def test_package_exports_renderer(self):
        self.assertIs(ExportedRenderer, Renderer)


if __name__ == "__main__":
    unittest.main()
