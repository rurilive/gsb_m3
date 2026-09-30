"""pathcount：有向图定长路径计数，纯标准库，无外部依赖。

当前对外能力是一份朴素实现：恰好走某步数的走法数靠逐层深度搜索把每一条
走法整条枚举出来再计数，两点之间的全部路径同样靠枚举，长度不超过某上界的
走法数对每个长度分别枚举再累加，回路按长度从小到大枚举判定存在与最短，
矩阵乘法用三重循环、矩阵幂把同一个矩阵逐次相乘。步数或点数一多就指数乃至
立方量级地退下去。基于邻接矩阵快速幂的对数级路径计数、两路逐项对照、以
及更完整的边界覆盖，都留待在这个基础上补齐。
"""

from .count import (
    DirectedGraph,
    GraphErro,
    PathCounter,
    PathErro,
    WalkerErro,
    mat_mul,
    mat_pow,
)

__all__ = [
    "DirectedGraph",
    "GraphErro",
    "PathCounter",
    "PathErro",
    "WalkerErro",
    "mat_mul",
    "mat_pow",
]
