"""shardcount 演示：单锁计数、注册表、并发对拍、快照清零与分片计数。

第一段：LockCounter 与 Registry 的基本用法。
第二段：4 线程并发打点，和纯算术参考对拍。
第三段：snapshot 取值清零，前后总量守恒。
第四段：分片计数器 exact/fast 两种模式与热键摊槽效果。
"""

from shardcount import (
    LockCounter,
    Registry,
    ShardedCounter,
    drive,
    expected_totals,
    make_plan,
)
from shardcount.bench import measure


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

    print("=== 分片计数器：热键摊槽 ===")
    plan = make_plan(seed=7, keys=("hot", "warm", "cold"), threads=8, per_thread=2000)
    want = expected_totals(plan)

    exact = registry.open("shard.exact", mode="exact")
    drive(exact, plan)
    got = {key: exact.get(key) for key in exact.keys()}
    print("  exact 模式 8 线程压完与纯算术参考一致:", got == want)
    print("  槽位数:", exact.slot_count, " hot 各槽分量:", exact.slot_values("hot"))

    fast = registry.open("shard.fast", mode="fast")
    drive(fast, plan)  # 写线程收工时挂账自动落槽
    got = {key: fast.get(key) for key in fast.keys()}
    print("  fast 模式收工后精确:", got == want)
    fast.incr("hot")
    print("  fast 模式读滞后(真值+1, 读到):", fast.get("hot"), " sync 后:", end=" ")
    fast.sync()
    print(fast.get("hot"))

    print("  Registry 老调用照旧:", type(registry.open("api.hits")).__name__)

    seconds = 0.5
    base = measure(LockCounter, 8, seconds=seconds)
    shard = measure(ShardedCounter, 8, seconds=seconds)
    print("  8 线程热键吞吐: 单锁 %.0f ops/s  分片 %.0f ops/s  (%.1fx)"
          % (base, shard, shard / base))


if __name__ == "__main__":
    main()
