"""triplet 现状演示。

第一段：用朴素实现做一轮上升三元组计数、存在性判定与长度四计数，看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from triplet.naive import (
    TripletAnalysis,
    count_increasing_subseq_of_length_naive,
    count_increasing_triplets_naive,
    count_non_decreasing_triplets_naive,
    enumerate_triplet_trials,
    first_increasing_triplet_naive,
    has_increasing_triplet_naive,
)

DATA = [3, 1, 4, 1, 5, 9, 2, 6]


def main():
    print("=== 朴素统计：三元组计数 ===")
    print(f"  序列           -> {DATA}")
    strict = count_increasing_triplets_naive(DATA)
    nondec = count_non_decreasing_triplets_naive(DATA)
    print(f"  严格上升       -> {strict}")
    print(f"  非下降         -> {nondec}")

    print("=== 朴素统计：存在性与首个三元组 ===")
    print(f"  是否存在       -> {has_increasing_triplet_naive(DATA)}")
    print(f"  首个三元组     -> {first_increasing_triplet_naive(DATA)}")
    print(f"  计数为零与否   -> {strict == 0}")

    print("=== 朴素统计：边界形态 ===")
    print(f"  递增           -> {count_increasing_triplets_naive([1, 2, 3, 4])}")
    print(f"  递降           -> {count_increasing_triplets_naive([4, 3, 2, 1])}")
    print(f"  全相等严格     -> {count_increasing_triplets_naive([3, 3, 3, 3])}")
    print(f"  全相等非下降   -> {count_non_decreasing_triplets_naive([3, 3, 3, 3])}")
    print(f"  含重复         -> {count_increasing_triplets_naive([2, 4, 1, 3, 5])}")

    print("=== 朴素统计：长度四的提升子序列 ===")
    print(f"  长度四严格     -> {count_increasing_subseq_of_length_naive(DATA, 4)}")
    print(f"  长度四非下降   -> {count_increasing_subseq_of_length_naive(DATA, 4, strict=False)}")

    print("=== 朴素统计：三重枚举规模与摘要 ===")
    print(f"  三重枚举次数   -> {enumerate_triplet_trials(DATA)}")
    analysis = TripletAnalysis(DATA)
    for key, value in analysis.summary().items():
        print(f"  {key:<15}-> {value}")

    # TODO: 第二段演示（实现后补）
    # 说明：树状数组前后缀三路、后缀式逆序对推广、长度四两次树状数组三条
    # 独立做法改造完成后，在这里补一段演示，对上面同一条固定序列分别走三路
    # 新做法，逐项断言严格上升与非下降两种口径的计数、存在性判定、首个三元组
    # 以及长度四计数全部一致，再与这条朴素三重枚举口径对照，并打印三重枚举
    # 次数与树状数组访问次数的规模差，让新路径能直接跑通并正常退出。


if __name__ == "__main__":
    main()
