"""linkmux: 跟采集端之间的单连接链路库，纯标准库。

线上是帧格式的字节流，帧头带流号；transport 用内存对象模拟对端，
session 目前按串行请求-响应用这条连接。
"""

from linkmux.errors import (
    FlowControlError, FrameError, LinkClosed, LinkError, StreamReset, StreamStateError,
)
from linkmux.frame import (
    CONNECTION_STREAM_ID, DEFAULT_MAX_FRAME_PAYLOAD, HEADER_SIZE, KIND_DATA, KIND_FIN,
    KIND_NAMES, KIND_PING, KIND_RESET, KIND_WINDOW_UPDATE, MAX_FRAME_PAYLOAD,
    WINDOW_PAYLOAD_SIZE, Frame, FrameBuffer, check_frame, pack_frame, pack_window,
    unpack_frame, unpack_window,
)
from linkmux.session import Message, Session, pump_all
from linkmux.transport import Endpoint, ManualClock, MemoryLink, SystemClock
