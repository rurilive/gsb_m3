"""stanza 的最朴素实现：一个行内占位符替换器。

现状只有单一的占位符替换：模板文本里形如双大括号的行内占位符，会被替换成
上下文里对应键的取值。没有条件、没有循环、没有继承、没有转义，也没有把模板
编译成可复用语法的能力。每次渲染都从头扫一遍文本。
"""

import re

# 只认 {{ name }} 这种行内占位符，键名限定为字母、数字、下划线。
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class Renderer(object):
    """最朴素的行内占位符替换器。

    构造时给定一个上下文字典，render 时把模板里每个双大括号占位符换成上下文
    里同名键的取值。缺键时按空串处理，取值原样插入，不做任何转义。
    """

    def __init__(self, context=None):
        self._context = dict(context) if context else {}

    @property
    def context(self):
        """当前上下文的一份拷贝。"""
        return dict(self._context)

    def render(self, template):
        """把 template 里的占位符逐个替换成上下文取值，返回结果字符串。"""

        def replace(match):
            name = match.group(1)
            return str(self._context.get(name, ""))

        return _PLACEHOLDER.sub(replace, template)


def render(template, context=None):
    """一次性渲染的便捷函数：等价于 Renderer(context).render(template)。"""
    return Renderer(context).render(template)
