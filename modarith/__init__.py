"""modarith: 模运算工具集（当前为基线朴素实现）。"""

from modarith.modarith import (
    InverseNotExistsError,
    InvalidCombinationError,
    InvalidModulusError,
    ModarithError,
    NegativeExponentError,
    NoSolutionError,
    NotCoprimeError,
    comb_mod,
    crt,
    mod_inverse,
    mod_pow,
    solve_linear_congruence,
)

__all__ = [
    "InverseNotExistsError",
    "InvalidCombinationError",
    "InvalidModulusError",
    "ModarithError",
    "NegativeExponentError",
    "NoSolutionError",
    "NotCoprimeError",
    "comb_mod",
    "crt",
    "mod_inverse",
    "mod_pow",
    "solve_linear_congruence",
]
