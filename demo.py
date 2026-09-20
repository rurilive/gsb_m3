"""radixest 演示。

第一段：精确去重计数——重复的 key 不重复计数。
第二段：概率基数估算——位图估算、稀疏/稠密表示互转、分片合并。
"""

from radixest import CardinalityEstimator, DistinctCounter


def main():
    print("=== 精确去重计数 ===")
    c = DistinctCounter()
    events = ["u1", "u2", "u1", "u3", "u2", "u4", "u1"]
    for key in events:
        print(f"  add({key!r}) -> {c.add(key)}")
    print(f"  一共 {len(events)} 条事件，不同 key {c.count()} 个")

    print()
    demo_estimation()
    demo_representation()
    demo_merge()


def demo_estimation():
    print("=== 概率基数估算（固定种子，估算值 vs 真实值 vs 误差界）===")
    for n in (1000, 5000, 20000):
        e = CardinalityEstimator(bits=1 << 14, seed=7, exact_limit=128)
        for i in range(n):
            e.add(f"event-{i}")
        estimate = e.count()
        bound = e.error_bound()
        actual_error = abs(estimate - n) / n
        print(
            f"  真实 {n:6d}，估算 {estimate:6d}，"
            f"实际相对误差 {actual_error:.2%}，error_bound {bound:.2%}"
        )
    small = CardinalityEstimator(bits=1 << 14, seed=7, exact_limit=128)
    for i in range(50):
        small.add(f"exact-{i}")
    print(f"  只有 50 个 key（未超 exact_limit）：count={small.count()}，精确")


def demo_representation():
    print("=== 稀疏/稠密表示互转（count 不跳）===")
    e = CardinalityEstimator(bits=1 << 14, seed=3, exact_limit=50, sparse_max=300)
    for i in range(60):
        e.add(f"k-{i}")
    print(f"  超过 exact_limit 后：count={e.count()}，表示={e.representation()}")
    for i in range(60, 400):
        e.add(f"k-{i}")
    print(f"  置位涨过 sparse_max 自动转稠密：count={e.count()}，表示={e.representation()}")
    before = e.count()
    e.to_sparse()
    print(f"  显式转回稀疏：count={e.count()}，表示={e.representation()}，差值 {e.count() - before}")
    e.to_dense()
    print(f"  再显式转回稠密：count={e.count()}，表示={e.representation()}，差值 {e.count() - before}")


def demo_merge():
    print("=== 分片合并（跨片重复 key 不重复入账）===")
    shard_a = CardinalityEstimator(bits=1 << 14, seed=1, exact_limit=0)
    shard_b = CardinalityEstimator(bits=1 << 14, seed=1, exact_limit=0)
    for i in range(10000):
        shard_a.add(f"user-{i}")
    for i in range(5000, 15000):
        shard_b.add(f"user-{i}")
    a_count, b_count = shard_a.count(), shard_b.count()

    merged = shard_a.merge(shard_b)
    truth = CardinalityEstimator(bits=1 << 14, seed=1, exact_limit=0)
    for i in range(15000):
        truth.add(f"user-{i}")
    print(f"  分片 A 估算 {a_count}，分片 B 估算 {b_count}（有 5000 个 key 重叠）")
    print(f"  简单相加会记成 {a_count + b_count}；merge 后估算 {merged.count()}")
    print(f"  同流量直接统计为 {truth.count()}，真实并集 15000，两个原分片未被修改")


if __name__ == "__main__":
    main()
