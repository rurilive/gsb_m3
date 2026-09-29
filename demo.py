"""stanza 现状演示。

第一段：用朴素替换器把一个模板里的单个占位符换成上下文取值。
第二段：预留的小模板语言演示位子（见文末注释）。
"""

from stanza.render import Renderer


def main():
    print("=== 朴素行内占位符替换 ===")
    renderer = Renderer({"name": "world"})
    print("  模板 -> hello {{ name }}")
    print("  渲染 -> %s" % renderer.render("hello {{ name }}"))

    # TODO(模板语言改造): 在 stanza 里把单一占位符替换扩成小模板语言之后，
    # 在这里加一段演示：用固定模板与上下文展示条件与循环（条件按真假挑分支、
    # 循环把序列展开并带上循环内变量），再展示子模板继承父模板并覆写命名块，
    # 最后给出渲染结果，确认与预期一致。


if __name__ == "__main__":
    main()
