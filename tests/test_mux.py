"""多路复用 MuxConn/Stream 的测试：并发、窗口、半关闭、重置、对拍。"""

import random
import unittest

from linkmux.errors import FlowControlError, StreamReset, StreamStateError
from linkmux.frame import (
    Frame, FrameBuffer, KIND_DATA, KIND_FIN, KIND_PING, KIND_RESET, KIND_WINDOW_UPDATE,
    pack_window,
)
from linkmux.mux import MuxConn
from linkmux.session import Session, pump_all
from linkmux.transport import ManualClock, MemoryLink


def make_pair(client_window=1024, server_window=1024, frame_limit=1024):
    a, b = MemoryLink.pair(clock=ManualClock(), names=("client", "server"))
    return (MuxConn(a, "client", client_window, frame_limit=frame_limit),
            MuxConn(b, "server", server_window, frame_limit=frame_limit))


def run_mux_echo(client, server, payloads, limit=100000):
    """客户端每条流发一段并半关闭，服务端收全后原样回显，返回各流收到的字节。"""
    streams = []
    for payload in payloads:
        stream = client.open_stream()
        stream.send(payload)
        stream.close()
        streams.append(stream)
    server_side = {}
    replies = [bytearray() for _ in payloads]
    for _ in range(limit):
        client.pump()
        server.pump()
        while True:
            incoming = server.accept()
            if incoming is None:
                break
            server_side[incoming.stream_id] = [incoming, bytearray(), False]
        for incoming, received, answered in server_side.values():
            received += incoming.recv()
            if incoming.recv_eof and not answered:
                incoming.send(bytes(received))
                incoming.close()
                server_side[incoming.stream_id][2] = True
        for stream, reply in zip(streams, replies):
            reply += stream.recv()
        if all(stream.recv_eof for stream in streams):
            return [bytes(reply) for reply in replies]
    raise AssertionError("泵了 %d 轮还没收完" % (limit,))


def run_session_echo(payloads):
    """串行参考：同样的负载用 Session 一对一对跑。"""
    a, b = MemoryLink.pair(clock=ManualClock(), names=("client", "server"))
    client, server = Session(a), Session(b)
    replies = []
    for payload in payloads:
        client.send_request(payload)
        pump_all(client, server)
        request = server.take_request()
        server.send_response(request.stream_id, request.payload)
        pump_all(client, server)
        replies.append(client.take_response().payload)
    return replies


class DifferentialTest(unittest.TestCase):
    def test_random_payloads_and_windows_match_serial_session(self):
        for seed in range(30):
            rng = random.Random(seed)
            payloads = [rng.randbytes(rng.randrange(0, 4000))
                        for _ in range(rng.randrange(1, 9))]
            expected = run_session_echo(payloads)
            self.assertEqual(expected, payloads)
            a, b = MemoryLink.pair(clock=ManualClock(), names=("client", "server"))
            client = MuxConn(a, "client", rng.randint(1, 4096),
                             frame_limit=rng.choice([4, 9, 100, 1024]))
            server = MuxConn(b, "server", rng.randint(1, 4096),
                             frame_limit=rng.choice([4, 9, 100, 1024]))
            self.assertEqual(run_mux_echo(client, server, payloads), expected)


class StreamIdTest(unittest.TestCase):
    def test_stream_id_parity_and_accept_order(self):
        client, server = make_pair()
        self.assertEqual([client.open_stream().stream_id for _ in range(3)], [1, 3, 5])
        self.assertEqual([server.open_stream().stream_id for _ in range(2)], [2, 4])
        pump_all(client, server)
        self.assertEqual([server.accept().stream_id for _ in range(3)], [1, 3, 5])
        self.assertEqual([client.accept().stream_id for _ in range(2)], [2, 4])
        self.assertIsNone(server.accept())
        self.assertIsNone(client.accept())


class WindowStallTest(unittest.TestCase):
    def test_small_stream_finishes_while_big_stream_hogs_window(self):
        client, server = make_pair(client_window=128, server_window=128)
        big = client.open_stream()
        big.send(b"x" * 40000)
        big.close()
        pump_all(client, server)
        stalled = server.accept()
        self.assertIsNotNone(stalled)
        self.assertEqual(stalled.buffered, 128)

        small = client.open_stream()
        small.send(b"hi")
        small.close()
        echoed = bytearray()
        small_server = None
        answered = False
        for _ in range(5):
            client.pump()
            server.pump()
            while True:
                incoming = server.accept()
                if incoming is None:
                    break
                if incoming.stream_id == small.stream_id:
                    small_server = incoming
            if small_server is not None and not answered:
                request = small_server.recv()
                if small_server.recv_eof:
                    small_server.send(request)
                    small_server.close()
                    answered = True
            echoed += small.recv()
            if small.recv_eof:
                break
        self.assertTrue(small.recv_eof)
        self.assertEqual(bytes(echoed), b"hi")
        self.assertEqual(stalled.buffered, 128)

        received = bytearray()
        for _ in range(100000):
            received += stalled.recv()
            client.pump()
            server.pump()
            if stalled.recv_eof:
                break
        self.assertEqual(bytes(received), b"x" * 40000)

    def test_recv_replenishes_window_incrementally(self):
        client, server = make_pair(client_window=100, server_window=100)
        stream = client.open_stream()
        stream.send(b"z" * 250)
        stream.close()
        pump_all(client, server)
        incoming = server.accept()
        self.assertEqual(incoming.buffered, 100)
        received = bytearray(incoming.recv(60))
        self.assertEqual(len(received), 60)
        pump_all(client, server)
        self.assertEqual(incoming.buffered, 100)
        received += incoming.recv()
        pump_all(client, server)
        received += incoming.recv()
        self.assertTrue(incoming.recv_eof)
        self.assertEqual(bytes(received), b"z" * 250)

    def test_over_window_data_rejected(self):
        client, server = make_pair(client_window=64)
        stream = client.open_stream()
        server.endpoint.send_frame(Frame(stream.stream_id, KIND_DATA, b"y" * 65))
        with self.assertRaises(FlowControlError):
            client.pump()


