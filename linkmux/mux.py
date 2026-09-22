"""多路复用：一条连接上同时跑多条流，帧按流号分发，各流独立流量控制。

MuxConn 管连接：open_stream() 开一条本端发起的流，accept() 取对端发起的
流，pump() 处理收件箱里到期的帧并把各流能发的都发出去。Stream 管一条流：
send() 攒进发送缓冲、按对端给的窗口额度和帧长上限切帧发出；recv() 取走
已收的字节，取走多少就给对端补多少窗口；close() 半关闭本端（收方向不受
影响）；reset() 发 reset 并丢掉这条流上所有缓冲和在途的数据，不连累别的
流。

流号 client 角色从 1 起占奇数，server 角色从 2 起占偶数，步长都是 2。每
条流一创建（本端 open_stream 或对端首帧到达）就先给对端发一份满载的
window_update 作为初始额度，之后应用每 recv 走多少字节就补多少；某条流
额度用光只停它自己的发送，别的流照跑。没见过的流号、重复的 fin/reset、
重置后在途的帧一律丢掉不崩；本地调用的非法状态转换抛 StreamStateError，
已重置的流上任何操作抛 StreamReset。
"""

from collections import deque

from linkmux.errors import FlowControlError, StreamReset, StreamStateError
from linkmux.frame import (
    DEFAULT_MAX_FRAME_PAYLOAD, Frame, FrameBuffer, KIND_DATA, KIND_FIN, KIND_PING,
    KIND_RESET, KIND_WINDOW_UPDATE, MAX_STREAM_ID, WINDOW_PAYLOAD_SIZE, pack_window,
    unpack_window,
)

ROLE_CLIENT = "client"
ROLE_SERVER = "server"
ROLES = (ROLE_CLIENT, ROLE_SERVER)


class Stream(object):
    """一条流：双向字节流，两个方向各自半关闭，整条可重置。"""

    def __init__(self, conn, stream_id):
        self.conn = conn
        self.stream_id = stream_id
        self.send_credit = 0
        self.recv_window = conn.window
        self._send_buf = bytearray()
        self._recv_buf = bytearray()
        self._local_fin = False
        self._fin_sent = False
        self._remote_fin = False
        self._reset = False

    def __repr__(self):
        return "Stream(stream=%d, buffered=%d, credit=%d)" % (
            self.stream_id, len(self._recv_buf), self.send_credit)

    @property
    def buffered(self):
        """已收到、还没被 recv 取走的字节数。"""
        return len(self._recv_buf)

    @property
    def local_closed(self):
        """本端已 close，不能再 send。"""
        return self._local_fin

    @property
    def remote_closed(self):
        """对端已 fin 或重置，不会再有新数据。"""
        return self._remote_fin or self._reset

    @property
    def reset_done(self):
        """这条流已被重置（本端或对端发起）。"""
        return self._reset

    @property
    def recv_eof(self):
        """对端的 fin 到了且缓冲已取空，之后 recv 只会拿到 b""。"""
        return self._remote_fin and not self._recv_buf

    @property
    def closed(self):
        """双向都收尾或已重置。"""
        return self._reset or (self._local_fin and self._remote_fin)

    def _check_live(self):
        if self._reset:
            raise StreamReset("流 %d 已重置" % (self.stream_id,), stream_id=self.stream_id)

    def send(self, data):
        """把字节排进发送缓冲，按额度和帧长上限尽快发出，返回排入的字节数。"""
        self._check_live()
        if self._local_fin:
            raise StreamStateError("流 %d 本端已关闭，不能再发" % (self.stream_id,))
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data 需要字节串，收到 %r" % (type(data).__name__,))
        self._send_buf += bytes(data)
        self.conn._flush_stream(self)
        return len(data)

    def recv(self, max_bytes=None):
        """取走已收到的字节；取走多少就给对端补多少窗口额度。"""
        self._check_live()
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("max_bytes 不能为负: %r" % (max_bytes,))
        count = len(self._recv_buf) if max_bytes is None else min(max_bytes, len(self._recv_buf))
        out = bytes(self._recv_buf[:count])
        del self._recv_buf[:count]
        if count:
            self.conn._grant_window(self, count)
        return out

    def close(self):
        """半关闭本端：缓冲发完后跟一帧 fin，收方向不受影响。"""
        self._check_live()
        if self._local_fin:
            raise StreamStateError("流 %d 本端已关闭" % (self.stream_id,))
        self._local_fin = True
        self.conn._flush_stream(self)

    def reset(self):
        """重置这条流：丢掉缓冲和在途的数据，发 reset 通知对端。"""
        self._check_live()
        self._reset = True
        self._send_buf = bytearray()
        self._recv_buf = bytearray()
        self.conn._send_frame(Frame(self.stream_id, KIND_RESET))


