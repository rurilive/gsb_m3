"""framec 现有行为的锁定测试。"""

import struct
import unittest
import zlib

from framec import (
    REGISTRY,
    AckFrame,
    CrcError,
    DataFrame,
    Decoder,
    Encoder,
    FrameError,
    FrameType,
    HeaderError,
    JsonFrame,
    PayloadError,
    UnknownTypeError,
    register,
)
from framec.registry import HEADER_LEN, MAGIC


def build_frame(type_code, payload, seq=1, flags=0):
    """按线格式手工组一帧（CRC 正确），用于构造解码侧的边界输入。"""
    body = MAGIC + struct.pack(">BBHI", type_code, flags, len(payload), seq) + payload
    return body + struct.pack(">I", zlib.crc32(body))


class TestWireFormat(unittest.TestCase):
    def test_data_frame_exact_bytes(self):
        wire = Encoder().encode("A")
        self.assertEqual(wire[:2], b"FC")
        self.assertEqual(wire[2], 0x01)
        self.assertEqual(wire[3], 0)
        self.assertEqual(struct.unpack(">H", wire[4:6])[0], 1)
        self.assertEqual(struct.unpack(">I", wire[6:10])[0], 1)
        self.assertEqual(wire[10:-4], b"A")
        self.assertEqual(struct.unpack(">I", wire[-4:])[0], zlib.crc32(wire[:-4]))

    def test_header_len_is_10_and_total(self):
        wire = Encoder().encode("hello")
        self.assertEqual(HEADER_LEN, 10)
        self.assertEqual(len(wire), HEADER_LEN + 5 + 4)

    def test_multi_byte_fields_big_endian(self):
        wire = Encoder().encode("héllo")  # UTF-8 占 6 字节
        self.assertEqual(struct.unpack(">H", wire[4:6])[0], 6)
        wire = Encoder(seq_start=0x01020304).encode("A")
        self.assertEqual(wire[6:10], b"\x01\x02\x03\x04")

    def test_seq_auto_increments(self):
        enc = Encoder()
        self.assertEqual(struct.unpack(">I", enc.encode("a")[6:10])[0], 1)
        self.assertEqual(struct.unpack(">I", enc.encode("b")[6:10])[0], 2)
        self.assertEqual(struct.unpack(">I", enc.encode(9, AckFrame)[6:10])[0], 3)

    def test_seq_start_respected(self):
        enc = Encoder(seq_start=100)
        self.assertEqual(struct.unpack(">I", enc.encode("a")[6:10])[0], 100)

    def test_ftype_by_instance_class_and_code_identical(self):
        a = Encoder().encode("x", DataFrame())
        b = Encoder().encode("x", DataFrame)
        c = Encoder().encode("x", 0x01)
        self.assertEqual(a, b)
        self.assertEqual(b, c)

    def test_encoder_unknown_type_code_raises(self):
        with self.assertRaises(UnknownTypeError):
            Encoder().encode("x", ftype=0x7F)

    def test_encoder_cannot_infer_int(self):
        with self.assertRaises(FrameError):
            Encoder().encode(5)

    def test_encoder_cannot_infer_list(self):
        with self.assertRaises(FrameError):
            Encoder().encode([1, 2])

    def test_encoder_bad_ftype_object(self):
        with self.assertRaises(FrameError):
            Encoder().encode("x", ftype="DATA")


class TestCrcPipeline(unittest.TestCase):
    def test_corrupt_payload_raises_crc_error(self):
        bad = bytearray(Encoder().encode("tampered"))
        bad[10] ^= 0xFF
        with self.assertRaises(CrcError):
            Decoder().feed(bytes(bad))

    def test_corrupt_header_raises_crc_error(self):
        bad = bytearray(Encoder().encode("tampered"))
        bad[7] ^= 0xFF  # seq 字节
        with self.assertRaises(CrcError):
            Decoder().feed(bytes(bad))

    def test_crc_error_consumes_frame_stream_continues(self):
        enc = Encoder()
        dec = Decoder()
        good = enc.encode("ok")
        bad = bytearray(enc.encode("x"))
        bad[10] ^= 0xFF
        with self.assertRaises(CrcError):
            dec.feed(bytes(bad) + good)
        self.assertEqual([f.value for f in dec.feed(b"")], ["ok"])

    def test_unknown_type_code_silently_skipped(self):
        good = Encoder().encode("after")
        stream = build_frame(0x7F, b"\x01\x02") + good
        frames = Decoder().feed(stream)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].type_code, 0x01)
        self.assertEqual(frames[0].value, "after")


