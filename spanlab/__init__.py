"""spanlab：序列左右边界的朴素工具箱（纯标准库，无外部依赖）。"""

from .stacks import (
    InvalidInputError,
    NotSpanableError,
    SpanError,
    bounds_greater,
    bounds_smaller,
    count_brute_scans,
    count_subarrays_as_min,
    first_greater_left,
    first_greater_right,
    first_smaller_left,
    first_smaller_right,
    largest_rectangle,
    sum_of_subarray_maxs,
    sum_of_subarray_mins,
)

__all__ = [
    "SpanError",
    "InvalidInputError",
    "NotSpanableError",
    "first_greater_left",
    "first_greater_right",
    "first_smaller_left",
    "first_smaller_right",
    "bounds_greater",
    "bounds_smaller",
    "largest_rectangle",
    "sum_of_subarray_mins",
    "sum_of_subarray_maxs",
    "count_subarrays_as_min",
    "count_brute_scans",
]
