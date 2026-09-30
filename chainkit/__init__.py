"""chainkit：矩阵连乘的最优括号化与派生问题的工具箱。

当前对外能力是一组朴素函数：算区间最少乘法次数、给一个最优括号化、数最优
方案个数、在括号串与方案之间来回。递推求值、重建并列口径、计数递推这些都
留待在这个基础上补齐。
"""

from .chain import (
    ChainError,
    check_dims,
    naive_cost,
    naive_count,
    naive_optimal,
    naive_plan_cost,
    parse_plan,
    plan_to_string,
    whole_cost,
    whole_count,
    whole_optimal,
)

__all__ = [
    "ChainError",
    "check_dims",
    "naive_cost",
    "naive_count",
    "naive_optimal",
    "naive_plan_cost",
    "parse_plan",
    "plan_to_string",
    "whole_cost",
    "whole_count",
    "whole_optimal",
]
