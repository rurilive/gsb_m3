"""0x81 新帧与混流解码器的测试。"""

import random
import unittest

from wirepack.errors import DecodeError, EncodeError, FrameDecodeError, WireError
from wirepack.frame import (
    FRAME_MAGIC,
    MAX_FRAME_SIZE,
    VARINT_MAX,
    Frame,
    encode_varint,
    pack_frame,
    unpack_frame,
)
from wirepack.records import Record, pack_record
from wirepack.stream import FrameDecoder, chunked


def sample_frames():
    return [
        Frame(0),
        Frame(2, b"hello"),
        Frame(4, b"", ext=[(7, b"k1"), (300, b"k2" * 30)]),
        Frame(VARINT_MAX, b"x" * 200, ext=[(VARINT_MAX, b"y")]),
    ]


def error_tuple(err):
    return (str(err.args[0]), err.offset, err.field,
            err.frame_index, err.resync_at)


class VarintTest(unittest.TestCase):
    def test_roundtrip_boundaries(self):
        for value in (0, 1, 127, 128, 300, 16383, 16384,
                      1 << 28, VARINT_MAX):
            self.assertEqual(
                unpack_frame(b"\x81" + encode_varint(value) + b"\x00\x00")[0].tag,
                value)

    def test_encoding_is_leb128(self):
        self.assertEqual(encode_varint(0), b"\x00")
        self.assertEqual(encode_varint(127), b"\x7f")
        self.assertEqual(encode_varint(128), b"\x80\x01")
        self.assertEqual(encode_varint(300), b"\xac\x02")

    def test_max_is_five_bytes(self):
        self.assertEqual(len(encode_varint(VARINT_MAX)), 5)

    def test_encode_rejects_bad_values(self):
        for bad in (-1, VARINT_MAX + 1, True, 1.5, "3"):
            with self.assertRaises(EncodeError):
                encode_varint(bad)


class FrameModelTest(unittest.TestCase):
    def test_nested_flag_follows_tag_low_bit(self):
        self.assertFalse(Frame(0).nested)
        self.assertTrue(Frame(1).nested)
        self.assertFalse(Frame(2).nested)
        self.assertTrue(Frame(3).nested)

    def test_unwrap_nested_payload(self):
        inner = Frame(0, b"core", ext=[(1, b"v")])
        outer = Frame(1, pack_frame(inner))
        self.assertEqual(outer.unwrap(), inner)

    def test_unwrap_requires_nested_flag(self):
        with self.assertRaises(WireError):
            Frame(0, b"x").unwrap()

    def test_unwrap_rejects_trailing_bytes(self):
        with self.assertRaises(DecodeError):
            Frame(1, pack_frame(Frame(0)) + b"\x00").unwrap()

    def test_equality_and_coercion(self):
        self.assertEqual(Frame(2, bytearray(b"ab"), ext=[(1, bytearray(b"c"))]),
                         Frame(2, b"ab", ext=[(1, b"c")]))
        self.assertNotEqual(Frame(2, b"ab"), Frame(2, b"ac"))
        self.assertNotEqual(Frame(2), Frame(3))


class PackUnpackTest(unittest.TestCase):
    def test_roundtrip(self):
        for frame in sample_frames():
            raw = pack_frame(frame)
            self.assertLessEqual(len(raw), MAX_FRAME_SIZE)
            decoded, next_offset = unpack_frame(raw)
            self.assertEqual(decoded, frame)
            self.assertEqual(next_offset, len(raw))

    def test_unpack_with_offset(self):
        frame = Frame(2, b"hello")
        blob = b"junk" + pack_frame(frame) + b"tail"
        decoded, next_offset = unpack_frame(blob, 4)
        self.assertEqual(decoded, frame)
        self.assertEqual(blob[next_offset:], b"tail")

    def test_pack_rejects_bad_tag(self):
        for bad in (-1, VARINT_MAX + 1, True, "2"):
            with self.assertRaises(EncodeError):
                pack_frame(Frame(bad))

    def test_pack_rejects_oversize_payload(self):
        with self.assertRaises(EncodeError):
            pack_frame(Frame(0, b"x" * (MAX_FRAME_SIZE + 1)))

    def test_pack_rejects_oversize_total(self):
        with self.assertRaises(EncodeError):
            pack_frame(Frame(0, b"x" * (MAX_FRAME_SIZE - 2),
                             ext=[(1, b"yyyy")]))

    def test_pack_rejects_bad_ext_key(self):
        with self.assertRaises(EncodeError):
            pack_frame(Frame(0, ext=[(-1, b"v")]))

    def test_unpack_rejects_bad_magic(self):
        with self.assertRaises(DecodeError) as ctx:
            unpack_frame(b"\x80\x00\x00")
        self.assertEqual(ctx.exception.field, "magic")

    def test_unpack_rejects_varint_over_five_bytes(self):
        with self.assertRaises(DecodeError) as ctx:
            unpack_frame(b"\x81" + b"\xff" * 6)
        self.assertEqual(ctx.exception.field, "tag")

    def test_unpack_rejects_oversize_payload_len(self):
        raw = b"\x81\x00" + encode_varint(MAX_FRAME_SIZE + 1)
        with self.assertRaises(DecodeError) as ctx:
            unpack_frame(raw)
        self.assertEqual(ctx.exception.field, "payload_len")

    def test_unpack_rejects_oversize_total(self):
        raw = b"\x81\x00" + encode_varint(MAX_FRAME_SIZE)
        with self.assertRaises(DecodeError) as ctx:
            unpack_frame(raw + b"x" * 10)
        self.assertEqual(ctx.exception.field, "frame")

    def test_unpack_rejects_oversize_ext_value_len(self):
        raw = b"\x81\x00\x00\x01\x01" + encode_varint(MAX_FRAME_SIZE + 1)
        with self.assertRaises(DecodeError) as ctx:
            unpack_frame(raw)
        self.assertEqual(ctx.exception.field, "ext[0].value_len")

    def test_unpack_reports_truncated_field(self):
        raw = pack_frame(Frame(2, b"hello", ext=[(1, b"v")]))
        for cut in range(1, len(raw)):
            with self.assertRaises(DecodeError) as ctx:
                unpack_frame(raw[:cut])
            self.assertIsNotNone(ctx.exception.field)


