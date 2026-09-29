"""朴素计数信号量。

现在这里只有一把普通的计数信号量：init 时给一个许可总数，acquire 一次
拿走一个许可，release 一次还回一个许可，没有许可就抛异常。没有等待队列，
不认识时钟，也不区分是谁在持有许可。加权、超时、公平排队、重入与动态
缩容都还没有，见 README 与任务描述。
"""


class SemaphoreBusy(Exception):
    """许可不足：当前可用许可为 0，本次获取没有被满足。"""


class Semaphore:
    """普通计数信号量，只认一个许可总数。

    capacity 是许可总数，非正整数立刻报错。acquire 与 release 都只处理
    一个许可，不做加权，也不排队等待。
    """

    def __init__(self, capacity):
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise ValueError("容量必须是整数: %r" % (capacity,))
        if capacity <= 0:
            raise ValueError("容量必须是正整数: %r" % (capacity,))
        self._capacity = capacity
        self._available = capacity

    @property
    def capacity(self):
        """许可总数。"""
        return self._capacity

    @property
    def available(self):
        """当前可用许可数。"""
        return self._available

    @property
    def held(self):
        """当前已被持有的许可数。"""
        return self._capacity - self._available

    def acquire(self):
        """拿走一个许可；没有可用许可时抛 SemaphoreBusy。"""
        if self._available <= 0:
            raise SemaphoreBusy("没有可用许可")
        self._available -= 1

    def release(self):
        """还回一个许可；还回之后不能超过总数。"""
        if self._available >= self._capacity:
            raise ValueError("释放超过总数")
        self._available += 1

    def __repr__(self):
        return "<Semaphore available=%d/%d>" % (self._available, self._capacity)