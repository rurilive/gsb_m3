"""统计口径层：把注册表的原始状态收敛成一份不可变快照。

排序、求和、最近秩法分位只在这里实现一次；三种导出共用这份快照，
渲染层不再各自算统计量。快照不带任何格式逻辑，可独立单测。
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CounterSnapshot:
    """一个计数器在某一时刻的只读视图。"""

    name: str
    value: int


@dataclass(frozen=True)
class HistogramSnapshot:
    """一个直方图在某一时刻的统计口径（三种导出共用）。

    min/max/分位保留样本原始数值（不强制 float），以保证 JSON
    输出与历史行为逐字节一致；格式化只发生在渲染层。
    """

    name: str
    count: int
    sum: float
    avg: float
    min: float
    max: float
    p50: float
    p95: float
    p999: float


@dataclass(frozen=True)
class Snapshot:
    """整个注册表某一时刻的只读视图，按注册顺序排列。"""

    counters: tuple[CounterSnapshot, ...]
    histograms: tuple[HistogramSnapshot, ...]


def percentile(sorted_values: Sequence[float], p: int) -> float:
    """最近秩法分位：第 ceil(p*n/100) 个（1 起数），空表返回 0.0。

    与历史的 `(p*n + 99) // 100`（text/prom）和
    `math.ceil(n*p/100.0)`（json）等价，这里用整数运算一份实现。
    """

    n = len(sorted_values)
    if n == 0:
        return 0.0
    k = (p * n + 99) // 100
    if k < 1:
        k = 1
    if k > n:
        k = n
    return sorted_values[k - 1]


def histogram_snapshot(name: str, samples: Sequence[float]) -> HistogramSnapshot:
    """从原始样本列表算出一个直方图的全部统计量。"""

    values = sorted(samples)
    n = len(values)
    total = sum(values)
    total_f = float(total)
    return HistogramSnapshot(
        name=name,
        count=n,
        sum=total_f,
        avg=(total_f / n) if n > 0 else 0.0,
        min=values[0] if n > 0 else 0.0,
        max=values[n - 1] if n > 0 else 0.0,
        p50=percentile(values, 50),
        p95=percentile(values, 95),
        p999=percentile(values, 999),
    )


def build_snapshot(
    counters: dict[str, int],
    counter_order: Sequence[str],
    histograms: dict[str, list[float]],
    histogram_order: Sequence[str],
) -> Snapshot:
    """从注册表的原始状态构建快照（保留注册顺序）。"""

    return Snapshot(
        counters=tuple(
            CounterSnapshot(name=name, value=counters[name])
            for name in counter_order
        ),
        histograms=tuple(
            histogram_snapshot(name, histograms[name])
            for name in histogram_order
        ),
    )
