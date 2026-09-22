"""内存连接与可注入时钟的基线测试。"""

import unittest

from linkmux.errors import FrameError, LinkClosed
from linkmux.frame import Frame, FrameBuffer, KIND_DATA, MAX_FRAME_PAYLOAD
from linkmux.transport import ManualClock, MemoryLink


class ClockAndDeliveryTest(unittest.TestCase):
    def test_clock_advances_and_refuses_backwards(self):
        clock = ManualClock(start=5.0)
        clock.advance(1.5)
        clock.advance(0.5)
        self.assertEqual(clock.now(), 7.0)
        with self.assertRaises(ValueError):
            clock.advance(-1)

    def test_latency_holds_bytes_until_clock_advances(self):
        a, b = MemoryLink.pair()
        a.send(b"hello")
        self.assertEqual(b.pending, 5)
        self.assertEqual(b.recv(), b"hello")
        self.assertEqual((b.pending, a.pending), (0, 0))
        clock = ManualClock()
        a, b = MemoryLink.pair(latency=0.25, clock=clock)
        a.send(b"later")
        self.assertEqual((b.pending, b.in_flight), (0, 5))
        clock.advance(0.25)
        self.assertEqual((b.pending, b.in_flight), (5, 0))
        self.assertEqual(b.recv(), b"later")

    def test_recv_limits_bytes_counts_traffic_and_refuses_closed_ends(self):
        a, b = MemoryLink.pair(names=("client", "server"))
        self.assertEqual((a.name, b.name, a.peer is b, b.peer is a), ("client", "server", True, True))
        a.send(b"0123456789")
        self.assertEqual(b.recv(4), b"0123")
        self.assertEqual(b.pending, 6)
        b.send(b"de")
        self.assertEqual((a.sent_bytes, b.recv_bytes, a.pending), (10, 4, 2))
        self.assertEqual(a.recv(), b"de")
        b.close()
        with self.assertRaises(LinkClosed):
            a.send(b"x")

    def test_send_frame_matches_frame_buffer(self):
        a, b = MemoryLink.pair()
        a.send_frame(Frame(1, KIND_DATA, b"z"))
        buffer = FrameBuffer()
        buffer.feed(b.recv())
        self.assertEqual(buffer.drain(), [Frame(1, KIND_DATA, b"z")])
        with self.assertRaises(FrameError):
            a.send_frame(Frame(1, KIND_DATA, b"x" * (MAX_FRAME_PAYLOAD + 1)))


if __name__ == "__main__":
    unittest.main()
