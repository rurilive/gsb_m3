"""radixest 演示。

第一段：精确去重计数——重复的 key 不重复计数。
第二段：基数估算——固定种子的误差界、稀疏/稠密互转、分片合并。
"""

import random

from radixest import CardinalityEstimator, DistinctCounter


def main():
    print("=== 精确去重计数 ===")
    c = DistinctCounter()
    events = ["u1", "u2", "u1", "u3", "u2", "u4", "u1"]
    for key in events:
        print(f"  add({key!r}) -> {c.add(key)}")
    print(f"  一共 {len(events)} 条事件，不同 key {c.count()} 个")

    print()
    print("=== 基数估算 ===")
    bits, seed, exact_limit = 1 << 16, 20260920, 1000
    for true_count in (500, exact_limit, 10_000, 50_000):
        est = CardinalityEstimator(bits, seed, exact_limit)
        for key in range(true_count):
            est.add(key)
        estimate = est.count()
        relative_error = abs(estimate - true_count) / true_count
        print(
            f"  真实 {true_count:6d} -> 估算 {estimate:9.1f}，"
            f"相对误差 {relative_error:6.3%}，误差界 {est.error_bound():6.3%}"
        )

    print()
    print("=== 稀疏/稠密互转 ===")
    est = CardinalityEstimator(bits, seed, exact_limit=100, dense_threshold=500)
    for key in range(2000):
        est.add(key)
    print(f"  置位涨过 500 后自动转稠密：is_dense={est.is_dense}，count={est.count():.1f}")
    est.to_sparse()
    sparse_count = est.count()
    print(f"  显式转回稀疏：is_dense={est.is_dense}，count={sparse_count:.1f}")
    est.to_dense()
    print(f"  再显式转稠密：is_dense={est.is_dense}，count={est.count():.1f}（与转换前一致）")

    print()
    print("=== 分片合并 ===")
    rng = random.Random(seed)
    universe = [f"user-{i}" for i in range(40_000)]
    rng.shuffle(universe)
    left_keys = set(universe[:25_000])
    right_keys = set(universe[15_000:])
    left = CardinalityEstimator(bits, seed, exact_limit)
    right = CardinalityEstimator(bits, seed, exact_limit)
    for key in left_keys:
        left.add(key)
    for key in right_keys:
        right.add(key)
    merged = left.merge(right)
    true_union = len(left_keys | right_keys)
    print(f"  分片 A 估算 {left.count():.1f}，分片 B 估算 {right.count():.1f}")
    print(f"  直接相加会重复入账；merge 后估算 {merged.count():.1f}，并集真实 {true_union}")
    print(f"  合并相对误差 {abs(merged.count() - true_union) / true_union:.3%}，"
          f"误差界 {merged.error_bound():.3%}，A/B 本身未被修改")


if __name__ == "__main__":
    main()
