"""segpile 现状演示：滚段、手动压缩、写峰期压缩的代价。

最后一段对照：同一串写入改由后台 Scheduler 驱动压缩。
"""

from segpile import MemoryBackend, Scheduler, SimDevice, Store


def percentile(values, q):
    """取分位数，空列表返回 0。"""
    ordered = sorted(values)
    return 0.0 if not ordered else ordered[int(round(q * (len(ordered) - 1)))]


def show_layout(store, limit=6):
    for seg in store.segments()[:limit]:
        mark = " <-active" if seg is store.active else ""
        print("  sid=%-2s seq=%-2s size=%-3d created=%-4.0f%s" % (seg.sid, seg.seq, seg.size, seg.created, mark))
    if len(store.segments()) > limit:
        print("  ... 共 %d 段" % len(store.segments()))


def demo_layout():
    print("=== 写入与滚段 ===")
    device = SimDevice()
    store = Store(MemoryBackend(), device, segment_limit=4)
    for i in range(10):
        store.put("user:%02d" % i, i)
        device.advance(1.0)
    show_layout(store)
    print("  段数 %d，get('user:03') = %r" % (len(store.segments()), store.get("user:03")))

    print("=== 手动压缩一轮 ===")
    report = store.compact_once()
    print("  %r" % (report,))
    show_layout(store)
    print("  snapshot 里 user:07 = %r" % store.snapshot()["user:07"])


def demo_write_peak():
    print("=== 写峰期穿插手动压缩，每 4 笔压一轮 ===")
    device = SimDevice()
    store = Store(MemoryBackend(), device, segment_limit=8)
    latencies = []
    rounds = 0
    for i in range(200):
        if i % 4 == 0 and store.compact_once() is not None:
            rounds += 1
        latencies.append(store.put("hot:%03d" % i, i))
        device.advance(1.0)
    print("  压了 %d 轮，设备账面 读=%d 写=%d" % (rounds, device.read_units, device.write_units))
    print(
        "  前台写延迟 p50=%.1f p95=%.1f max=%.1f tick"
        % (percentile(latencies, 0.5), percentile(latencies, 0.95), max(latencies))
    )
    show_layout(store)

def demo_scheduler():
    print("=== 同一串写入，改由后台调度压缩（budget=4）===")
    device = SimDevice()
    store = Store(MemoryBackend(), device, segment_limit=8)
    sched = Scheduler(store, budget=4)
    latencies = []
    merges = 0
    spent = 0
    for i in range(200):
        if sched.step() is not None:
            merges += 1
        spent += sched.last_units
        latencies.append(store.put("hot:%03d" % i, i))
        device.advance(1.0)
    print("  并掉 %d 轮，后台 IO 共 %d 单位，设备账面 读=%d 写=%d"
          % (merges, spent, device.read_units, device.write_units))
    print(
        "  前台写延迟 p50=%.1f p95=%.1f max=%.1f tick"
        % (percentile(latencies, 0.5), percentile(latencies, 0.95), max(latencies))
    )
    print("  各段等待轮数: %r" % (sched.wait_times(),))
    show_layout(store)


def main():
    demo_layout()
    demo_write_peak()
    demo_scheduler()


if __name__ == "__main__":
    main()
