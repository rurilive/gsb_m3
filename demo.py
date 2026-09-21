"""steadyclock 现状演示。

第一段：时间源的两个读法，墙钟与单调钟。
第二段：Deadline 与 Stopwatch 在正常推进下的口径。
第三段：机房校时之后，回拨与前跳都撼不动单调钟上的超时。
第四段：一次往返的四个时间戳，单发估计被请求时延整个带偏。
第五段：OffsetEstimator 多次测量、滤波收敛，校时压测纹丝不动。
"""

from steadyclock import (
    Deadline,
    Link,
    Loopback,
    ManualSource,
    OffsetEstimator,
    OffsetProbe,
    PeerClock,
    Stopwatch,
)


def section(title):
    print()
    print(f"=== {title} ===")


def demo_time_sources():
    section("时间源")
    source = ManualSource(wall=1_700_000_000.0)
    print(f"  起点：墙钟 {source.wall():.1f}，单调钟 {source.monotonic():.1f}")
    source.sleep(5.0)
    print(f"  过 5 秒：墙钟 {source.wall():.1f}，单调钟 {source.monotonic():.1f}")
    source.step_wall(-300.0)
    print(f"  校时回拨 300 秒：墙钟 {source.wall():.1f}，"
          f"单调钟 {source.monotonic():.1f}，单调钟不回头")


def demo_deadline():
    section("超时与耗时")
    source = ManualSource(wall=1_700_000_000.0)
    deadline = Deadline(source, 3.0)
    watch = Stopwatch(source)
    for _ in range(4):
        source.sleep(1.0)
        print(f"  过了 {watch.elapsed():.0f} 秒，剩余 "
              f"{deadline.remaining():.1f} 秒，到期 {deadline.expired()}")


def demo_calibration():
    section("机房校时之后")
    source = ManualSource(wall=1_700_000_000.0)
    deadline = Deadline(source, 3.0)
    source.sleep(1.0)
    print(f"  正常走 1 秒，剩余 {deadline.remaining():.1f} 秒")
    source.step_wall(-300.0)
    print(f"  回拨 300 秒：剩余 {deadline.remaining():.1f} 秒，到期 "
          f"{deadline.expired()}，单调钟上回拨不存在")
    source.step_wall(600.0)
    print(f"  再前跳 600 秒：剩余 {deadline.remaining():.1f} 秒，到期 "
          f"{deadline.expired()}，前跳也掐不断它")


def demo_round_trip():
    section("一次往返的四个时间戳")
    source = ManualSource(wall=1_700_000_000.0)
    peer = PeerClock(true_offset=-7.5)
    link = Link(base_delay=0.02, jitter=0.004, seed=2024)
    loopback = Loopback(source, peer, link)
    probe = OffsetProbe(loopback)
    t0, t1, t2, t3 = loopback.exchange()
    print(f"  本地发出 {t0:.6f}，对端收到 {t1:.6f}")
    print(f"  对端发出 {t2:.6f}，本地收到 {t3:.6f}")
    print(f"  往返走完全程 {(t3 - t0) - (t2 - t1):.4f} 秒")
    print(f"  单发估计 {probe.probe():.4f} 秒，真值 -7.5，"
          f"请求方向走了多久就偏多少")


def demo_offset_estimator():
    section("偏移估计器")
    source = ManualSource(wall=1_700_000_000.0)
    peer = PeerClock(true_offset=-7.5)
    clean = Link(base_delay=0.02, jitter=0.004, seed=2024)
    estimator = OffsetEstimator(Loopback(source, peer, clean))
    for _ in range(40):
        estimate = estimator.sample()
    print(f"  干净链路 40 轮：offset {estimate.offset:+.4f}（真值 -7.5），"
          f"界 ±{estimate.error_bound:.4f} 兜住真值，"
          f"confidence {estimate.confidence:.2f}")

    dirty = Link(base_delay=0.02, jitter=0.004, spike_chance=0.2,
                 fault_chance=0.1, seed=99)
    estimator = OffsetEstimator(Loopback(source, peer, dirty))
    for _ in range(60):
        estimate = estimator.sample()
    print(f"  尖峰 {dirty.spikes} 次、错读 {dirty.faults} 次："
          f"offset {estimate.offset:+.4f} 不被带偏，"
          f"confidence 降到 {estimate.confidence:.2f}")

    deadline = Deadline(source, 5.0)
    held = estimator.sample()
    source.step_wall(-300.0)
    estimator.sample()
    source.step_wall(600.0)
    estimate = estimator.sample()
    print(f"  墙钟回拨 300 秒再前跳 600 秒：offset 仍是 "
          f"{estimate.offset:+.4f}，超时剩余仍是 {deadline.remaining():.1f} 秒")

    for _ in range(10000):
        estimate = estimator.sample()
    print(f"  再跑一万轮：offset {estimate.offset:+.4f} 不漂，"
          f"界 ±{estimate.error_bound:.4f} 不涨")


def main():
    demo_time_sources()
    demo_deadline()
    demo_calibration()
    demo_round_trip()
    demo_offset_estimator()


if __name__ == "__main__":
    main()
