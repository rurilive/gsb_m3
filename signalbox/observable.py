"""朴素可观察值：存一个值，设值时把新值通知给订阅者。

这是 signalbox 目前唯一的能力，没有依赖图、没有惰性求值、也没有批处理。
订阅者按注册顺序同步收到通知，退订后不再收到。整层由一把可重入锁保护。
"""

import threading


class Observable:
    """一个可观察的值。

    get() 读当前值；set(value) 更新值并把 (self, value) 逐个通知给订阅者；
    subscribe(fn) 注册一个订阅者并返回退订函数；unsubscribe(fn) 按引用退订，
    未注册过的订阅者退订返回 False。订阅者收到通知时抛出的异常会原样冒泡，
    此时值已经更新完毕。
    """

    def __init__(self, value=None):
        self._value = value
        self._subscribers = []
        self._lock = threading.RLock()
        self._version = 0

    def get(self):
        with self._lock:
            return self._value

    def set(self, value):
        with self._lock:
            self._value = value
            self._version += 1
            subscribers = list(self._subscribers)
        for fn in subscribers:
            fn(self, value)

    def subscribe(self, fn):
        if not callable(fn):
            raise TypeError("subscriber must be callable")
        with self._lock:
            self._subscribers.append(fn)

        def unsubscribe():
            return self.unsubscribe(fn)

        return unsubscribe

    def unsubscribe(self, fn):
        with self._lock:
            for i, existing in enumerate(self._subscribers):
                if existing is fn:
                    del self._subscribers[i]
                    return True
            return False

    def subscribers(self):
        with self._lock:
            return list(self._subscribers)

    @property
    def version(self):
        with self._lock:
            return self._version