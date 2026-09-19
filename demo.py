"""healthd 现状演示。

第一段：注册几个探针，手动跑一轮检查并查看状态板。
第二段：常驻自检的位子（见文件末尾注释）。
"""

import random

from healthd import CheckRunner


def check_db():
    # 假装探一下主库连通性
    return "primary up"


def check_queue():
    # 模拟队列积压探针：积压过深直接抛错
    depth = random.randrange(0, 60)
    if depth > 45:
        raise RuntimeError(f"backlog={depth}")
    return f"depth={depth}"


def check_disk():
    return "72% used"


def demo_resident():
    """常驻自检演示：探针超时降级/恢复，以及 k/n 就绪门限翻转。

    3 个探针、门限 k=2：全过 ok；1 个探针超时变 degraded 但仍 ready；
    2 个超时变 down 且 ready=False；逐一恢复后翻回 ok。
    每轮开始前给该探针换一个新 gate：已置位即立即通过，未置位则被
    runner 的 timeout 判超时（探针线程随后释放，不拖死整轮）。
    """
    import threading

    from healthd.monitor import HealthMonitor

    gates = {}

    def set_mode(name, hold):
        old = gates.get(name)
        event = threading.Event()
        if not hold:
            event.set()
        gates[name] = event
        if old is not None and not hold:
            old.set()

    def probe(name):
        def _fn():
            gates[name].wait()
            return f"{name} ok"

        return _fn

    monitor = HealthMonitor(period=0.12, jitter=0.01, k=2)
    monitor.register("db", check_db, timeout=0.1)
    monitor.register("queue", probe("queue"), timeout=0.1)
    monitor.register("disk", probe("disk"), timeout=0.1)

    flipped = threading.Event()

    def on_change(old, new):
        print(f"  [flip] {old} -> {new}  ready={monitor.ready()}")
        flipped.set()

    monitor.on_change(on_change)

    def next_round(label, name, hold):
        # 翻转回调结束时上一轮已写完，线程在睡下一个周期，趁此窗口换 gate。
        set_mode(name, hold)
        flipped.clear()
        assert flipped.wait(1.0), f"no state flip for: {label}"
        detail = monitor.snapshot()[name].detail
        print(f"  {label}: status={monitor.status()} ready={monitor.ready()} ({detail})")

    print("=== 常驻自检（period=0.12s, k=2/3）===")
    set_mode("queue", False)
    set_mode("disk", False)
    monitor.start()
    flipped.wait(1.0)
    print(f"  全过:      status={monitor.status()} ready={monitor.ready()}")

    next_round("queue 超时", "queue", True)
    next_round("disk 也超时", "disk", True)
    next_round("queue 恢复", "queue", False)
    next_round("disk 恢复", "disk", False)
    monitor.stop()


def main():
    runner = CheckRunner()
    runner.register("db", check_db)
    runner.register("queue", check_queue)
    runner.register("disk", check_disk)

    print("=== 手动跑一轮检查 ===")
    snap = runner.run_once()
    for name in runner.names():
        r = snap[name]
        mark = "PASS" if r.ok else "FAIL"
        print(f"  [{mark}] {name:<6} {r.detail}")
    print(f"  overall_ok = {runner.board.overall_ok()}")

    print()
    demo_resident()


if __name__ == "__main__":
    main()
