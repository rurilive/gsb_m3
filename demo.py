"""leftistheap 现状演示。

第一段：朴素优先队列。看建堆后取最小、插入、弹出最小、合并两个堆，给出弹出
序列、合并后的最小元素与堆元素个数，再打印朴素合并逐个插入的次数规模。
第二段：预留的左偏堆与配对堆两路新做法的演示位子（见文末注释）。
"""

from leftistheap import (
    build_heap,
    heap_sort,
    merge_heaps,
    merge_many,
    naive_merge_insert_count,
)
from leftistheap.builders import ascending, constant, with_negative


def main():
    print("=== 朴素优先队列 ===")

    base = build_heap([5, 1, 4, 2, 3])
    print("  建堆后元素个数:", base.size)
    print("  建堆后最小元素:", base.peek_min())
    base.insert(0)
    print("  插入 0 后最小元素:", base.peek_min())
    base.insert(9)
    print("  插入 9 后元素个数:", base.size)

    odd = build_heap([1, 3, 5, 7, 9])
    even = build_heap([2, 4, 6, 8, 10])
    merged = merge_heaps(odd, even)
    print("  合并两个五元素堆后元素个数:", merged.size)
    print("  合并后的最小元素:", merged.peek_min())
    print("  合并后弹出全部:", merged.drain())

    many = merge_many([build_heap([3, 1]), build_heap([9, 7]), build_heap([5, 0])])
    print("  一次合并三个堆后弹出全部:", many.drain())

    print("  堆排序结果:", heap_sort([5, 3, 9, 1, 7, 3]))
    print("  严格递增建堆后弹出首个:", ascending(6).peek_min())
    print("  全相同元素堆的个数:", constant(5, 4).size)
    print("  含负值堆的最小元素:", with_negative([3, -1, -7, 2]).peek_min())

    print("  朴素合并两堆的逐个插入次数:", naive_merge_insert_count(odd, even))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
