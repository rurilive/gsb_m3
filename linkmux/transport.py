"""单连接的内存模拟。

一对 Endpoint 用 MemoryLink.pair() 建出来，send 的字节进对端收件箱，
默认投递延迟为 0 立刻可读；配上延迟和时钟之后要等时钟走过投递时刻。
时钟可注入，只要有 now() 就行：SystemClock 跟真实时间走，ManualClock
手动推进，测试和演示里用它，不用真等。
"""

import time

from linkmux.errors import LinkClosed, LinkError
from linkmux.frame import DEFAULT_MAX_FRAME_PAYLOAD, pack_frame


class SystemClock(object):
    """跟真实时间走。"""

    def now(self):
        return time.monotonic()


class ManualClock(object):
    """手动推进的时钟，起点可以指定。"""

    def __init__(self, start=0.0):
        self._now = float(start)

    def now(self):
        return self._now

    def advance(self, seconds):
        if seconds < 0:
            raise ValueError("时间不能倒流: %r" % (seconds,))
        self._now += float(seconds)
        return self._now


class Endpoint(object):
    """连接的一端：send 进对端收件箱，recv 取到自己已到期的字节。"""

    def __init__(self, name="endpoint", clock=None, latency=0.0):
        self.name = name
        self.clock = clock or SystemClock()
        self.latency = float(latency)
        self.peer = None
        self.closed = False
        self.sent_bytes = 0
        self.recv_bytes = 0
        self._inbox = []

    def _buffered(self, due):
        now = self.clock.now()
        return sum(len(buf) for at, buf in self._inbox if (at <= now) == due)

    @property
    def pending(self):
        """现在就能取走的字节数。"""
        return self._buffered(True)

    @property
    def in_flight(self):
        """还在路上、没到投递时刻的字节数。"""
        return self._buffered(False)

    def send(self, data):
        """把字节发给对端，返回发出的字节数。"""
        if self.closed:
            raise LinkClosed("本端已经关了，发不出去")
        if self.peer is None or self.peer.closed:
            raise LinkClosed("对端已经关了，发不出去")
        data = bytes(data)
        self.peer._inbox.append((self.clock.now() + self.latency, bytearray(data)))
        self.sent_bytes += len(data)
        return len(data)

    def send_frame(self, frame, max_payload=DEFAULT_MAX_FRAME_PAYLOAD):
        """编好一帧再发，返回发出的字节数。"""
        return self.send(pack_frame(frame, max_payload))

    def recv(self, max_bytes=None):
        """取走收件箱里已到期的字节，max_bytes 限一次取多少。"""
        if max_bytes is not None and max_bytes < 0:
            raise LinkError("max_bytes 不能为负: %r" % (max_bytes,))
        out = bytearray()
        now = self.clock.now()
        while self._inbox:
            deliver_at, buf = self._inbox[0]
            if deliver_at > now:
                break
            want = len(buf) if max_bytes is None else min(len(buf), max_bytes - len(out))
            if want <= 0:
                break
            out += buf[:want]
            del buf[:want]
            if not buf:
                self._inbox.pop(0)
        self.recv_bytes += len(out)
        return bytes(out)

    def close(self):
        """关掉这一端，收件箱里剩的字节还可以读。"""
        self.closed = True


class MemoryLink(object):
    """一条内存里的连接，两端都看得见。"""

    def __init__(self, latency=0.0, clock=None, names=("a", "b")):
        clock = clock or SystemClock()
        self.clock = clock
        self.a = Endpoint(names[0], clock, latency)
        self.b = Endpoint(names[1], clock, latency)
        self.a.peer = self.b
        self.b.peer = self.a

    @classmethod
    def pair(cls, latency=0.0, clock=None, names=("a", "b")):
        """建一条连接，返回两端。"""
        link = cls(latency=latency, clock=clock, names=names)
        return link.a, link.b
