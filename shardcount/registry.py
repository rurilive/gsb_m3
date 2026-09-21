"""名字到计数器实例的注册表。

一个进程里要维护好些计数器：按服务、按接口、按租户各一份。名字对实例，
第一次 open 建出来，以后 open 拿到的都是同一份；多个线程同时 open 同名
也不会各拿各的。工厂可注入，方便把别的实现挂进来。
"""

import threading

from shardcount.counter import LockCounter


class Registry:
    """按名字发计数器的注册表，整个进程共用一份。

    factory: 可调用对象，收一个名字返回计数器实例；默认建 LockCounter。
    """

    def __init__(self, factory=None):
        self._factory = factory or (lambda name: LockCounter())
        self._lock = threading.Lock()
        self._counters = {}

    def open(self, name):
        """取 name 对应的计数器，没有就按工厂建一个；同名永远同一份。"""
        with self._lock:
            counter = self._counters.get(name)
            if counter is None:
                counter = self._factory(name)
                self._counters[name] = counter
            return counter

    def bind(self, name, counter):
        """把一份现成的计数器挂到 name 上，同名已有的会被换掉。"""
        with self._lock:
            self._counters[name] = counter
        return counter

    def get(self, name):
        """取已注册的计数器，没注册抛 KeyError。"""
        with self._lock:
            counter = self._counters.get(name)
        if counter is None:
            raise KeyError("counter not opened: %r" % (name,))
        return counter

    def names(self):
        """已注册的名字，排序返回。"""
        with self._lock:
            return sorted(self._counters)

    def drop(self, name):
        """摘掉一个名字，返回是否真有东西被摘掉；之后 open 会重新建。"""
        with self._lock:
            return self._counters.pop(name, None) is not None
