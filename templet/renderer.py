"""渲染入口：Engine 持有模板注册表与过滤器表，Context 携带作用域链。"""

from collections import ChainMap

from templet import expr
from templet.errors import TemplateCycleError
from templet.filters import FILTERS
from templet.parser import parse


class Context:
    """一次渲染的上下文：engine 引用 + 变量作用域链。

    push 生成子作用域（for 循环变量），parent 供回退。
    """

    def __init__(self, engine, vars, parent=None, include_depth=0):
        self.engine = engine
        self.vars = vars
        self.parent = parent
        self.include_depth = include_depth

    def resolve(self, name):
        return self.vars.get(name, expr.UNDEFINED)

    def push(self, scope):
        return Context(self.engine, self.vars.new_child(scope), self,
                       self.include_depth)


class Engine:
    """模板引擎：register/render 管理命名模板，render_string 渲染一次性源码。"""

    def __init__(self, autoescape=True, max_include_depth=10):
        self.autoescape = autoescape
        self.max_include_depth = max_include_depth
        self.filters = dict(FILTERS)
        self._templates = {}

    def register(self, name, source):
        """登记命名模板，同名覆盖。"""
        self._templates[name] = source

    def render(self, name, ctx=None):
        """渲染命名模板。未注册的名字抛 KeyError。"""
        if name not in self._templates:
            raise KeyError(name)
        return self.render_string(self._templates[name], ctx)

    def render_string(self, source, ctx=None):
        """解析并渲染一段源码，不进注册表。ctx 是变量字典。"""
        context = Context(self, ChainMap(dict(ctx or {})))
        return self._render_nodes(parse(source), context)

    def render_include(self, name, context):
        """在既有 Context 上展开一个被注册模板：同上下文、不新建作用域。

        未注册沿用注册表的 KeyError；嵌套深度超限抛 TemplateCycleError；
        展开结果原样返回，由 IncludeNode 直接插入、不再二次转义。
        """
        source = self._templates[name]
        depth = context.include_depth + 1
        if depth > self.max_include_depth:
            raise TemplateCycleError(
                "include 深度超过上限 %d（模板 %r）" % (self.max_include_depth, name))
        included = Context(self, context.vars, context, depth)
        return self._render_nodes(parse(source), included)

    def _render_nodes(self, nodes, context):
        out = []
        for node in nodes:
            node.render(out, context)
        return "".join(out)
