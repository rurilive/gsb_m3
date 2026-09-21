"""shardcount 现状演示：单锁计数、注册表、并发对拍与快照清零。

第一段：LockCounter 与 Registry 的基本用法。
第二段：4 线程并发打点，和纯算术参考对拍。
第三段：snapshot 取值清零，前后总量守恒。
文末留了分片版的演示位子。
"""

from shardcount import LockCounter, Registry, drive, expected_totals, make_plan


def main():
    print("=== 单锁计数与注册表 ===")
    registry = Registry()
    hits = registry.open("api.hits")
    errors = registry.open("api.errors")
    hits.incr("GET /v1/items")
    hits.incr("GET /v1/items", 2)
    errors.incr("GET /v1/items")
    print("  运行中的计数器:", registry.names())
    print("  hits:", hits.get("GET /v1/items"), " errors:", errors.get("GET /v1/items"))
    print("  同名 open 拿的是同一份:", registry.open("api.hits") is hits)
    print("  stats:", hits.stats())

    print("=== 并发打点与纯算术参考对拍 ===")
    plan = make_plan(seed=7, keys=("hot", "warm", "cold"), threads=4, per_thread=2000)
    counter = LockCounter()
    drive(counter, plan)
    got = {key: counter.get(key) for key in counter.keys()}
    want = expected_totals(plan)
    print("  实得:", got)
    print("  期望:", want)
    print("  一致:", got == want)

    print("=== 快照取值清零 ===")
    queue = LockCounter()
    for _ in range(5):
        queue.incr("queue.depth")
    print("  快照拿走:", queue.snapshot("queue.depth"))
    print("  快照之后读到:", queue.get("queue.depth"))
    print("  再快照一次:", queue.snapshot("queue.depth"))

    # TODO(分片改造): 分片版做完后，在这里补一段演示：用 Registry.open 的
    # mode 选实现，多线程围着同一个热键打点，跟单锁版对拍总量；打印分片
    # 布局，以及 bench 量出来的相对单锁倍数。


if __name__ == "__main__":
    main()