class MuxConn(object):
    """一条连接上的多路复用器，window 是每条流的接收窗口。"""

    def __init__(self, endpoint, role, window, frame_limit=DEFAULT_MAX_FRAME_PAYLOAD):
        if role not in ROLES:
            raise ValueError("role 只能是 %r 或 %r: %r" % (ROLE_CLIENT, ROLE_SERVER, role))
        if not isinstance(window, int) or isinstance(window, bool) \
                or not 1 <= window <= MAX_STREAM_ID:
            raise ValueError("window 要在 1..%d 之间: %r" % (MAX_STREAM_ID, window))
        if not WINDOW_PAYLOAD_SIZE <= frame_limit <= DEFAULT_MAX_FRAME_PAYLOAD:
            raise ValueError("frame_limit 要在 %d..%d 之间: %r"
                             % (WINDOW_PAYLOAD_SIZE, DEFAULT_MAX_FRAME_PAYLOAD, frame_limit))
        self.endpoint = endpoint
        self.role = role
        self.window = window
        self.frame_limit = frame_limit
        self._buffer = FrameBuffer()
        self._streams = {}
        self._pending = deque()
        self._next_id = 1 if role == ROLE_CLIENT else 2

    def open_stream(self):
        """开一条本端发起的流，先给对端发初始窗口通告。"""
        stream = self._create_stream(self._next_id)
        self._next_id += 2
        return stream

    def accept(self):
        """取一条对端发起的流，没有就返回 None。"""
        return self._pending.popleft() if self._pending else None

    def pump(self):
        """处理收件箱里到期的帧，再把各流能发的发出去，返回处理的帧数。"""
        data = self.endpoint.recv()
        if data:
            self._buffer.feed(data)
        handled = 0
        while True:
            frame = self._buffer.pop()
            if frame is None:
                break
            self._handle(frame)
            handled += 1
        self._flush()
        return handled

    def _create_stream(self, stream_id):
        stream = Stream(self, stream_id)
        self._streams[stream_id] = stream
        self._send_frame(Frame(stream_id, KIND_WINDOW_UPDATE, pack_window(self.window)))
        return stream

    def _is_peer_id(self, stream_id):
        return stream_id % 2 == (0 if self.role == ROLE_CLIENT else 1)

    def _handle(self, frame):
        if frame.kind == KIND_PING:
            return
        stream = self._streams.get(frame.stream_id)
        if stream is None:
            if frame.kind == KIND_RESET or not self._is_peer_id(frame.stream_id):
                return
            stream = self._create_stream(frame.stream_id)
            self._pending.append(stream)
        if frame.kind == KIND_DATA:
            self._on_data(stream, frame)
        elif frame.kind == KIND_WINDOW_UPDATE:
            self._on_window_update(stream, frame)
        elif frame.kind == KIND_FIN:
            stream._remote_fin = True
        elif frame.kind == KIND_RESET:
            stream._reset = True
            stream._send_buf = bytearray()
            stream._recv_buf = bytearray()

    def _on_data(self, stream, frame):
        if stream.remote_closed:
            return
        if len(frame.payload) > stream.recv_window:
            raise FlowControlError(
                "流 %d 一帧 %d 字节，超过剩余接收窗口 %d"
                % (stream.stream_id, len(frame.payload), stream.recv_window))
        stream.recv_window -= len(frame.payload)
        stream._recv_buf += frame.payload

    def _on_window_update(self, stream, frame):
        if stream.reset_done:
            return
        stream.send_credit += unpack_window(frame.payload)
        if stream.send_credit > MAX_STREAM_ID:
            raise FlowControlError("流 %d 的发送额度超过 32 位上限" % (stream.stream_id,))

    def _grant_window(self, stream, amount):
        stream.recv_window += amount
        if not stream.remote_closed:
            self._send_frame(Frame(stream.stream_id, KIND_WINDOW_UPDATE, pack_window(amount)))

    def _flush(self):
        for stream in list(self._streams.values()):
            self._flush_stream(stream)

    def _flush_stream(self, stream):
        if stream.reset_done:
            return
        while stream._send_buf and stream.send_credit:
            chunk = bytes(stream._send_buf[:min(self.frame_limit, stream.send_credit)])
            del stream._send_buf[:len(chunk)]
            stream.send_credit -= len(chunk)
            self._send_frame(Frame(stream.stream_id, KIND_DATA, chunk))
        if stream._local_fin and not stream._send_buf and not stream._fin_sent:
            stream._fin_sent = True
            self._send_frame(Frame(stream.stream_id, KIND_FIN))

    def _send_frame(self, frame):
        self.endpoint.send_frame(frame, self.frame_limit)
