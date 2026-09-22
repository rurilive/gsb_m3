"""帧编解码与拆帧的基线测试。"""

import unittest

from linkmux.errors import FrameError
from linkmux.frame import (
    HEADER, HEADER_SIZE, KIND_DATA, KIND_FIN, KIND_PING, KIND_RESET, KIND_WINDOW_UPDATE,
    MAX_FRAME_PAYLOAD, Frame, FrameBuffer, pack_frame, pack_window, unpack_frame, unpack_window,
)


class PackTest(unittest.TestCase):
    def test_header_layout_and_roundtrip(self):
        raw = pack_frame(Frame(7, KIND_DATA, b"hi", flags=3))
        self.assertEqual(len(raw), HEADER_SIZE + 2)
        self.assertEqual(HEADER.unpack_from(raw, 0), (7, KIND_DATA, 3, 2))
        self.assertEqual(raw[HEADER_SIZE:], b"hi")
        self.assertEqual(len(pack_frame(Frame(0, KIND_PING))), HEADER_SIZE)
        for frame in (Frame(1, KIND_DATA, b"payload"), Frame(3, KIND_FIN),
                      Frame(5, KIND_RESET, flags=1), Frame(0, KIND_PING, b"tick"),
                      Frame(9, KIND_WINDOW_UPDATE, pack_window(4096))):
            self.assertEqual(unpack_frame(pack_frame(frame)), frame)
        self.assertEqual(pack_window(0xFFFFFFFF), b"\xff\xff\xff\xff")
        self.assertEqual(unpack_window(pack_window(4096)), 4096)

    def test_payload_bounds(self):
        frame = Frame(1, KIND_DATA, b"x" * MAX_FRAME_PAYLOAD)
        self.assertEqual(len(pack_frame(frame)), HEADER_SIZE + MAX_FRAME_PAYLOAD)
        with self.assertRaises(FrameError) as caught:
            pack_frame(Frame(1, KIND_DATA, b"x" * (MAX_FRAME_PAYLOAD + 1)))
        self.assertEqual(caught.exception.field, "length")
        for frame in (Frame(1, KIND_FIN, b"x"), Frame(1, KIND_RESET, b"x"),
                      Frame(9, KIND_WINDOW_UPDATE, b"\x00\x00\x00\x10\x00")):
            with self.assertRaises(FrameError) as caught:
                pack_frame(frame)
            self.assertEqual(caught.exception.field, "payload")
        with self.assertRaises(FrameError):
            unpack_window(b"\x00\x10")
        with self.assertRaises(FrameError):
            pack_window(-1)

    def test_field_bounds(self):
        with self.assertRaises(FrameError) as caught:
            pack_frame(Frame(1, 99))
        self.assertEqual(caught.exception.field, "kind")
        with self.assertRaises(FrameError) as caught:
            pack_frame(Frame(0, KIND_DATA, b"x"))
        self.assertEqual(caught.exception.field, "stream_id")
        for bad in (Frame(1, KIND_DATA, b"", flags=256), Frame(0x1_0000_0000, KIND_DATA, b"")):
            with self.assertRaises(FrameError):
                pack_frame(bad)
        with self.assertRaises(FrameError) as caught:
            unpack_frame(pack_frame(Frame(1, KIND_DATA, b"ab")) + b"\x00")
        self.assertEqual(caught.exception.field, "length")
        with self.assertRaises(FrameError) as caught:
            unpack_frame(b"\x00\x01")
        self.assertEqual(caught.exception.field, "header")


class FrameBufferTest(unittest.TestCase):
    def blob(self):
        return b"".join(pack_frame(f) for f in (
            Frame(1, KIND_DATA, b"first"), Frame(1, KIND_FIN), Frame(3, KIND_DATA, b"second")))

    def test_split_feed_reassembles_and_incomplete_frame_waits(self):
        buffer, seen = FrameBuffer(), []
        for index in range(len(self.blob())):
            buffer.feed(self.blob()[index:index + 1])
            seen.extend(buffer.drain())
        self.assertEqual([f.payload for f in seen], [b"first", b"", b"second"])
        self.assertEqual(buffer.pending, 0)
        buffer.feed(self.blob()[:HEADER_SIZE + 3])
        self.assertIsNone(buffer.pop())
        self.assertEqual(buffer.pending, HEADER_SIZE + 3)

    def test_header_alone_decides_oversize_and_unknown_kind(self):
        for raw, field in ((HEADER.pack(1, KIND_DATA, 0, MAX_FRAME_PAYLOAD + 1), "length"),
                           (HEADER.pack(1, 77, 0, 0), "kind")):
            buffer = FrameBuffer()
            buffer.feed(raw)
            with self.assertRaises(FrameError) as caught:
                buffer.pop()
            self.assertEqual(caught.exception.field, field)


if __name__ == "__main__":
    unittest.main()
