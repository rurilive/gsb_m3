"""线程池用法演示。

第一段：submit / map / Task 句柄的基本用法。
第二段：优雅关闭 close() 的报告与拒收行为。
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

    print("\n=== close() 无时限：全部落定 ===")
    graceful = WorkerPool(2, atexit=False)
    g_tasks = [graceful.submit(fetch, i) for i in range(3)]
    report = graceful.close()
    print(f"  completed={report['completed']} cancelled={len(report['cancelled'])}")
    print(f"  states={[t.state for t in g_tasks]}")

    print("\n=== close(grace_timeout) 到期：在途与排队被取消 ===")
    shutting = WorkerPool(2, atexit=False)
    s_tasks = [
        shutting.submit(fetch, 10),  # 在途：约 0.05s 内跑不完 0.01s 宽限
        shutting.submit(fetch, 11),  # 在途
        shutting.submit(fetch, 12),  # 排队：不会被执行
    ]
    report = shutting.close(grace_timeout=0.01)
    print(f"  completed={report['completed']} cancelled={len(report['cancelled'])}")
    print(f"  states={[t.state for t in s_tasks]}")
    seqs = [t.seq for t in report["cancelled"]]
    print(f"  cancelled handles (seq)={seqs}")
    # 重复 close 幂等：拿回的是同一份首次报告
    print(f"  close() again is same report: {shutting.close() is report}")

    print("\n=== 关闭后拒收新任务 ===")
    try:
        shutting.submit(fetch, 99)
    except PoolClosed as exc:
        print(f"  submit after close: {type(exc).__name__}: {exc}")
    try:
        shutting.map(fetch, [1, 2])
    except PoolClosed as exc:
        print(f"  map after close: {type(exc).__name__}: {exc}")

    print("\ndone.")


if __name__ == "__main__":
    main()
