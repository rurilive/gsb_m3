"""unionx: 内存里的朴素连通判定。

当前只有邻接表加广度优先遍历的实现，见 unionx/graph.py。
带路径压缩与按秩合并的并查集、组件统计、撤销回滚、带权关系与离线
批量查询见任务描述。
"""

from unionx.graph import NaiveUnionFind, UnknownNode

__all__ = ["NaiveUnionFind", "UnknownNode"]
