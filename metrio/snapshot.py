"""统计快照：排序、分位、聚合口径的唯一出处。

三个导出（text/json/prom）都消费这里的 Snapshot，不再各自算一遍。
"""

from dataclasses import dataclass
from typing import List, Sequence, Union

Number = Union[int, float]


def percentile(sorted_vals: Sequence[Number], p: int) -> Number:
    """最近秩法：第 ceil(p*n/100) 个（1 起数）。空表给 0.0。"""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    k = (p * n + 99) // 100
    if k < 1:
        k = 1
    if k > n:
        k = n
    return sorted_vals[k - 1]


@dataclass(frozen=True)
class CounterSnapshot:
    name: str
    value: int


@dataclass(frozen=True)
class HistogramSnapshot:
    name: str
    count: int
    sum: float
    avg: float
    min: Number
    max: Number
    p50: Number
    p95: Number
    p999: Number

    @classmethod
    def from_samples(cls, name: str, samples: Sequence[Number]) -> "HistogramSnapshot":
        vals = sorted(samples)
        n = len(vals)
        total = float(sum(vals))
        avg = total / n if n > 0 else 0.0
        mn: Number = vals[0] if n > 0 else 0.0
        mx: Number = vals[n - 1] if n > 0 else 0.0
        return cls(
            name=name,
            count=n,
            sum=total,
            avg=avg,
            min=mn,
            max=mx,
            p50=percentile(vals, 50),
            p95=percentile(vals, 95),
            p999=percentile(vals, 999),
        )


@dataclass(frozen=True)
class Snapshot:
    counters: List[CounterSnapshot]
    histograms: List[HistogramSnapshot]
