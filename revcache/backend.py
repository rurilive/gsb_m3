"""revcache 背后的数据源。

Backend 保存每个 key 的权威副本。所有操作线程安全；读操作可以按需加
延迟或注入失败，方便在测试和演示里摆出某个不巧的时刻，而不用真去
连下游服务。
"""

import threading
import time


class TransientError(Exception):
    """数据源暂时答不上来，过一会儿重试也许就好。"""


class Backend:
    """带修订号的 key/value 权威存储。

    修订号记录一个 key 被改动过几次，只增不减，删除也不会让它回退，
    所以 snapshot 返回的 (值, 修订号) 总是成对的，读的人拿到值就知道
    自己手里是哪一版。
    """

    def __init__(self, sleep=time.sleep):
        self._sleep = sleep
        self._lock = threading.Lock()
        self._data = {}
        self._revs = {}
        self._reads = 0
        self._writes = 0
        self._deletes = 0
        self._latency = 0.0
        self._per_key_latency = {}
        self._faults = {}

    # 读

    def snapshot(self, key):
        """返回 (值, 修订号)。key 不存在时抛 KeyError。

        修订号只说明这份值是哪一版，不保证它还是最新的一版：注入的
        延迟加在返回路上，值在请求被受理时就已经定下了。
        """
        with self._lock:
            self._reads += 1
            if self._faults.get(key, 0) > 0:
                self._faults[key] -= 1
                raise TransientError(key)
            if key not in self._data:
                raise KeyError(key)
            result = (self._data[key], self._revs[key])
        self._delay(key)
        return result

    def get(self, key):
        """返回 key 的值。key 不存在时抛 KeyError。"""
        return self.snapshot(key)[0]

    def revision(self, key):
        """返回 key 当前的修订号，从没存在过的 key 返回 0。"""
        with self._lock:
            return self._revs.get(key, 0)

    # 写

    def set(self, key, value):
        """写入 value 并返回 key 的新修订号。"""
        with self._lock:
            rev = self._revs.get(key, 0) + 1
            self._revs[key] = rev
            self._data[key] = value
            self._writes += 1
            return rev

    def delete(self, key):
        """删除 key 并推高它的修订号，返回它原先是否存在。"""
        with self._lock:
            existed = key in self._data
            if existed:
                del self._data[key]
                self._revs[key] = self._revs.get(key, 0) + 1
                self._deletes += 1
            return existed

    # 供测试和演示用的故障注入

    def inject_latency(self, seconds, key=None):
        """让每次读取的返回晚 seconds 秒，指定 key 时只管这个 key。"""
        if key is None:
            self._latency = seconds
        else:
            self._per_key_latency[key] = seconds

    def inject_fault(self, key, count=1):
        """让接下来 count 次读这个 key 抛 TransientError。"""
        with self._lock:
            self._faults[key] = self._faults.get(key, 0) + count

    def stats(self):
        """返回计数器快照。"""
        with self._lock:
            return {"reads": self._reads, "writes": self._writes,
                    "deletes": self._deletes}

    # 内部

    def _delay(self, key):
        if key in self._per_key_latency:
            delay = self._per_key_latency[key]
        else:
            delay = self._latency
        if delay > 0:
            self._sleep(delay)
