"""linkmux 现状演示：帧布局、串行一问一答、分片、重置。

串行往返跑在手动时钟上，投递延迟 0 立刻可读，延迟和时钟玩法见
tests/test_transport.py。
"""

from linkmux.errors import StreamReset
from linkmux.frame import HEADER_SIZE, KIND_DATA, KIND_FIN, KIND_NAMES, KIND_PING, KIND_RESET
from linkmux.frame import Frame, FrameBuffer, pack_frame
from linkmux.session import Session, pump_all
from linkmux.transport import ManualClock, MemoryLink


def show_layout():
    print("=== 帧布局 ===")
    for frame in (Frame(1, KIND_DATA, b"hello"), Frame(1, KIND_FIN), Frame(0, KIND_PING, b"tick")):
        print("  %-42s %s" % (frame, pack_frame(frame).hex(" ")))
    print("  头部固定 %d 字节" % HEADER_SIZE)


def show_round_trip():
    print("=== 串行一问一答 ===")
    a, b = MemoryLink.pair(clock=ManualClock(), names=("client", "server"))
    client, server = Session(a), Session(b)
    stream_id = client.send_request(b"hello mux")
    rounds = pump_all(client, server)
    request = server.take_request()
    server.send_response(request.stream_id, request.payload.upper())
    rounds += pump_all(client, server)
    print("  流 %d 来回 %d 轮，响应 %r，两端各发 %d 字节"
          % (stream_id, rounds, client.take_response().payload, a.sent_bytes))


def show_fragmentation():
    print("=== 帧长上限下的分片 ===")
    a, b = MemoryLink.pair()
    Session(a, frame_limit=64).send_request(bytes(range(150)))
    buffer = FrameBuffer()
    buffer.feed(b.recv())
    frames = buffer.drain()
    print("  150 字节 payload 切成 %d 帧: %s" % (len(frames), " ".join(
        "%s/%d" % (KIND_NAMES[f.kind], len(f.payload)) for f in frames)))


def show_reset():
    print("=== 对端重置在途的流 ===")
    a, b = MemoryLink.pair()
    client, server = Session(a), Session(b)
    stream_id = client.send_request(b"question")
    pump_all(client, server)
    server.take_request()
    b.send_frame(Frame(stream_id, KIND_RESET))
    client.pump()
    try:
        client.take_response()
    except StreamReset as exc:
        print("  客户端感知: %s" % (exc,))


def main():
    show_layout()
    show_round_trip()
    show_fragmentation()
    show_reset()


if __name__ == "__main__":
    main()
