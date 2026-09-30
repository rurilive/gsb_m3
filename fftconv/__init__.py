"""fftconv: 多项式乘法工具。

当前只有朴素实现，见 fftconv/conv.py。两个多项式相乘用双重循环逐对系数
相乘再按幂次累加，复杂度是两个长度的乘积，规模一大就上到平方量级。配套的
求值、由根构造、配对校验与模数、长度校验也都是最直白的写法。

改用迭代版快速傅里叶变换做点值相乘再逆变换，用模素数下的数论变换或整数
拆分的卷积做独立印证，以及边界与确定性要求，见任务描述。
"""

from fftconv.conv import (
    Erro,
    IllegalArgument,
    IllegalLength,
    IllegalModulus,
    PointMismatch,
    Poly,
    check_coeffs,
    check_modulus,
    check_pointwise,
    check_transform_length,
    convolve_naive,
    evaluate_many,
    from_roots,
    is_power_of_two,
    is_prime,
    result_length,
    trim,
)

__all__ = [
    "Erro",
    "IllegalArgument",
    "IllegalLength",
    "IllegalModulus",
    "PointMismatch",
    "Poly",
    "check_coeffs",
    "check_modulus",
    "check_pointwise",
    "check_transform_length",
    "convolve_naive",
    "evaluate_many",
    "from_roots",
    "is_power_of_two",
    "is_prime",
    "result_length",
    "trim",
]
