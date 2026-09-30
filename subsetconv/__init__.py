"""集合函数卷积工具包（改造前朴素基线）。"""

from .convolution import (
    ConvolutionError,
    InvalidLengthError,
    LengthMismatchError,
    SetFunction,
    is_power_of_two,
)

__all__ = [
    "ConvolutionError",
    "InvalidLengthError",
    "LengthMismatchError",
    "SetFunction",
    "is_power_of_two",
]
