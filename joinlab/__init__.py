"""joinlab: 面向内存行的等值连接工具箱。

当前只提供基于双重循环的 NestedLoopJoin，作为哈希连接、排序归并连接、分块落盘
与多表连接改造前的基线实现。
"""

from joinlab.join import NestedLoopJoin

__all__ = ["NestedLoopJoin"]
