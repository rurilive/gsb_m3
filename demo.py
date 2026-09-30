"""固定窗限流器现状演示。

第一段：朴素限流器的固定窗判定、窗口内计数观测与拒绝统计。
第二段：预留的滑动窗口与令牌桶演示位子（见文末注释）。
"""

from ratelimit.core import TimestampLimiter, naive_scan


def main():
    print("=== 朴素固定窗限流器（现有能力） ===")
    lim = TimestampLimiter(window=10, limit=2)
    for t in (0, 3, 11, 12, 19):
        verdict = "放行" if lim.allow(t) else "拒绝"
        print("  时刻", t, "判定 =", verdict)
    print("  累计拒绝 =", lim.total_rejected())
    print("  时刻 19 窗口内计数 =", lim.observed(19))
    print("  判定记录 =", lim.history())

    print("=== 独立朴素扫描核对 ===")
    stamps = [0, 3, 11, 12, 19]
    print("  时刻 19 线性扫描计数 =", naive_scan(stamps, 10, 19))

    print("=== 分维度隔离 ===")
    multi = TimestampLimiter(window=10, limit=1)
    multi.allow(0, label="read")
    multi.allow(0, label="write")
    multi.allow(1, label="read")
    print("  read 拒绝 =", multi.total_rejected("read"))
    print("  write 拒绝 =", multi.total_rejected("write"))
    print("  维度列表 =", multi.labels())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
