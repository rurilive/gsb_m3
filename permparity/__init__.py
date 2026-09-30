"""permparity: 排列的逆序数、奇偶性与置换分解，当前只有最朴素的两两比较口径。

逆序数靠两两比较全部数对，奇偶性看逆序数的奇偶，循环分解靠反复标记，
最少交换次数靠反复查找，置换复合靠逐位搬，平方量级，规模一大就慢，
见 permparity/perm.py。升级方向见任务描述与 README。
"""

from permparity.perm import (
    PermParityError,
    InvalidPermutationError,
    UnsupportedElementError,
    validate_perm,
    inversion_count,
    parity,
    is_even,
    cycle_decomposition,
    min_swaps,
    cycle_type,
    parity_by_cycles,
    compose,
    compose_parity,
    can_swap,
    min_swaps_between,
)

__all__ = [
    "PermParityError",
    "InvalidPermutationError",
    "UnsupportedElementError",
    "validate_perm",
    "inversion_count",
    "parity",
    "is_even",
    "cycle_decomposition",
    "min_swaps",
    "cycle_type",
    "parity_by_cycles",
    "compose",
    "compose_parity",
    "can_swap",
    "min_swaps_between",
]
