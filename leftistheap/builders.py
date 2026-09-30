"""构造演示与测试用堆的小工具，纯标准库。

这些函数只负责把一个普通序列塞进堆里，或者造出几种典型形状，方便演示脚本
与基线测试反复取用，本身不含任何新的合并做法。
"""

from leftistheap import Heap, build_heap


def from_values(values):
    """用一串数值建堆，顺序原样传入。"""
    return build_heap(list(values))


def empty_heap():
    """一个什么都没有的空堆。"""
    return Heap()


def single_heap(value):
    """只有一个元素的堆。"""
    return Heap([value])


def ascending(n, start=0):
    """严格递增插入：start 开始连续 n 个数，逐个插入。"""
    if n < 0:
        raise ValueError("n must be >= 0")
    return Heap([start + i for i in range(n)])


def descending(n, start=None):
    """严格递减插入：从大到小连续 n 个数，逐个插入。"""
    if n < 0:
        raise ValueError("n must be >= 0")
    if start is None:
        start = n - 1
    return Heap([start - i for i in range(n)])


def constant(n, value=7):
    """全相同元素：n 个一样的值。"""
    if n < 0:
        raise ValueError("n must be >= 0")
    return build_heap([value] * n)


def with_negative(values):
    """含负值的堆。"""
    return build_heap(list(values))


def two_heaps():
    """一对样本堆：奇数堆与偶数堆，用来演示合并。"""
    odd = build_heap([1, 3, 5, 7, 9])
    even = build_heap([2, 4, 6, 8, 10])
    return odd, even
