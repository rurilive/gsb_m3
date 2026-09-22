"""串行会话：一条连接上同一时刻只跑一对请求和响应。

Session 把 payload 切成不超过 frame_limit 的 data 帧发出去，尾上跟一帧
fin；收侧把同一条流的 data 拼回来，fin 到齐才算收全。本端发起的流号从
1 起、步长 2，响应沿用请求的流号。上一对没走完之前不许再发第二对，这
正是采集端现在要排队的根源。调用方拿 pump_all() 对接两端，来回泵到都
没有帧可处理为止。
"""

from linkmux.errors import LinkError, StreamReset, StreamStateError
from linkmux.frame import (
    DEFAULT_MAX_FRAME_PAYLOAD, Frame, FrameBuffer, KIND_DATA, KIND_FIN, KIND_PING, KIND_RESET,
)


class Message(object):
    """一条流上收全的请求或响应。"""

    __slots__ = ("stream_id", "payload")

    def __init__(self, stream_id, payload):
        self.stream_id = stream_id
        self.payload = payload

    def __eq__(self, other):
        return (isinstance(other, Message) and self.stream_id == other.stream_id
                and self.payload == other.payload)

    def __repr__(self):
        return "Message(stream=%d, payload=%d bytes)" % (self.stream_id, len(self.payload))


class Session(object):
    """一条连接上的串行请求-响应会话。"""

    def __init__(self, endpoint, frame_limit=DEFAULT_MAX_FRAME_PAYLOAD):
        if not 1 <= frame_limit <= DEFAULT_MAX_FRAME_PAYLOAD:
            raise ValueError("frame_limit 要在 1..%d 之间: %r"
                             % (DEFAULT_MAX_FRAME_PAYLOAD, frame_limit))
        self.endpoint = endpoint
        self.frame_limit = frame_limit
        self._buffer = FrameBuffer(frame_limit)
        self._next_id = 1
        self._out_id = None
        self._out_data = bytearray()
        self._out_reset = None
        self._incoming = {}
        self._done_requests = []
        self._done_responses = []
        self._replied = set()

    def send_request(self, payload):
        """开一对新的请求响应；上一对没收完就发是状态错误。"""
        if self._out_id is not None:
            raise StreamStateError("流 %d 的响应还没收完，一次只能跑一对" % (self._out_id,))
        stream_id = self._next_id
        self._next_id += 2
        self._send_stream(stream_id, payload)
        self._out_id = stream_id
        return stream_id

    def send_response(self, stream_id, payload):
        """在对端发起的流上回一段响应，流号沿用对方的。"""
        if stream_id in self._replied:
            raise StreamStateError("流 %d 已经回过响应了" % (stream_id,))
        self._replied.add(stream_id)
        self._send_stream(stream_id, payload)

    def _send_stream(self, stream_id, payload):
        payload = bytes(payload)
        for start in range(0, max(len(payload), 1), self.frame_limit):
            chunk = payload[start:start + self.frame_limit]
            if chunk:
                self.endpoint.send_frame(Frame(stream_id, KIND_DATA, chunk), self.frame_limit)
        self.endpoint.send_frame(Frame(stream_id, KIND_FIN), self.frame_limit)

    def pump(self):
        """处理收件箱里到期的帧，返回处理的帧数。"""
        data = self.endpoint.recv()
        if data:
            self._buffer.feed(data)
        handled = 0
        while True:
            frame = self._buffer.pop()
            if frame is None:
                return handled
            self._handle(frame)
            handled += 1

    def _handle(self, frame):
        if frame.kind == KIND_PING:
            return
        stream_id = frame.stream_id
        if frame.kind == KIND_DATA:
            if stream_id == self._out_id:
                self._out_data += frame.payload
            else:
                self._incoming.setdefault(stream_id, bytearray()).extend(frame.payload)
        elif frame.kind == KIND_FIN:
            if stream_id == self._out_id:
                self._done_responses.append(Message(stream_id, bytes(self._out_data)))
                self._out_data, self._out_id = bytearray(), None
            else:
                self._done_requests.append(Message(stream_id, bytes(self._incoming.pop(stream_id, b""))))
        elif frame.kind == KIND_RESET:
            if stream_id == self._out_id:
                self._out_reset, self._out_data, self._out_id = stream_id, bytearray(), None
            else:
                self._incoming.pop(stream_id, None)

    def take_request(self):
        """取一条对端发来的完整请求，没有就返回 None。"""
        return self._done_requests.pop(0) if self._done_requests else None

    def take_response(self):
        """取一条收全的响应；对端重置过在途的流就在这里抛 StreamReset。"""
        if self._out_reset is not None:
            stream_id, self._out_reset = self._out_reset, None
            raise StreamReset("对端重置了流 %d" % (stream_id,), stream_id=stream_id)
        return self._done_responses.pop(0) if self._done_responses else None


def pump_all(*parties, limit=1000):
    """把两端来回泵到都没有帧可处理，返回实际有帧处理的轮数。

    轮数就是一对请求响应要几个来回的底数，性能上的对比拿它当尺子。
    """
    rounds = 0
    while True:
        handled = 0
        for party in parties:
            handled += party.pump()
        if not handled:
            return rounds
        rounds += 1
        if rounds >= limit:
            raise LinkError("泵了 %d 轮还没停，八成有帧在原地打转" % (limit,))
