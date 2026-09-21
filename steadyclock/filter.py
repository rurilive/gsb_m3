"""偏移样本的滤波：离群剔除与平滑，单独成模块。

OffsetEstimator 每跑一次往返拿到一个 (offset, delay) 样本：offset 是
这一趟看到的钟差，delay 是往返时延。两个事实撑起整个滤波口径：

- 单趟样本的误差以半时延为界：真值必落在 offset ± delay/2 里，所以
  时延越小的样本越值钱，时延成倍放大的排队尖峰天然该出局
- 对端错读把 offset 整个搬飞，但时延不变，靠中位数与绝对中位差
  （MAD）把这种离群点剔掉

幸存样本取均值做平滑；误差界按 max(|幸存样本 - 均值| + 样本半时延)
兜底——只要幸存里还有一个干净样本，真值就被这个界兜住。confidence
是窗口里干净样本（时延没尖峰、读数没离群）的占比，链路越脏它越低。
"""

import statistics
from collections import deque, namedtuple

FilterResult = namedtuple(
    "FilterResult", ("offset", "error_bound", "confidence", "spread")
)


class OffsetFilter:
    """一串 (offset, delay) 样本的滑动窗口滤波。

    window 是窗口容量，select 是每次评估取时延最低的多少个样本做候选，
    spike_ratio 判定时延尖峰的倍数，mad_factor 是离群剔除的 MAD 倍数。
    窗口定长，单轮评估的开销不随总轮数增长。
    """

    def __init__(self, window=32, select=8, spike_ratio=1.5, mad_factor=8.0):
        if select < 1:
            raise ValueError("select 至少为 1")
        if window < select:
            raise ValueError("window 不能小于 select")
        self._window = int(window)
        self._select = int(select)
        self._spike_ratio = float(spike_ratio)
        self._mad_factor = float(mad_factor)
        self._samples = deque(maxlen=self._window)

    def __len__(self):
        return len(self._samples)

    @property
    def window(self):
        return self._window

    def add(self, offset, delay):
        """放进一个样本：offset 钟差读数，delay 这一趟的往返时延。"""
        self._samples.append((float(offset), float(delay)))

    def reset(self):
        """清空窗口，真值迁移之后重新收敛用。"""
        self._samples.clear()

    def evaluate(self):
        """评估当前窗口，返回 FilterResult；窗口为空返回 None。"""
        if not self._samples:
            return None
        samples = list(self._samples)
        min_delay = min(delay for _, delay in samples)
        candidates = sorted(samples, key=lambda sample: sample[1])[: self._select]
        median = statistics.median(offset for offset, _ in candidates)
        mad = statistics.median(abs(offset - median) for offset, _ in candidates)
        limit = self._mad_factor * mad
        survivors = [
            (offset, delay)
            for offset, delay in candidates
            if abs(offset - median) <= limit
        ]
        if not survivors:
            survivors = [(median, min_delay)]
        offset = sum(value for value, _ in survivors) / len(survivors)
        spread = max(abs(value - offset) for value, _ in survivors)
        error_bound = max(
            abs(value - offset) + delay / 2.0 for value, delay in survivors
        )
        clean = sum(
            1
            for value, delay in samples
            if delay <= min_delay * self._spike_ratio
            and abs(value - median) <= limit
        )
        confidence = min(1.0, clean / self._window)
        return FilterResult(offset, error_bound, confidence, spread)
