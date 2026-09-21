"""genheap：纯标准库的标记清除对象堆。

ObjectHeap 管分配、根集合、槽位读写与全堆回收；
mark 里是从一组根出发的遍历原语，跟回收策略无关。
"""

from genheap.errors import (
    BarrierError,
    CollectionError,
    HeapError,
    RootError,
    SlotError,
    UnknownObject,
)
from genheap.generational import GenerationalHeap, OLD, YOUNG
from genheap.heap import Cell, ObjectHeap
from genheap.mark import trace, unmarked

__all__ = [
    "ObjectHeap",
    "GenerationalHeap",
    "Cell",
    "HeapError",
    "UnknownObject",
    "RootError",
    "SlotError",
    "CollectionError",
    "BarrierError",
    "YOUNG",
    "OLD",
    "trace",
    "unmarked",
]
