"""注册表：计数器/直方图的状态全部收在实例里，不再有模块级可变 dict。

模块级函数（meters.py）只是默认实例上的薄壳转发；下个版本加标签维度时，
按 key 组合（名称 + 标签）在本类里扩展即可，导出侧不用动。
"""

from collections.abc import Sequence

from metrio.snapshot import Snapshot, build_snapshot


class Registry:
    """进程内指标注册表（注册顺序即导出顺序）。"""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}
        self._counter_order: list[str] = []
        self._histogram_order: list[str] = []

    def inc(self, name: str, n: int = 1) -> int:
        """计数器加 n。n 允许负数（历史行为：不拦）。返回加完的值。"""

        if not isinstance(n, int):
            raise TypeError("inc expects an int n, got %r" % (n,))
        if name not in self._counters:
            self._counters[name] = 0
            self._counter_order.append(name)
        self._counters[name] = self._counters[name] + n
        return self._counters[name]

    def counter_value(self, name: str, default: int = 0) -> int:
        """读计数器当前值，没注册过返回 default。"""

        return self._counters.get(name, default)

    def histogram(self, name: str) -> None:
        """注册一个空直方图（后面 observe 往里灌样本）。"""

        if name not in self._histograms:
            self._histograms[name] = []
            self._histogram_order.append(name)

    def observe(self, name: str, value: float) -> None:
        """往直方图里记一个样本。没注册过会顺手注册（历史行为）。"""

        if name not in self._histograms:
            self._histograms[name] = []
            self._histogram_order.append(name)
        self._histograms[name].append(value)

    def histogram_samples(self, name: str) -> Sequence[float]:
        """只读访问某直方图的原始样本（快照计算用）。"""

        return self._histograms[name]

    def snapshot(self) -> Snapshot:
        """对当前状态做一份不可变统计快照（快照→渲染管线的起点）。"""

        return build_snapshot(
            self._counters,
            self._counter_order,
            self._histograms,
            self._histogram_order,
        )

    def reset(self) -> None:
        """清空全部指标（进程内测试用）。"""

        self._counters.clear()
        self._histograms.clear()
        del self._counter_order[:]
        del self._histogram_order[:]
