"""eventlog 的朴素全局事件列表（改造前的现状）。

现在只有一条最简单的事件路径：一个只追加的全局列表，append 把事件
排到末尾，read 按顺序读回。没有流、没有版本号、没有并发控制、没有
快照、没有投影、没有订阅。
多流、版本、快照、投影重建与订阅见任务描述。
"""


class EventLog:
    """一个只追加的全局事件列表。

    - append(event)：把一个事件对象排到全局列表末尾，返回它的下标
    - read()：按追加顺序读回全部事件，返回列表副本
    - __len__()：当前事件条数
    - __iter__()：按追加顺序遍历事件
    事件按对象原样存放，不打包、不带版本、不做任何并发检查。
    """

    def __init__(self):
        self._events = []

    def append(self, event):
        """把一个事件排到全局列表末尾，返回它在全局序列里的下标（从 0 起）。"""
        self._events.append(event)
        return len(self._events) - 1

    def read(self):
        """按追加顺序读回全部事件，返回列表副本，改动副本不影响内部。"""
        return list(self._events)

    def __len__(self):
        return len(self._events)

    def __iter__(self):
        return iter(list(self._events))

    def __repr__(self):
        return "EventLog(%d events)" % len(self._events)
