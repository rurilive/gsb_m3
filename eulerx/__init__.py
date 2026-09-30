"""eulerx: 一笔画工具的朴素基线（改造前）。

对外只暴露朴素多重图与那一层阶乘量级的枚举求解，以及错误基类。
"""

from .graph import (
    EmptyEdgeError,
    EulerError,
    UnknownVertexError,
    chain_count,
    enumerate_edge_orders,
    has_euler_circuit_undirected,
    has_euler_path_directed,
    has_euler_path_undirected,
    itoa,
    make_directed,
    make_undirected,
    naive_edge_order_check_count,
    naive_euler_circuit_undirected,
    naive_euler_path_directed,
    naive_euler_path_undirected,
)

__all__ = [
    "EulerError",
    "UnknownVertexError",
    "EmptyEdgeError",
    "make_undirected",
    "make_directed",
    "has_euler_path_undirected",
    "has_euler_circuit_undirected",
    "has_euler_path_directed",
    "naive_euler_path_undirected",
    "naive_euler_circuit_undirected",
    "naive_euler_path_directed",
    "naive_edge_order_check_count",
    "enumerate_edge_orders",
    "chain_count",
    "itoa",
]
