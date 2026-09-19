"""PING / PONG / VERSION 扩展帧的行为测试。

framec.heartbeat 不随包初始化注册，这里在 setUpModule 显式导入注册、
tearDownModule 注销，避免污染 test_framec 的注册表基线。
"""

import struct
import time
import unittest
import zlib

from framec import Decoder, Encoder, FrameError, PayloadError, REGISTRY
from framec.registry import MAGIC

heartbeat = None


def setUpModule():
    global heartbeat
    from framec import heartbeat  # 导入即注册 0x10/0x11/0x20


def tearDownModule():
    for code in (0x10, 0x11, 0x20):
        REGISTRY.pop(code, None)


def build_frame(type_code, payload, seq=1):
    """按线格式手工组一帧（CRC 正确），用于构造解码侧的非法载荷。"""
    body = MAGIC + struct.pack(">BBHI", type_code, 0, len(payload), seq) + payload
    return body + struct.pack(">I", zlib.crc32(body))


class TestRegistration(unittest.TestCase):
    def test_registered_on_import(self):
        self.assertEqual(REGISTRY[0x10].NAME, "PING")
        self.assertEqual(REGISTRY[0x11].NAME, "PONG")
        self.assertEqual(REGISTRY[0x20].NAME, "VERSION")

    def test_int_value_not_auto_inferred(self):
        with self.assertRaises(FrameError):
            Encoder().encode(time.monotonic_ns())

    def test_ftype_accepts_instance_class_and_code(self):
        ts = 123456789
        a = Encoder().encode(ts, heartbeat.PingFrame())
        b = Encoder().encode(ts, heartbeat.PingFrame)
        c = Encoder().encode(ts, 0x10)
        self.assertEqual(a, b)
        self.assertEqual(b, c)


class TestPingPong(unittest.TestCase):
    def test_wire_format_big_endian_u64(self):
        ts = time.monotonic_ns()
        wire = Encoder().encode(ts, heartbeat.PingFrame)
        self.assertEqual(wire[2], 0x10)
        self.assertEqual(wire[10:-4], struct.pack(">Q", ts))

    def test_echo_pairing_and_rtt(self):
        enc, dec = Encoder(), Decoder()
        sent = time.monotonic_ns()
        ping = dec.feed(enc.encode(sent, heartbeat.PingFrame))[0]
        self.assertEqual(ping.type_code, 0x10)
        pong = dec.feed(enc.encode(ping.value, heartbeat.PongFrame))[0]
        self.assertEqual(pong.type_code, 0x11)
        self.assertEqual(pong.value, sent)  # 原样回显，按值配对
        self.assertGreaterEqual(time.monotonic_ns() - pong.value, 0)

    def test_roundtrip_boundaries(self):
        for ts in (0, 1, 0xFFFFFFFFFFFFFFFF):
            wire = Encoder().encode(ts, heartbeat.PongFrame)
            self.assertEqual(Decoder().feed(wire)[0].value, ts)

    def test_bad_payload_length(self):
        for n in (0, 4, 7, 9):
            for code in (0x10, 0x11):
                with self.assertRaises(PayloadError):
                    Decoder().feed(build_frame(code, b"\x00" * n))

    def test_encode_rejects_bad_values(self):
        for bad in (-1, 0x10000000000000000, True, "1", 1.5, None):
            with self.assertRaises(PayloadError):
                Encoder().encode(bad, heartbeat.PingFrame)


class TestVersion(unittest.TestCase):
    def test_wire_format_csv_ascii(self):
        wire = Encoder().encode([1, 3], heartbeat.VersionFrame)
        self.assertEqual(wire[2], 0x20)
        self.assertEqual(wire[10:-4], b"1,3")
        self.assertEqual(Decoder().feed(wire)[0].value, [1, 3])

    def test_roundtrip_variants(self):
        for value in ([0], [2, 0, 9], [10, 20, 30, 255]):
            wire = Encoder().encode(value, heartbeat.VersionFrame)
            self.assertEqual(Decoder().feed(wire)[0].value, value)

    def test_empty_list_raises(self):
        with self.assertRaises(PayloadError):
            Encoder().encode([], heartbeat.VersionFrame)

    def test_encode_rejects_bad_values(self):
        for bad in ([1, "x"], [True], [-1], "1,3", (1, 3), 1, None):
            with self.assertRaises(PayloadError):
                Encoder().encode(bad, heartbeat.VersionFrame)

    def test_bad_payloads(self):
        for payload in (b"", b"1,,2", b"1,a", b",", b"\xff", b" 1", b"1 ",
                        b"-1", b"1.0"):
            with self.assertRaises(PayloadError):
                Decoder().feed(build_frame(0x20, payload))


if __name__ == "__main__":
    unittest.main()
