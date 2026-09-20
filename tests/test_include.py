"""{% include %} 节点的行为测试。"""

import unittest

from templet import Engine, TemplateCycleError, TemplateError, TemplateSyntaxError


def make_engine(mapping, **kw):
    engine = Engine(**kw)
    for name, source in mapping.items():
        engine.register(name, source)
    return engine


class TestIncludeBasic(unittest.TestCase):
    def test_include_expands_registered_template(self):
        engine = make_engine({"frag.html": "<em>{{ word }}</em>"})
        out = engine.render_string('A{% include "frag.html" %}B', {"word": "hi"})
        self.assertEqual(out, "A<em>hi</em>B")

    def test_include_via_render_named_template(self):
        engine = make_engine({
            "page.html": 'H{% include "frag.html" %}F',
            "frag.html": "-",
        })
        self.assertEqual(engine.render("page.html"), "H-F")

    def test_missing_template_raises_keyerror(self):
        engine = make_engine({})
        with self.assertRaises(KeyError):
            engine.render_string('{% include "nope.html" %}')

    def test_include_output_not_double_escaped(self):
        engine = make_engine({"frag.html": "{{ v }}"})
        out = engine.render_string('{% include "frag.html" %}', {"v": "<b>"})
        self.assertEqual(out, "&lt;b&gt;")

    def test_include_sees_render_variables(self):
        engine = make_engine({"frag.html": "[{{ outer }}]"})
        out = engine.render_string('{% include "frag.html" %}', {"outer": "x"})
        self.assertEqual(out, "[x]")

    def test_nested_include_sees_outer_variables(self):
        engine = make_engine({
            "inner.html": "{{ user.name }}@{{ loop_var }}",
            "outer.html": '{% for loop_var in seq %}{% include "inner.html" %};{% endfor %}',
        })
        out = engine.render_string(
            '{% include "outer.html" %}',
            {"user": {"name": "tom"}, "seq": [1, 2]},
        )
        self.assertEqual(out, "tom@1;tom@2;")

    def test_include_inside_for_sees_loop_variable(self):
        engine = make_engine({"row.html": "<{{ x }}>"})
        out = engine.render_string(
            '{% for x in items %}{% include "row.html" %}{% endfor %}',
            {"items": ["a", "b"]},
        )
        self.assertEqual(out, "<a><b>")


class TestIncludeDepth(unittest.TestCase):
    def test_cycle_error_is_template_error(self):
        self.assertTrue(issubclass(TemplateCycleError, TemplateError))

    def test_direct_recursion_raises_cycle_error(self):
        engine = make_engine({"a.html": '{% include "a.html" %}'})
        with self.assertRaises(TemplateCycleError):
            engine.render("a.html")

    def test_indirect_recursion_raises_cycle_error(self):
        engine = make_engine({
            "a.html": '{% include "b.html" %}',
            "b.html": '{% include "a.html" %}',
        })
        with self.assertRaises(TemplateCycleError):
            engine.render("a.html")

    def test_chain_at_depth_limit_passes(self):
        engine = make_engine({
            "a.html": 'A{% include "b.html" %}',
            "b.html": 'B{% include "c.html" %}',
            "c.html": "C",
        }, max_include_depth=2)
        self.assertEqual(engine.render("a.html"), "ABC")

    def test_chain_beyond_depth_limit_raises(self):
        engine = make_engine({
            "a.html": '{% include "b.html" %}',
            "b.html": '{% include "c.html" %}',
            "c.html": '{% include "d.html" %}',
            "d.html": "D",
        }, max_include_depth=2)
        with self.assertRaises(TemplateCycleError):
            engine.render("a.html")

    def test_default_depth_limit_allows_reasonable_nesting(self):
        mapping = {"t0.html": "end"}
        for i in range(1, 8):
            mapping["t%d.html" % i] = '{%% include "t%d.html" %%}' % (i - 1)
        engine = make_engine(mapping)
        self.assertEqual(engine.render("t7.html"), "end")


class TestIncludeSyntax(unittest.TestCase):
    def test_single_quoted_name_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include 'a.html' %}")

    def test_bare_name_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include a %}")

    def test_missing_argument_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include %}")

    def test_extra_argument_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string('{% include "a.html" extra %}')


if __name__ == "__main__":
    unittest.main()
