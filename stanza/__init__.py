"""stanza：纯标准库的模板渲染小包。

当前只导出基线占位符替换器 Renderer 与便捷函数 render。
"""

from stanza.render import Renderer, render

__all__ = ["Renderer", "render"]
