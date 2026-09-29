"""朴素的无界先进先出队列。

FifoQueue 只做一件事：把元素按放进来的先后顺序存起来，再按同样的顺序取出。
内部用一把互斥锁保护底层的双端队列，保证多线程下入队与出队不会把内部结构弄乱。
它没有容量概念，放多少存多少，取不到就返回 None，不阻塞、不排队、不认时钟，
也没有关闭之类的生命周期语义。
"""

import threading
from collections import deque


class FifoQueue:
    """先入先出的无界队列，带一把互斥锁。"""

    def __init__(self):
        self._items = deque()
        self._lock = threading.Lock()

    def push(self, item):
        """把一个元素放到队尾，返回元素本身。"""
        if item is None:
            raise ValueError("item 不能是 None")
        with self._lock:
            self._items.append(item)
        return item

    def pop(self):
        """从队首取出一个元素；队列为空时返回 None。"""
        with self._lock:
            if not self._items:
                return None
            return self._items.popleft()

    def peek(self):
        """看一眼队首元素但不取走；队列为空时返回 None。"""
        with self._lock:
            if not self._items:
                return None
            return self._items[0]

    def __len__(self):
        with self._lock:
            return len(self._items)

    def __bool__(self):
        with self._lock:
            return bool(self._items)
