"""stealpool 演示：提交取结果、任务树对拍、取消、工作窃取特性。"""

import threading
import time

from stealpool import Pool, TaskCancelled
from stealpool.reference import TaskNode, TreeRunner, run_sequential


def fetch(name, delay=0.02):
    time.sleep(delay)
    return "body:" + name


def main():
    print("=== 提交与取结果（3 个 worker） ===")
    pool = Pool(3)
    futures = [pool.submit(fetch, "page%d" % i) for i in range(6)]
    print("  结果:", [f.result() for f in futures])
    pool.shutdown()
    snap = pool.stats()
    print("  submitted=%d completed=%d failed=%d steals=%d"
          % (snap["submitted"], snap["completed"], snap["failed"], snap["steals"]))
    print("  每 worker 忙碌秒数:", ["%.3f" % s for s in snap["busy_seconds"]])
    print("  每 worker 空闲秒数:", ["%.3f" % s for s in snap["idle_seconds"]])

    print("=== 任务树：顺序参考对拍并行执行 ===")
    tree = TaskNode(
        "page",
        (
            TaskNode("links", work=0.03, tag=2),
            TaskNode("images", (TaskNode("thumb", work=0.03, tag=3),), work=0.02, tag=5),
        ),
        work=0.02,
        tag=100,
    )
    started = time.monotonic()
    expected = run_sequential(tree)
    sequential_seconds = time.monotonic() - started
    with Pool(4) as tree_pool:
        started = time.monotonic()
        got = TreeRunner(tree_pool).run(tree)
        parallel_seconds = time.monotonic() - started
    print("  顺序结果:", expected)
    print("  并行结果:", got, "一致" if got == expected else "不一致")
    print("  顺序 %.3fs，并行 %.3fs" % (sequential_seconds, parallel_seconds))

    print("=== 取消一个还没开跑的任务 ===")
    pool = Pool(2)
    release = threading.Event()
    blockers = [pool.submit(release.wait, 5.0) for _ in range(2)]
    victim = pool.submit(fetch, "cancel-me")
    print("  cancel 返回:", victim.cancel())
    try:
        victim.result()
    except TaskCancelled as exc:
        print("  取结果抛出:", type(exc).__name__, exc)
    release.set()
    for blocker in blockers:
        blocker.result(5.0)
    pool.shutdown()

    print("=== 一头沉的任务树：各 worker 分工与偷取 ===")
    def skewed(level, counter=[0]):
        # 每个节点挂一个重子树加一片轻叶子，活明显偏向一边
        counter[0] += 1
        name = "skew%d" % counter[0]
        if level <= 0:
            return TaskNode(name, work=0.01, tag=1)
        return TaskNode(name, (skewed(level - 1), TaskNode(name + "s", work=0.01, tag=1)),
                        work=0.01, tag=1)

    with Pool(4) as skew_pool:
        TreeRunner(skew_pool).run(skewed(11))
        time.sleep(0.05)
    snap = skew_pool.stats()
    print("  每 worker 忙碌秒数:", ["%.3f" % s for s in snap["busy_seconds"]])
    print("  每 worker 任务数:", snap["tasks"], "偷取次数:", snap["steals"])

    print("=== 单 worker 跑 500 层深链（等子任务时不空等） ===")
    with Pool(1) as single:
        def link(n):
            if n == 0:
                return 0
            return single.submit(link, n - 1).result() + 1
        started = time.monotonic()
        print("  结果:", single.submit(link, 500).result(),
              "耗时 %.3fs" % (time.monotonic() - started))

    print("=== 取消整条链：没开跑的子任务一并作废，在干活的不打断 ===")
    pool = Pool(2)
    gate = threading.Event()

    def chain_parent():
        running = pool.submit(gate.wait, 5.0)  # 会被另一个 worker 偷走执行
        queued = [pool.submit(fetch, "queued-%d" % i) for i in range(3)]
        time.sleep(0.2)  # 留时间让 running 被偷走、queued 留在队列里
        return running, queued

    parent_future = pool.submit(chain_parent)
    time.sleep(0.1)
    print("  cancel 运行中的父任务返回:", parent_future.cancel())
    gate.set()
    running, queued = parent_future.result()
    print("  在干活的子任务照常完成:", running.result())
    for child in queued:
        try:
            child.result()
        except TaskCancelled:
            print("  排队子任务已作废: cancelled=%s" % child.cancelled())
    pool.shutdown()


if __name__ == "__main__":
    main()
