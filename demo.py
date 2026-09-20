"""线程池现状演示。

第一段：submit / map / Task 句柄的基本用法。
第二段：优雅关闭 close() 的行为演示。
"""

import time

from workerpool import PoolClosed, WorkerPool


def fetch(item):
    # 模拟一次带耗时的外部调用
    time.sleep(0.05)
    return f"resp-{item}"


def main():
    print("=== submit / Task 句柄 ===")
    pool = WorkerPool(3)
    tasks = [pool.submit(fetch, i) for i in range(3)]
    for t in tasks:
        print(f"  result={t.result(5)} state={t.state}")

    print("\n=== map 批量转换 ===")
    squares = pool.map(lambda x: x * x, range(1, 8))
    print(f"  squares = {squares}")

    print("\n=== 任务异常不拖垮工作线程 ===")
    bad = pool.submit(int, "not-a-number")
    try:
        bad.result(5)
    except ValueError as exc:
        print(f"  caught from task: {exc}")
    good = pool.submit(fetch, 7)
    print(f"  next task on same pool: {good.result(5)}")

    print("\n=== 优雅关闭 close(grace_timeout=...) ===")
    slow = [pool.submit(fetch, 100 + i) for i in range(4)]
    # 池子 3 个槽位、每个任务约 0.05s：时限 0.08s 内前三个落定，
    # 第四个来不及，被标记 cancelled
    report = pool.close(grace_timeout=0.08)
    print(f"  completed={report.completed}")
    for t in report.cancelled:
        print(f"  cancelled: {t!r}")
    again = pool.close()
    print(f"  重复 close 幂等: {again is report}")
    try:
        pool.submit(fetch, 999)
    except PoolClosed as exc:
        print(f"  关闭后 submit: {type(exc).__name__}: {exc}")
    print(f"  atexit_registered={pool.atexit_registered}")

    print("\ndone.")


if __name__ == "__main__":
    main()
