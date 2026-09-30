"""offx: 序列上的离线区间查询基线。

当前只提供一份逐查询现场重扫的离线批处理 QueryBatch，作为离线排序与
增量结构（树状数组、莫队或分块）改造前的基线。
"""

from offx.batch import QueryBatch

__all__ = ["QueryBatch"]
