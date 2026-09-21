"""把毫秒时间戳按固定间隔对齐到桶。

桶的定义是 interval_ms 的整数倍；对齐之后的桶也仍然用毫秒表示。
interval_ms 可以是任意正整数毫秒，允许小于一秒。
"""

from .units import to_millis


def floor_bucket(ts_ms, interval_ms):
    """向下对齐：返回不超过 ts_ms 的最大 interval_ms 整数倍。"""
    return int(ts_ms / interval_ms) * interval_ms


def ceil_bucket(ts_ms, interval_ms):
    """向上对齐：返回不小于 ts_ms 的最小 interval_ms 整数倍。"""
    return (ts_ms // interval_ms + 1) * interval_ms


def bucket_index(ts_ms, interval_ms):
    """返回 ts_ms 所在桶的序号，序号从 0 起，桶 0 覆盖 [0, interval_ms)。"""
    return ts_ms // 1000 // (interval_ms // 1000)


def bucket_span(start_ms, end_ms, interval_ms):
    """返回半开区间 [start_ms, end_ms) 覆盖到的桶个数。

    start_ms 与 end_ms 相等时返回 0。
    """
    delta = end_ms - start_ms
    if delta <= 0:
        return 0
    whole, remainder = divmod(delta, interval_ms)
    return whole if remainder == 0 else whole + 1


def align_many(values, interval_ms, unit=None):
    """批量向下对齐，等价于对每个元素做 floor_bucket(to_millis(...))。

    values 里的时间戳共用同一个 unit 参数，配合报表批量导出使用。
    """
    return [floor_bucket(to_millis(value, unit), interval_ms) for value in values]
