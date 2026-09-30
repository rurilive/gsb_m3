"""leftistheap：优先队列合并的朴素实现（改造前基线）。

全部能力都建立在同一件事上：堆就是一条普通列表，建堆时把元素逐个排好序，
插入时用线性查找给新元素找位置再塞进去，合并两个堆时把一边的元素逐个插入
另一边。做法直白、结果正确，元素一多、合并一多就退化到平方以上量级。
"""


class LeftistHeapError(Exception):
    """所有 leftistheap 错误的公共基类。"""


class HeapError(LeftistHeapError):
    """堆的构造或输入不合法。"""


class OperationError(LeftistHeapError):
    """堆操作的前置条件不满足。"""


def _merge_sorted(left, right):
    """归并两条已升序排列的列表，返回新的升序列表。"""
    out = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    if i < len(left):
        out.extend(left[i:])
    if j < len(right):
        out.extend(right[j:])
    return out


def _check_element(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HeapError("element must be a number")


class Heap:
    """优先队列，底层是一条升序列表。

    空堆用空列表表示。元素必须是数值。所有查询与修改都直接作用在这条列表
    上，取最小就是取列表头，弹出最小就是丢掉列表头。
    """

    def __init__(self, items=None):
        self._items = []
        if items is not None:
            for value in items:
                self.insert(value)

    @property
    def size(self):
        """堆里的元素个数。"""
        return len(self._items)

    def is_empty(self):
        """堆里有没有元素。"""
        return not self._items

    def insert(self, value):
        """插入一个元素。

        朴素做法：从头到尾线性扫描这条升序列表，找到第一个比新元素大的位置，
        再把新元素插进去，后面整体后移。
        """
        _check_element(value)
        position = 0
        while position < len(self._items) and self._items[position] <= value:
            position += 1
        self._items.insert(position, value)

    def peek_min(self):
        """看最小的元素，不弹出。空堆抛 OperationError。"""
        if not self._items:
            raise OperationError("peek on empty heap")
        return self._items[0]

    def pop_min(self):
        """弹出并返回最小的元素。空堆抛 OperationError。"""
        if not self._items:
            raise OperationError("pop on empty heap")
        return self._items.pop(0)

    def to_sorted_list(self):
        """把全部元素按升序排好返回，堆本身不变。"""
        return list(self._items)

    def drain(self):
        """反复弹出最小元素，返回升序序列，堆被清空。"""
        out = []
        while self._items:
            out.append(self._items.pop(0))
        return out


def build_heap(items):
    """用一批元素建堆。"""
    return Heap(items)


def merge_heaps(first, second):
    """合并两个堆，返回一个新堆，两个输入堆都不被改动。

    朴素做法：把第二个堆的每个元素逐个插入第一个堆的副本，每次插入都要在这
    条升序列表里线性找位置。
    """
    _check_heap(first)
    _check_heap(second)
    merged = Heap()
    merged._items = list(first._items)
    for value in second._items:
        merged.insert(value)
    return merged


def _check_heap(heap):
    if not isinstance(heap, Heap):
        raise HeapError("heap must be a Heap")


def merge_many(heaps):
    """把一批堆顺次合并成一个堆。

    朴素做法：从左到右两两合并，每次合并都把右边堆的每个元素逐个插入左边。
    """
    if not isinstance(heaps, (list, tuple)):
        raise HeapError("heaps must be a list or tuple")
    for heap in heaps:
        _check_heap(heap)
    if not heaps:
        return Heap()
    acc = heaps[0]
    for heap in heaps[1:]:
        acc = merge_heaps(acc, heap)
    return acc


def heap_sort(items):
    """堆排序：把元素逐个插入堆，再反复弹出最小元素得到升序序列。"""
    return build_heap(items).drain()


def naive_merge_insert_count(first, second):
    """朴素合并这两个堆这一趟要做多少次逐个插入的比较。

    把第二个堆的每个元素插进第一个堆的副本，每次插入在列表里线性找位置，最
    坏要扫过当前全部元素，这里按每次插入扫过的元素个数累计。
    """
    _check_heap(first)
    _check_heap(second)
    count = 0
    current = len(first._items)
    for _ in second._items:
        count += current
        current += 1
    return count


__all__ = [
    "LeftistHeapError",
    "HeapError",
    "OperationError",
    "Heap",
    "build_heap",
    "merge_heaps",
    "merge_many",
    "heap_sort",
    "naive_merge_insert_count",
]
