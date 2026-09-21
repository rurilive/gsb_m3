"""时间跨度：差值、可读格式化与归档打包。

跨度一律用毫秒表示，打包格式见 README 契约。
"""

import struct

_UNIT_FACTOR_MS = {
    "ms": 1,
    "s": 1000,
    "min": 60 * 1000,
    "h": 60 * 60 * 1000,
    "d": 24 * 60 * 60 * 1000,
}


def duration_between(start_ms, end_ms, unit="ms"):
    """两个毫秒时间点之间的间隔，换算成 unit 的整数个单位。

    unit 取 "ms"、"s"、"min"、"h"、"d" 之一。
    """
    factor = _UNIT_FACTOR_MS[unit]
    return (end_ms - start_ms) // factor


def format_duration(ms):
    """把毫秒间隔格式化成从大到小的可读形式，例如 "1d 2h 3m 4.500s"。"""
    sign = "-" if ms < 0 else ""
    total = abs(int(ms))
    days, rest = divmod(total, 86_400_000)
    hours, rest = divmod(rest, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)

    parts = []
    if days:
        parts.append("%dd" % days)
    if days or hours:
        parts.append("%dh" % hours)
    if days or hours or minutes:
        parts.append("%dm" % minutes)
    parts.append("%d.%03ds" % (seconds, millis))
    return sign + " ".join(parts)


def pack_duration(ms):
    """把毫秒跨度打包成归档索引用的 8 字节定长编码。"""
    return struct.pack("<q", ms)


def unpack_duration(blob):
    """把 pack_duration 的产物解回毫秒跨度。"""
    return struct.unpack("<q", blob)[0]
