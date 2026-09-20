"""include 节点的行为测试：展开、上下文共享、递归与深度边界。"""

import unittest

from templet import Engine, TemplateCycleError, TemplateError, TemplateSyntaxError


class TestInclude(unittest.TestCase):
    def test_include_expands_registered_template(self):
        e = Engine()
        e.register("header.html", "<header>{{ title }}</header>")
        self.assertEqual(
            e.render_string('{% include "header.html" %}', {"title": "首页"}),
            "<header>首页</header>")

    def test_include_inside_named_template(self):
        e = Engine()
        e.register("part.html", "P")
        e.register("page.html", '[{% include "part.html" %}]')
        self.assertEqual(e.render("page.html"), "[P]")

    def test_include_shares_outer_variables(self):
        e = Engine()
        e.register("snippet.html", "{{ user.name }}/{{ user.age }}")
        out = e.render_string('{% include "snippet.html" %}',
                              {"user": {"name": "Tom", "age": 7}})
        self.assertEqual(out, "Tom/7")

    def test_nested_include_sees_outer_for_variable(self):
        e = Engine()
        e.register("row.html", "<{{ i }}>")
        out = e.render_string(
            '{% for i in items %}{% include "row.html" %}{% endfor %}',
            {"items": [1, 2, 3]})
        self.assertEqual(out, "<1><2><3>")

    def test_nested_include_sees_grandparent_variables(self):
        e = Engine()
        e.register("inner.html", "{{ outer }}/{{ middle }}")
        e.register("outer.html", '{% for middle in xs %}{% include "inner.html" %};{% endfor %}')
        e.register("page.html", '{% include "outer.html" %}')
        out = e.render("page.html", {"outer": "O", "xs": ["a", "b"]})
        self.assertEqual(out, "O/a;O/b;")

    def test_included_output_not_double_escaped(self):
        e = Engine()
        e.register("raw.html", "<b>粗体 &amp; 实体</b>")
        out = e.render_string('{% include "raw.html" %}')
        self.assertEqual(out, "<b>粗体 &amp; 实体</b>")

    def test_included_variable_still_autoescaped(self):
        e = Engine()
        e.register("v.html", "{{ v }}")
        out = e.render_string('{% include "v.html" %}', {"v": "<i>&"})
        self.assertEqual(out, "&lt;i&gt;&amp;")

    def test_missing_template_raises_keyerror(self):
        e = Engine()
        try:
            e.render_string('{% include "nope.html" %}')
        except KeyError as exc:
            self.assertEqual(exc.args[0], "nope.html")
        else:
            self.fail("未注册模板应抛 KeyError")

    def test_direct_recursion_raises_cycle_error(self):
        e = Engine()
        e.register("self.html", 'S{% include "self.html" %}')
        with self.assertRaises(TemplateCycleError):
            e.render("self.html")

    def test_indirect_recursion_raises_cycle_error(self):
        e = Engine()
        e.register("a.html", 'A{% include "b.html" %}')
        e.register("b.html", 'B{% include "c.html" %}')
        e.register("c.html", 'C{% include "a.html" %}')
        with self.assertRaises(TemplateCycleError):
            e.render("a.html")

    def test_default_max_include_depth_is_10(self):
        self.assertEqual(Engine().max_include_depth, 10)

    def test_depth_boundary_at_limit_passes(self):
        e = Engine(max_include_depth=3)
        e.register("t3.html", "end")
        e.register("t2.html", '2{% include "t3.html" %}')
        e.register("t1.html", '1{% include "t2.html" %}')
        e.register("t0.html", '0{% include "t1.html" %}')
        self.assertEqual(e.render("t0.html"), "012end")

    def test_depth_boundary_exceeded_raises_cycle_error(self):
        e = Engine(max_include_depth=3)
        e.register("t4.html", "end")
        e.register("t3.html", '3{% include "t4.html" %}')
        e.register("t2.html", '2{% include "t3.html" %}')
        e.register("t1.html", '1{% include "t2.html" %}')
        e.register("t0.html", '0{% include "t1.html" %}')
        with self.assertRaises(TemplateCycleError):
            e.render("t0.html")

    def test_sibling_includes_do_not_accumulate_depth(self):
        e = Engine(max_include_depth=2)
        e.register("leaf.html", "L")
        e.register("branch.html", 'B{% include "leaf.html" %}')
        e.register("page.html",
                   '{% include "branch.html" %}|{% include "branch.html" %}')
        self.assertEqual(e.render("page.html"), "BL|BL")

    def test_cycle_error_inherits_template_error(self):
        self.assertTrue(issubclass(TemplateCycleError, TemplateError))

    def test_single_quoted_arg_rejected(self):
        with self.assertRaises(TemplateSyntaxError):
            Engine().render_string("{% include 'a.html' %}")

    def test_bad_include_syntax_rejected(self):
        for bad in ("{% include %}",
                    '{% include "a.html" extra %}',
                    '{% include a.html %}',
                    '{% include 123 %}',
                    '{% include "a.html" "b.html" %}'):
            with self.assertRaises(TemplateSyntaxError):
                Engine().render_string(bad)


if __name__ == "__main__":
    unittest.main()
