"""genheap 的错误类型。"""


class HeapError(Exception):
    """堆相关错误的基类。"""


class UnknownObject(HeapError):
    """对象不存在，或者已经被回收。"""


class RootError(HeapError):
    """根集合操作不合法，比如放掉一个本来就不在根集合里的对象。"""


class SlotError(HeapError):
    """槽位操作不合法，比如槽位名不是非空字符串。"""


class CollectionError(HeapError):
    """回收相关错误，比如在钩子里递归调用 collect。"""


class BarrierError(CollectionError):
    """写屏障记账坏了：跨代引用漏记，或记录集里有悬空/虚假条目。"""
