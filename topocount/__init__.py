"""topocount: 有向无环图上的拓扑序计数，当前只有最朴素的全排列枚举。

枚举全部顶点排列逐个校验每条边的方向，判是否存在拓扑序、数拓扑序个数、
挑字典序最小的拓扑序都靠这一条路，阶乘量级，见 topocount/dag.py。
升级方向见任务描述与 README。
"""

from topocount.dag import (
    TopoCountError,
    InvalidGraphError,
    NodeNotFoundError,
    DAGCounter,
    brute_permutations,
)

__all__ = [
    "TopoCountError",
    "InvalidGraphError",
    "NodeNotFoundError",
    "DAGCounter",
    "brute_permutations",
]
