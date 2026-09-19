"""注册表：指标状态收进 Registry 实例，模块级函数只是默认实例的薄壳。"""

from typing import Dict, List

from metrio.snapshot import CounterSnapshot, HistogramSnapshot, Number, Snapshot


class Registry:
    """一份独立的指标状态：计数器、直方图及各自的注册顺序。"""

    def __init__(self) -> None:
        self.counters: Dict[str, int] = {}
        self.histos: Dict[str, List[Number]] = {}
        self.order_c: List[str] = []
        self.order_h: List[str] = []

    def inc(self, name: str, n: int = 1) -> int:
        if not isinstance(n, int):
            raise TypeError("inc expects an int n, got %r" % (n,))
        if name not in self.counters:
            self.counters[name] = 0
            self.order_c.append(name)
        self.counters[name] = self.counters[name] + n
        return self.counters[name]

    def counter_value(self, name: str, default: int = 0) -> int:
        if name in self.counters:
            return self.counters[name]
        return default

    def histogram(self, name: str) -> None:
        if name not in self.histos:
            self.histos[name] = []
            self.order_h.append(name)

    def observe(self, name: str, value: Number) -> None:
        if name not in self.histos:
            self.histos[name] = []
            self.order_h.append(name)
        self.histos[name].append(value)

    def snapshot(self) -> Snapshot:
        return Snapshot(
            counters=[CounterSnapshot(name, self.counters[name]) for name in self.order_c],
            histograms=[
                HistogramSnapshot.from_samples(name, self.histos[name])
                for name in self.order_h
            ],
        )

    def reset(self) -> None:
        self.counters.clear()
        self.histos.clear()
        del self.order_c[:]
        del self.order_h[:]
