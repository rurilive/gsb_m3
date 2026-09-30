"""crtkit：同余方程组工具集（当前为基线朴素试值实现）。"""

from crtkit.crtkit import (
    CrtkitError,
    EmptySystemError,
    InvalidBoundsError,
    InvalidModulusError,
    InvalidRangeError,
    NoSolutionError,
    count_in_range,
    count_search_steps,
    has_solution,
    normalize_modulus,
    normalize_residue,
    search_first_solution,
    smallest_non_negative,
    solve,
    solutions_in_range,
)

__all__ = [
    "CrtkitError",
    "EmptySystemError",
    "InvalidBoundsError",
    "InvalidModulusError",
    "InvalidRangeError",
    "NoSolutionError",
    "count_in_range",
    "count_search_steps",
    "has_solution",
    "normalize_modulus",
    "normalize_residue",
    "search_first_solution",
    "smallest_non_negative",
    "solve",
    "solutions_in_range",
]
