"""进程内网络：消息排队投递，丢包、延迟、乱序、分区都能注入。

发送和投递都看注入的时钟，随机源由外部传入，同一颗种子跑出来的
时间线完全可复现。
"""

import random


class Delivery:
    """一次投递：谁发给谁、带了什么、什么时候到期。"""

    __slots__ = ("seq", "src", "dst", "payload", "due")

    def __init__(self, seq, src, dst, payload, due):
        self.seq = seq
        self.src = src
        self.dst = dst
        self.payload = payload
        self.due = due

    def __repr__(self):
        return f"Delivery({self.src}->{self.dst}, due={self.due})"


class InMemoryNetwork:
    """一条按到期时刻排序的在途消息队列。

    同一对节点之间不保证先进先出，到期时刻相同的按发送先后投递。
    断掉的链路在消息到期那一刻会再拦一次，断链期间到期的消息直接
    作废，不会攒着等链路恢复再冒出来。
    """

    def __init__(self, clock, rng=None, loss=0.0, min_delay=1, max_delay=1):
        if min_delay < 1:
            raise ValueError("min_delay must be at least 1")
        if max_delay < min_delay:
            raise ValueError("max_delay must be >= min_delay")
        if not 0.0 <= loss < 1.0:
            raise ValueError("loss must be in [0, 1)")
        self._clock = clock
        self._rng = rng if rng is not None else random.Random(0)
        self.loss = float(loss)
        self.min_delay = int(min_delay)
        self.max_delay = int(max_delay)
        self.stats = {"sent": 0, "dropped": 0, "delivered": 0}
        self._queue = []
        self._seq = 0
        self._groups = None
        self._sent_by = {}

    # ---- 拓扑 ----

    def partition(self, group_a, group_b):
        """把节点分成两拨，跨组的链路全部断开。"""
        self._groups = (set(group_a), set(group_b))

    def heal(self):
        """恢复所有链路。"""
        self._groups = None

    def blocked(self, src, dst):
        """这条链路此刻是否断开。"""
        if self._groups is None:
            return False
        a, b = self._groups
        return (src in a and dst in b) or (src in b and dst in a)

    # ---- 收发 ----

    def send(self, src, dst, payload):
        """发一条消息，返回是否进了队列（被丢也计入 sent）。"""
        self.stats["sent"] += 1
        self._sent_by[src] = self._sent_by.get(src, 0) + 1
        if self.blocked(src, dst) or self._rng.random() < self.loss:
            self.stats["dropped"] += 1
            return False
        self._seq += 1
        due = self._clock.now + self._rng.randint(self.min_delay, self.max_delay)
        self._queue.append(Delivery(self._seq, src, dst, payload, due))
        self._queue.sort(key=lambda m: (m.due, m.seq))
        return True

    def deliver_due(self):
        """投出所有到期的消息，返回投递列表，按到期先后排序。"""
        now = self._clock.now
        ready = []
        waiting = []
        for msg in self._queue:
            if msg.due <= now:
                if self.blocked(msg.src, msg.dst):
                    self.stats["dropped"] += 1
                else:
                    ready.append(msg)
            else:
                waiting.append(msg)
        self._queue = waiting
        self.stats["delivered"] += len(ready)
        return ready

    def inflight(self):
        """还在路上的消息条数。"""
        return len(self._queue)

    def sent_by(self, node_id):
        """某个节点累计发出（含被丢）的消息条数。"""
        return self._sent_by.get(node_id, 0)

    def reset_stats(self):
        """清零计数，方便按周期统计。"""
        self.stats.update({"sent": 0, "dropped": 0, "delivered": 0})
        self._sent_by.clear()