class FrameDecoderFeedTest(unittest.TestCase):
    def mixed_blob(self):
        parts = [pack_record(Record(11, "data", "n1"))]
        for frame in sample_frames():
            parts.append(pack_frame(frame))
            parts.append(pack_record(Record(12, "ack", "")))
        return b"".join(parts)

    def test_mixed_stream_one_shot(self):
        decoder = FrameDecoder()
        out = decoder.feed(self.mixed_blob())
        decoder.finish()
        self.assertEqual(decoder.records, 5)
        self.assertEqual(decoder.frames, 4)
        self.assertEqual(decoder.errors, [])
        self.assertIsInstance(out[0], Record)
        self.assertIsInstance(out[1], Frame)
        self.assertEqual(out[1], sample_frames()[0])

    def test_chunked_feed_matches_one_shot(self):
        blob = self.mixed_blob()
        for size in (1, 2, 3, 5, 7, 16, 40, len(blob)):
            decoder = FrameDecoder()
            seen = []
            for piece in chunked(blob, size):
                seen.extend(decoder.feed(piece))
            decoder.finish()
            self.assertEqual(len(seen), 9, "块大小 %d" % size)
            self.assertEqual(decoder.errors, [])
            self.assertEqual(decoder.pending, 0)

    def test_random_chunking_matches_one_shot(self):
        rng = random.Random(20260921)
        blob = self.mixed_blob()
        one_shot = FrameDecoder()
        expected = one_shot.feed(blob)
        one_shot.finish()
        for _ in range(20):
            decoder = FrameDecoder()
            seen = []
            pos = 0
            while pos < len(blob):
                step = rng.randint(1, 23)
                seen.extend(decoder.feed(blob[pos:pos + step]))
                pos += step
            decoder.finish()
            self.assertEqual(seen, expected)
            self.assertEqual(decoder.errors, one_shot.errors)

    def test_feed_rejects_non_bytes(self):
        with self.assertRaises(TypeError):
            FrameDecoder().feed("81")

    def test_record_error_resyncs_to_next_frame(self):
        blob = b"\xff" * 16 + pack_frame(Frame(2, b"ok"))
        decoder = FrameDecoder()
        out = decoder.feed(blob)
        decoder.finish()
        self.assertEqual(out, [Frame(2, b"ok")])
        self.assertEqual(len(decoder.errors), 1)
        err = decoder.errors[0]
        self.assertIsNone(err.frame_index)
        self.assertEqual(err.field, "seq")
        self.assertEqual(err.offset, 0)
        self.assertEqual(err.resync_at, 16)


