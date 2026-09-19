"""心跳扩展帧行为测试：PING/PONG 回显配对、坏载荷、空版本列表。

心跳帧是 framec.heartbeat 扩展，导入即注册进 REGISTRY。为不污染
test_framec.py 锁定的初始注册表快照（仅 0x01-0x03），导入推迟到
setUpModule；unittest discover 按文件名字母序运行，test_framec 先跑完。
"""

import struct
import time
import unittest
import zlib

from framec import (
    REGISTRY,
    CrcError,
    Decoder,
    Encoder,
    FrameError,
    PayloadError,
)
from framec.registry import MAGIC

PingFrame = PongFrame = VersionFrame = None


def setUpModule():
    global PingFrame, PongFrame, VersionFrame
    from framec.heartbeat import PingFrame as _Ping, PongFrame as _Pong, VersionFrame as _Ver
    PingFrame, PongFrame, VersionFrame = _Ping, _Pong, _Ver


def build_frame(type_code, payload, seq=1, flags=0):
    """按线格式手工组一帧（CRC 正确），用于构造解码侧的边界输入。"""
    body = MAGIC + struct.pack(">BBHI", type_code, flags, len(payload), seq) + payload
    return body + struct.pack(">I", zlib.crc32(body))


class TestRegistryExtension(unittest.TestCase):
    def test_heartbeat_types_registered(self):
        self.assertIn(0x10, REGISTRY)
        self.assertIn(0x11, REGISTRY)
        self.assertIn(0x20, REGISTRY)
        self.assertEqual(REGISTRY[0x10].NAME, "PING")
        self.assertEqual(REGISTRY[0x11].NAME, "PONG")
        self.assertEqual(REGISTRY[0x20].NAME, "VERSION")
        self.assertIsInstance(REGISTRY[0x10], PingFrame)
        self.assertIsInstance(REGISTRY[0x11], PongFrame)

    def test_go_through_crc_pipeline(self):
        bad = bytearray(Encoder().encode(123, PingFrame))
        bad[10] ^= 0xFF
        with self.assertRaises(CrcError):
            Decoder().feed(bytes(bad))


class TestPingPong(unittest.TestCase):
    def test_payload_eight_big_endian_u64(self):
        wire = Encoder().encode(0x0102030405060708, PingFrame)
        self.assertEqual(wire[2], 0x10)
        self.assertEqual(struct.unpack(">H", wire[4:6])[0], 8)
        self.assertEqual(wire[10:-4], struct.pack(">Q", 0x0102030405060708))

    def test_roundtrip_boundaries(self):
        for value in (0, 1, 0xFFFFFFFFFFFFFFFF):
            wire = Encoder().encode(value, PingFrame)
            frame = Decoder().feed(wire)[0]
            self.assertEqual(frame.type_code, 0x10)
            self.assertEqual(frame.type_name, "PING")
            self.assertEqual(frame.value, value)

    def test_encode_rejects_bool(self):
        with self.assertRaises(PayloadError):
            Encoder().encode(True, PingFrame)

    def test_encode_rejects_negative(self):
        with self.assertRaises(PayloadError):
            Encoder().encode(-1, PingFrame)

    def test_encode_rejects_over_u64(self):
        with self.assertRaises(PayloadError):
            Encoder().encode(1 << 64, PingFrame)

    def test_encode_rejects_non_int(self):
        for bad in ("1", 1.5, None):
            with self.assertRaises(PayloadError):
                Encoder().encode(bad, PingFrame)

    def test_short_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x10, b"\x00" * 7))

    def test_long_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x10, b"\x00" * 9))

    def test_pong_payload_roundtrip(self):
        wire = Encoder().encode(99, PongFrame)
        self.assertEqual(wire[2], 0x11)
        frame = Decoder().feed(wire)[0]
        self.assertEqual(frame.type_code, 0x11)
        self.assertEqual(frame.type_name, "PONG")
        self.assertEqual(frame.value, 99)

    def test_pong_bad_length_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x11, b"\x00" * 4))

    def test_int_not_auto_inferred(self):
        with self.assertRaises(FrameError):
            Encoder().encode(5)

    def test_ftype_by_class_instance_and_code_identical(self):
        value = 77
        a = Encoder().encode(value, PingFrame)
        b = Encoder().encode(value, PingFrame())
        c = Encoder().encode(value, 0x10)
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_pong_echoes_ping_timestamp_and_rtt_pair(self):
        """PING 发出 -> 对端原样回 PONG -> 回包时刻配对算 RTT。"""
        enc, dec = Encoder(), Decoder()

        sent_ns = time.monotonic_ns()
        wire_in = enc.encode(sent_ns, PingFrame)
        ping = dec.feed(wire_in)[0]
        self.assertEqual(ping.value, sent_ns)

        reply = enc.encode(ping.value, PongFrame)
        pong = dec.feed(reply)[0]
        self.assertEqual(pong.type_code, 0x11)
        self.assertEqual(pong.value, sent_ns)

        recv_ns = time.monotonic_ns()
        rtt = recv_ns - pong.value
        self.assertIsInstance(rtt, int)
        self.assertGreaterEqual(rtt, 0)


class TestVersion(unittest.TestCase):
    def test_payload_is_comma_decimal_ascii(self):
        wire = Encoder().encode([1, 3], VersionFrame)
        self.assertEqual(wire[2], 0x20)
        self.assertEqual(wire[10:-4], b"1,3")

    def test_roundtrip(self):
        for value in ([0], [1, 3], [1, 2, 30]):
            wire = Encoder().encode(value, VersionFrame)
            frame = Decoder().feed(wire)[0]
            self.assertEqual(frame.type_code, 0x20)
            self.assertEqual(frame.type_name, "VERSION")
            self.assertEqual(frame.value, value)

    def test_empty_list_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Encoder().encode([], VersionFrame)

    def test_non_list_raises_payload_error(self):
        for bad in ((1, 2), "1,2", 1, None, {"1": 2}):
            with self.assertRaises(PayloadError):
                Encoder().encode(bad, VersionFrame)

    def test_non_int_element_raises_payload_error(self):
        for bad in ([1, "2"], [1, 2.0], [1, None], [1, True]):
            with self.assertRaises(PayloadError):
                Encoder().encode(bad, VersionFrame)

    def test_negative_element_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Encoder().encode([1, -2], VersionFrame)

    def test_empty_wire_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x20, b""))

    def test_non_ascii_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x20, "1,二".encode("utf-8")))

    def test_garbage_decimal_raises_payload_error(self):
        for bad in (b"x", b"1,", b",1", b"1,,3", b"1,a", b"-1", b"1,+2",
                    b" 1", b"1.0", b"1, 3"):
            with self.assertRaises(PayloadError):
                Decoder().feed(build_frame(0x20, bad))

    def test_ftype_by_class_and_code_identical(self):
        a = Encoder().encode([1, 3], VersionFrame)
        b = Encoder().encode([1, 3], 0x20)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
