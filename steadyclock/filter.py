"""偏移测量的滤波：离群剔除与平滑。

OffsetEstimator 每跑一趟往返得到一个原始偏移测量，里面混着链路抖动、
排队尖峰、对端错读。这个模块把一串原始测量揉成稳定口径：先拿中位数
与 MAD 把离群样本剔掉，再在留下的样本里挑时延最低的一段（时延越小，
不对称带来的偏差越小），取它们的中位数当平滑后的估计。窗口定长，
耗时不随轮数涨；估计锚在窗口中位数上，收敛后不跟着单个样本抖。
"""

import statistics
from collections import deque


class OffsetFilter:
    """一串原始偏移测量的滑动窗口滤波器。"""

    def __init__(self, window=64, gate=6.0, gate_floor=1e-3, headroom=0.25):
        if window < 4:
            raise ValueError("窗口至少容纳 4 个样本")
        self._samples = deque(maxlen=window)
        self._window = window
        self._gate = float(gate)
        self._gate_floor = float(gate_floor)
        self._headroom = float(headroom)

    def __len__(self):
        return len(self._samples)

    def add(self, offset, rtt):
        """喂进一次原始测量：偏移与往返时延，单位秒。"""
        self._samples.append((float(offset), float(rtt)))

    def _inliers(self):
        """离群剔除：中位数为锚，MAD 的数倍加下限做门。"""
        offsets = [sample[0] for sample in self._samples]
        anchor = statistics.median(offsets)
        mad = statistics.median([abs(value - anchor) for value in offsets])
        gate = max(self._gate * mad, self._gate_floor)
        return [
            sample for sample in self._samples
            if abs(sample[0] - anchor) <= gate
        ]

    def estimate(self):
        """平滑后的 (offset, error_bound, confidence)，窗口空时返回 None。

        error_bound 的口径：被选中样本的往返时延一半是偏移偏差的上界
        （单程时延非负，不对称偏差最大就是往返的一半），再加选中样本
        自身的散布一半，真值落在界内。confidence 由窗口填满程度与
        留存率合成：错误样本、尖峰多了，留存率掉，置信度跟着降。
        """
        if not self._samples:
            return None
        keep = self._inliers()
        lowest_rtt = min(sample[1] for sample in keep)
        rtt_cap = lowest_rtt * (1.0 + self._headroom) + 1e-9
        kept = [sample for sample in keep if sample[1] <= rtt_cap]
        offsets = [sample[0] for sample in kept]
        offset = statistics.median(offsets)
        spread = max(offsets) - min(offsets)
        error_bound = max(sample[1] for sample in kept) / 2.0 + spread / 2.0
        fill = min(1.0, len(self._samples) / self._window)
        confidence = fill * (len(keep) / len(self._samples))
        return offset, error_bound, confidence
