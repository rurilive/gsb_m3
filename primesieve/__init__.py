"""primesieve: 素数筛与整数分解的朴素实现。

当前只有逐数试除的一路实现，见 primesieve/sieve.py。
线性时间筛出素数并顺带记录每个数的最小质因子、以及对数级快速分解
见任务描述。
"""

from primesieve.sieve import Erro, NumberRangeError, Sieve, ValueTypeError

__all__ = ["Erro", "NumberRangeError", "ValueTypeError", "Sieve"]
