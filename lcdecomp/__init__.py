"""lcdecomp: 树上按深度统计的改造前基线工具。

以 LongChainTree 载入一棵有根树，给出若干深度统计题面的朴素答案。
当前实现用子树节点数定重儿子，且按深度归并时对每棵子树逐结点深搜、
把深度数组逐个复制合并，朴素直观，但规模一大就退化到平方甚至更高量级。
"""

from .core import LongChainTree

__all__ = ["LongChainTree"]