class FrameDecoderErrorTest(unittest.TestCase):
    def good(self, tag=2):
        return pack_frame(Frame(tag, b"ok"))

    def oversize_len_prefix(self):
        # 编码里不能带 0x81，否则 resync 会落在垃圾数据自己身上
        raw = encode_varint(MAX_FRAME_SIZE + 1000)
        self.assertNotIn(FRAME_MAGIC, raw)
        return raw

    def test_oversize_length_prefix_resyncs(self):
        blob = self.good(2) + b"\x81\x00" + self.oversize_len_prefix() \
            + self.good(4)
        decoder = FrameDecoder()
        out = decoder.feed(blob)
        decoder.finish()
        self.assertEqual([f.tag for f in out], [2, 4])
        self.assertEqual(len(decoder.errors), 1)
        err = decoder.errors[0]
        self.assertIsInstance(err, FrameDecodeError)
        self.assertEqual(err.frame_index, 1)
        self.assertEqual(err.field, "payload_len")
        self.assertEqual(err.offset, len(self.good()))
        self.assertEqual(err.resync_at, len(blob) - len(self.good()))

    def test_varint_over_five_bytes_resyncs(self):
        blob = b"\x81" + b"\xff" * 6 + self.good(6)
        decoder = FrameDecoder()
        out = decoder.feed(blob)
        decoder.finish()
        self.assertEqual([f.tag for f in out], [6])
        self.assertEqual(len(decoder.errors), 1)
        self.assertEqual(decoder.errors[0].field, "tag")
        self.assertEqual(decoder.errors[0].frame_index, 0)
        self.assertEqual(decoder.errors[0].resync_at, 7)

    def test_resync_waits_for_next_magic_across_chunks(self):
        blob = b"\x81\x00" + self.oversize_len_prefix() + b"junk" \
            + self.good(8)
        decoder = FrameDecoder()
        self.assertEqual(decoder.feed(blob[:5]), [])
        self.assertEqual(decoder.errors, [])
        out = decoder.feed(blob[5:])
        decoder.finish()
        self.assertEqual([f.tag for f in out], [8])
        self.assertEqual(len(decoder.errors), 1)
        self.assertEqual(decoder.errors[0].resync_at, len(blob) - len(self.good()))

    def test_truncated_frame_reported_at_finish(self):
        raw = self.good()
        decoder = FrameDecoder()
        self.assertEqual(decoder.feed(raw + raw[:-2]), [Frame(2, b"ok")])
        decoder.finish()
        self.assertEqual(len(decoder.errors), 1)
        err = decoder.errors[0]
        self.assertEqual(err.frame_index, 1)
        self.assertEqual(err.offset, len(raw))
        self.assertEqual(err.resync_at, 2 * len(raw) - 2)
        self.assertEqual(decoder.pending, 0)

    def test_record_tail_reported_at_finish(self):
        decoder = FrameDecoder()
        decoder.feed(pack_record(Record(11, "data", "n1")) + b"\x00\x01")
        decoder.finish()
        self.assertEqual(len(decoder.errors), 1)
        err = decoder.errors[0]
        self.assertIsNone(err.frame_index)
        self.assertEqual(err.field, "record")
        self.assertEqual(err.resync_at, 18)

    def test_pending_never_exceeds_max_frame_size(self):
        rng = random.Random(7)
        blob = self.good() + b"\x81\x00" + self.oversize_len_prefix() \
            + bytes(rng.randrange(256) for _ in range(5000)) + self.good()
        decoder = FrameDecoder()
        pos = 0
        while pos < len(blob):
            step = rng.randint(1, 100)
            decoder.feed(blob[pos:pos + step])
            self.assertLessEqual(decoder.pending, MAX_FRAME_SIZE)
            pos += step
        decoder.finish()
        self.assertLessEqual(decoder.pending, MAX_FRAME_SIZE)

    def test_dirty_stream_chunked_matches_one_shot(self):
        rng = random.Random(931)
        parts = []
        for _ in range(30):
            roll = rng.randrange(6)
            if roll == 0:
                parts.append(b"\x81\x00" + encode_varint(MAX_FRAME_SIZE + 1000))
            elif roll == 1:
                parts.append(b"\x81" + b"\xff" * rng.randrange(5, 8))
            elif roll == 2:
                parts.append(pack_frame(Frame(rng.randrange(8), b"payload")))
            elif roll == 3:
                parts.append(pack_record(Record(rng.randrange(1000), "data")))
            elif roll == 4:
                parts.append(pack_frame(Frame(4, b"x", ext=[(1, b"v")]))[:3])
            else:
                parts.append(bytes(rng.randrange(256)
                                   for _ in range(rng.randrange(1, 20))))
        blob = b"".join(parts)
        one_shot = FrameDecoder()
        expected_items = one_shot.feed(blob)
        one_shot.finish()
        expected_errors = [error_tuple(e) for e in one_shot.errors]
        for _ in range(10):
            decoder = FrameDecoder()
            seen = []
            pos = 0
            while pos < len(blob):
                step = rng.randint(1, 40)
                seen.extend(decoder.feed(blob[pos:pos + step]))
                pos += step
            decoder.finish()
            self.assertEqual(seen, expected_items)
            self.assertEqual([error_tuple(e) for e in decoder.errors],
                             expected_errors)


if __name__ == "__main__":
    unittest.main()
