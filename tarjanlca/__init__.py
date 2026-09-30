"""tarjanlca: 森林上朴素但正确的逐询问标记最近公共祖先。

当前只有每个询问都重标一次端点到根路径的实现，见 tarjanlca/tree.py。
塔扬离线解与逐询问标记的逐项一致性对照，见任务描述。
"""

from tarjanlca.tree import Tree, Erro

__all__ = ["Tree", "Erro"]