class HalfCloseTest(unittest.TestCase):
    def test_half_close_and_illegal_transitions(self):
        client, server = make_pair()
        stream = client.open_stream()
        stream.send(b"question")
        stream.close()
        self.assertTrue(stream.local_closed)
        with self.assertRaises(StreamStateError):
            stream.send(b"more")
        with self.assertRaises(StreamStateError):
            stream.close()
        pump_all(client, server)
        incoming = server.accept()
        self.assertEqual(incoming.recv(), b"question")
        self.assertTrue(incoming.recv_eof)
        incoming.send(b"answer")
        incoming.close()
        pump_all(client, server)
        self.assertEqual(stream.recv(), b"answer")
        self.assertTrue(stream.recv_eof)
        self.assertTrue(stream.closed)


class ResetTest(unittest.TestCase):
    def test_reset_drops_in_flight_and_spares_others(self):
        client, server = make_pair()
        one = client.open_stream()
        one.send(b"drop me")
        two = client.open_stream()
        two.send(b"keep me")
        two.close()
        pump_all(client, server)
        first, second = server.accept(), server.accept()
        first.reset()
        with self.assertRaises(StreamReset):
            first.recv()
        pump_all(client, server)
        for op in (lambda: one.recv(), lambda: one.send(b"x"),
                   lambda: one.close(), lambda: one.reset()):
            with self.assertRaises(StreamReset):
                op()
        client.endpoint.send_frame(Frame(one.stream_id, KIND_DATA, b"late"))
        client.endpoint.send_frame(Frame(one.stream_id, KIND_FIN))
        server.pump()
        self.assertEqual(second.recv(), b"keep me")
        self.assertTrue(second.recv_eof)
        second.send(b"kept")
        second.close()
        pump_all(client, server)
        self.assertEqual(two.recv(), b"kept")
        self.assertTrue(two.recv_eof)


class GarbageFrameTest(unittest.TestCase):
    def test_unknown_duplicate_and_interleaved_frames_do_not_crash(self):
        client, server = make_pair()
        stream = client.open_stream()
        stream.send(b"real")
        stream.close()
        server.endpoint.send_frame(Frame(99, KIND_DATA, b"ghost"))
        server.endpoint.send_frame(Frame(99, KIND_FIN))
        server.endpoint.send_frame(Frame(97, KIND_RESET))
        server.endpoint.send_frame(Frame(0, KIND_PING, b"tick"))
        server.endpoint.send_frame(Frame(2, KIND_DATA, b"sneaky"))
        server.endpoint.send_frame(Frame(2, KIND_FIN))
        server.endpoint.send_frame(Frame(2, KIND_FIN))
        client.pump()
        phantom = client.accept()
        self.assertEqual(phantom.recv(), b"sneaky")
        self.assertTrue(phantom.recv_eof)
        self.assertIsNone(client.accept())
        pump_all(client, server)
        incoming = server.accept()
        self.assertEqual(incoming.recv(), b"real")
        incoming.send(b"REAL")
        incoming.close()
        pump_all(client, server)
        server.endpoint.send_frame(Frame(stream.stream_id, KIND_FIN))
        server.endpoint.send_frame(Frame(stream.stream_id, KIND_DATA, b"too late"))
        server.endpoint.send_frame(Frame(41, KIND_WINDOW_UPDATE, pack_window(8)))
        client.pump()
        self.assertEqual(stream.recv(), b"REAL")
        self.assertTrue(stream.recv_eof)


class FragmentationTest(unittest.TestCase):
    def test_large_payload_split_by_frame_limit(self):
        a, b = MemoryLink.pair(clock=ManualClock(), names=("client", "server"))
        client = MuxConn(a, "client", 4096, frame_limit=100)
        server = MuxConn(b, "server", 4096, frame_limit=100)
        stream = client.open_stream()
        payload = bytes(range(256)) * 3
        stream.send(payload)
        stream.close()
        server.pump()
        client.pump()
        raw = b.recv()
        buffer = FrameBuffer()
        buffer.feed(raw)
        frames = buffer.drain()
        data = [frame for frame in frames if frame.kind == KIND_DATA]
        self.assertEqual(len(data), 8)
        self.assertTrue(all(len(frame.payload) <= 100 for frame in data))
        self.assertEqual(b"".join(frame.payload for frame in data), payload)
        self.assertEqual(frames[-1].kind, KIND_FIN)


class ConstructorTest(unittest.TestCase):
    def test_invalid_arguments_rejected(self):
        a, _ = MemoryLink.pair()
        with self.assertRaises(ValueError):
            MuxConn(a, "peer", 100)
        for window in (0, -1, 2 ** 32, "100"):
            with self.assertRaises(ValueError):
                MuxConn(a, "client", window)
        for limit in (0, 3, 2048):
            with self.assertRaises(ValueError):
                MuxConn(a, "client", 100, frame_limit=limit)


if __name__ == "__main__":
    unittest.main()