class TestDecoder(unittest.TestCase):
    def test_incomplete_frame_returns_empty(self):
        wire = Encoder().encode("hello")
        dec = Decoder()
        self.assertEqual(dec.feed(wire[:5]), [])
        self.assertEqual(dec.feed(wire[5:12]), [])
        frames = dec.feed(wire[12:])
        self.assertEqual([f.value for f in frames], ["hello"])

    def test_byte_by_byte_feed(self):
        wire = Encoder(seq_start=7).encode("abc")
        dec = Decoder()
        out = []
        for i in range(len(wire)):
            out += dec.feed(wire[i:i + 1])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].seq, 7)
        self.assertEqual(out[0].value, "abc")

    def test_multiple_frames_in_one_feed(self):
        enc = Encoder()
        stream = enc.encode("a") + enc.encode({"k": 1}) + enc.encode(3, AckFrame)
        frames = Decoder().feed(stream)
        self.assertEqual([f.type_name for f in frames], ["DATA", "JSON", "ACK"])
        self.assertEqual([f.value for f in frames], ["a", {"k": 1}, 3])

    def test_bad_magic_raises_header_error(self):
        wire = bytearray(Encoder().encode("a"))
        wire[0] = ord("X")
        dec = Decoder()
        with self.assertRaises(HeaderError):
            dec.feed(bytes(wire))
        with self.assertRaises(HeaderError):  # 缓冲未消费，垃圾仍在前
            dec.feed(b"")

    def test_nonzero_flags_raise_header_error(self):
        with self.assertRaises(HeaderError):
            Decoder().feed(build_frame(0x01, b"a", flags=1))

    def test_declared_length_over_max_raises_header_error(self):
        body = MAGIC + struct.pack(">BBHI", 0x01, 0, 4097, 1)
        wire = body + struct.pack(">I", zlib.crc32(body))
        with self.assertRaises(HeaderError):
            Decoder().feed(wire)

    def test_bad_utf8_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x01, b"\xff\xfe"))

    def test_short_ack_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x03, b"\x00\x00\x01"))

    def test_long_ack_payload_raises_payload_error(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x03, b"\x00" * 5))

    def test_frame_attributes_and_repr(self):
        frame = Decoder().feed(Encoder(seq_start=9).encode("hi"))[0]
        self.assertEqual(frame.type_code, 0x01)
        self.assertEqual(frame.type_name, "DATA")
        self.assertEqual(frame.seq, 9)
        self.assertEqual(frame.value, "hi")
        self.assertEqual(repr(frame), "Frame<DATA seq=9 value='hi'>")


class TestDataFrame(unittest.TestCase):
    def test_roundtrip_unicode(self):
        wire = Encoder().encode("信号帧")
        self.assertEqual(Decoder().feed(wire)[0].value, "信号帧")

    def test_empty_string(self):
        wire = Encoder().encode("")
        self.assertEqual(struct.unpack(">H", wire[4:6])[0], 0)
        self.assertEqual(Decoder().feed(wire)[0].value, "")

    def test_encode_rejects_non_str(self):
        for bad in (123, b"x", None, {"a": 1}):
            with self.assertRaises(PayloadError):
                Encoder().encode(bad, DataFrame)


class TestJsonFrame(unittest.TestCase):
    def test_roundtrip_nested(self):
        value = {"op": "pub", "ch": "ns/a", "n": [1, 2, 3], "u": "符号"}
        wire = Encoder().encode(value)
        self.assertEqual(Decoder().feed(wire)[0].value, value)

    def test_empty_dict(self):
        wire = Encoder().encode({})
        self.assertEqual(wire[10:-4], b"{}")
        self.assertEqual(Decoder().feed(wire)[0].value, {})

    def test_encode_rejects_unserializable(self):
        with self.assertRaises(PayloadError):
            Encoder().encode({"f": object()}, JsonFrame)

    def test_decode_rejects_garbage_payload(self):
        with self.assertRaises(PayloadError):
            Decoder().feed(build_frame(0x02, b"not json"))


class TestAckFrame(unittest.TestCase):
    def test_roundtrip_boundaries(self):
        for value in (0, 1, 0xFFFFFFFF):
            wire = Encoder().encode(value, AckFrame)
            self.assertEqual(wire[10:-4], struct.pack(">I", value))
            self.assertEqual(Decoder().feed(wire)[0].value, value)

    def test_encode_rejects_bool(self):
        with self.assertRaises(PayloadError):
            Encoder().encode(True, AckFrame)

    def test_encode_rejects_negative(self):
        with self.assertRaises(PayloadError):
            Encoder().encode(-1, AckFrame)

    def test_encode_rejects_over_u32(self):
        with self.assertRaises(PayloadError):
            Encoder().encode(0x100000000, AckFrame)

    def test_encode_rejects_non_int(self):
        with self.assertRaises(PayloadError):
            Encoder().encode("42", AckFrame)


class TestRegistry(unittest.TestCase):
    def test_builtin_types_registered(self):
        self.assertEqual(sorted(REGISTRY), [0x01, 0x02, 0x03])
        self.assertEqual(REGISTRY[0x01].NAME, "DATA")
        self.assertEqual(REGISTRY[0x02].NAME, "JSON")
        self.assertEqual(REGISTRY[0x03].NAME, "ACK")

    def test_duplicate_type_code_raises(self):
        with self.assertRaises(FrameError):
            register(DataFrame())

    def test_base_class_type_zero_not_registered(self):
        self.assertIsInstance(REGISTRY[0x01], FrameType)
        self.assertNotIn(0x00, REGISTRY)

    def test_payload_size_limit(self):
        enc = Encoder()
        wire = enc.encode("x" * 4096)
        self.assertEqual(Decoder().feed(wire)[0].value, "x" * 4096)
        with self.assertRaises(PayloadError):
            enc.encode("x" * 4097)


if __name__ == "__main__":
    unittest.main()
