"""修复项的回归 + 随机对拍 + 截断 + 大文件内存/计时测试。

这些测试不改 tests/test_parser.py 的基线,只在它之外补:
- 线上翻车点的定点回归(跨块假前缀、分隔行切边界、收尾切开、
  完整 marker 后错字节、转义引号 filename、头部值尾随 CR)
- 同一份 body 用随机切点喂,逐字段和 reference.parse_all 对拍
- 半路断掉的流必须 ParseError,不能当成功
- 50MB 正文:解析器手里的峰值内存 < 8MB、10 秒内跑完
"""

import hashlib
import random
import time
import tracemalloc
import unittest

from chunkmime import MultipartParser, ParseError, PartCollector, parse_all

BOUNDARY = b"abc123"


def build_body(parts, boundary=BOUNDARY, preamble=b"", epilogue=b"\r\n"):
    """拼一份规范 multipart body;parts 是 (头部块, 正文)。"""
    out = bytearray(preamble)
    for head, data in parts:
        if out and not out.endswith(b"\r\n"):
            out += b"\r\n"
        out += b"--" + boundary + b"\r\n" + head + b"\r\n\r\n" + data
    out += b"\r\n--" + boundary + b"--" + epilogue
    return bytes(out)


def feed_cuts(parser, body, cuts):
    """按 cuts 偏移把 body 切块喂进去(cuts 是严格递增的内部偏移)。"""
    pos = 0
    for cut in cuts:
        parser.feed(body[pos:cut])
        pos = cut
    parser.feed(body[pos:])


def parse_with_cuts(body, cuts, boundary=BOUNDARY):
    collector = PartCollector()
    parser = MultipartParser(boundary, collector)
    feed_cuts(parser, body, cuts)
    parser.finish()
    return collector.parts()


def upload_head(filename=None, name="upload"):
    cd = b'Content-Disposition: form-data; name="' + name.encode() + b'"'
    if filename is not None:
        cd += b'; filename="' + filename + b'"'
    return cd + b"\r\nContent-Type: application/octet-stream"


class TestReportedBugs(unittest.TestCase):
    def test_body_with_boundary_prefix_split_across_chunks(self):
        # 正文里有分隔行的半截前缀,切点正好落在那一截后面
        payload = b"payload-1\r\n--abc12 follows more bytes\r\npayload-2"
        body = build_body([(upload_head(b"note.txt"), payload)])
        cut = body.index(b"\r\n--abc12 ") + len(b"\r\n--abc12")
        parts = parse_with_cuts(body, [cut])
        self.assertEqual(parts[0].data, payload)
        self.assertEqual(parts, parse_all(body, BOUNDARY))

    def test_real_marker_split_at_every_offset(self):
        # 真分隔行本体被切在块边界的每个位置都不能丢字段
        payload = b"abc\r\n--abc12X nope\r\ndef"
        body = build_body([
            (upload_head(b"a.bin"), payload),
            (upload_head(b"b.bin"), b"second"),
        ])
        marker = b"\r\n--" + BOUNDARY
        start = body.index(marker, len(payload))
        for delta in range(len(marker) + 3):
            parts = parse_with_cuts(body, [start + delta])
            self.assertEqual(len(parts), 2, delta)
            self.assertEqual(parts[0].data, payload, delta)
            self.assertEqual(parts[1].data, b"second", delta)

    def test_closing_marker_split_at_every_offset(self):
        # 收尾分隔行(含 --)被切开时最后一段不能丢
        body = build_body([(upload_head(b"f.bin"), b"final bytes")])
        close = body.rindex(b"\r\n--" + BOUNDARY + b"--")
        closing = b"\r\n--" + BOUNDARY + b"--"
        for delta in range(len(closing) + 1):
            parts = parse_with_cuts(body, [close + delta])
            self.assertEqual(len(parts), 1, delta)
            self.assertEqual(parts[0].data, b"final bytes", delta)
            self.assertEqual(parts, parse_all(body, BOUNDARY), delta)

    def test_full_marker_followed_by_other_byte_is_body(self):
        # 完整 marker 后面既不是 -- 也不是 CRLF:只是正文
        payload = b"x\r\n--" + BOUNDARY + b"z\r\n--" + BOUNDARY + b"9 tail"
        body = build_body([(upload_head(b"f.bin"), payload)])
        for cut in range(len(body) + 1):
            parts = parse_with_cuts(body, [cut])
            self.assertEqual(parts[0].data, payload, cut)
        self.assertEqual(parse_all(body, BOUNDARY)[0].data, payload)

    def test_escaped_quote_and_backslash_in_filename(self):
        # 线上字节是 a\"qu\ote.txt -> 参数值 a"qu\ote.txt
        filename = b'a\\"qu\\\\ote.txt'
        body = build_body([(upload_head(filename), b"x")])
        parts = parse_with_cuts(body, [])
        self.assertEqual(parts[0].filename, 'a"qu\\ote.txt')
        self.assertEqual(parts, parse_all(body, BOUNDARY))

    def test_header_split_block_has_no_trailing_cr(self):
        # 头部块的结束空行被切在各种位置,值不能多出尾随回车
        body = build_body([(upload_head(b"x.bin"), b"z")])
        blank = body.index(b"\r\n\r\n")
        for delta in range(-4, 5):
            cut = max(1, blank + delta)
            parts = parse_with_cuts(body, [cut])
            self.assertEqual(parts[0].headers["content-type"],
                             "application/octet-stream", cut)

    def test_truncated_stream_raises(self):
        body = build_body([(upload_head(b"x.bin"), b"some payload")])
        # 从不同长度截断:开场、收尾分隔行被切到一半的各种位置
        close = body.rindex(b"\r\n--" + BOUNDARY + b"--")
        closing = b"\r\n--" + BOUNDARY + b"--"
        for end in (1, len(b"--" + BOUNDARY), close, close + 3,
                    close + len(closing) - 1):
            parser = MultipartParser(BOUNDARY, PartCollector())
            parser.feed(body[:end])
            with self.assertRaises(ParseError):
                parser.finish()
        # 收尾 -- 到齐即完整,epilogue 缺不缺不影响
        parser = MultipartParser(BOUNDARY, PartCollector())
        parser.feed(body[:close + len(closing)])
        parser.finish()

    def test_malformed_boundary_line_raises(self):
        # 完整 marker 后面跟错字节,且后面再没有合法分隔行
        body = (b"--" + BOUNDARY + b"\r\n"
                + upload_head(b"x.bin") + b"\r\n\r\npayload"
                + b"\r\n--" + BOUNDARY + b"Xjunk")
        parser = MultipartParser(BOUNDARY, PartCollector())
        parser.feed(body)
        with self.assertRaises(ParseError):
            parser.finish()


# ---- 随机对拍 ----

FIELD_NAMES = ["title", "tags", "note", "x", "field-2"]
MARKER = b"\r\n--" + BOUNDARY


def make_filename(rng):
    raw = bytes(rng.choice([0x61, 0x62, 0x63, 0x20, 0x2e, 0x2d])
                for _ in range(rng.randrange(1, 8)))
    style = rng.randrange(3)
    if style == 0:
        quoted = raw.replace(b"\\", b"\\\\").replace(b'"', b'\\"')
        return b'"' + quoted + b'"', raw.decode("latin-1")
    if style == 1:
        return raw, raw.decode("latin-1").strip()
    escaped = raw.replace(b"\\", b"\\\\").replace(b'"', b'\\"')
    return b'"' + escaped + b'"', raw.decode("latin-1")


def make_head(rng):
    cd = (b'Content-Disposition: form-data; name="'
          + rng.choice(FIELD_NAMES).encode() + b'"')
    if rng.random() < 0.7:
        token, _ = make_filename(rng)
        cd += b"; filename=" + token
    lines = [cd]
    if rng.random() < 0.6:
        lines.append(b"Content-Type: " + rng.choice([
            b"text/plain", b"application/octet-stream", b"image/png"]))
    if rng.random() < 0.2:
        lines.append(b"X-Note: " + bytes(rng.randrange(0x21, 0x7f)
                                         for _ in range(rng.randrange(0, 12))))
    return b"\r\n".join(lines)


def make_payload(rng):
    kind = rng.randrange(7)
    if kind == 0:
        return b""
    if kind == 1:
        return rng.randbytes(rng.randrange(1, 200))
    if kind == 2:
        return b"\r\n" * rng.randrange(1, 6)
    if kind == 3:
        return (b"pre " + MARKER[:rng.randrange(0, len(MARKER))]
                + b" post " + rng.randbytes(rng.randrange(0, 30)))
    if kind == 4:
        return MARKER + b"X" + rng.randbytes(rng.randrange(0, 20))
    if kind == 5:
        return b"--" + BOUNDARY + bytes(rng.randrange(0x41, 0x5b)
                                        for _ in range(rng.randrange(0, 10)))
    return (b"line\r\n" * rng.randrange(1, 8)
            + bytes(rng.randrange(0x20, 0x7f)
                    for _ in range(rng.randrange(0, 40))))


def make_body(rng):
    parts = []
    for _ in range(rng.randrange(1, 5)):
        parts.append((make_head(rng), make_payload(rng)))
    preamble = b""
    if rng.random() < 0.3:
        preamble = rng.randbytes(rng.randrange(0, 20))
    epilogue = (b"" if rng.random() < 0.5
                else rng.randbytes(rng.randrange(0, 12)))
    return build_body(parts, preamble=preamble, epilogue=epilogue)


def random_cuts(rng, body):
    count = rng.randrange(0, 8)
    return sorted(rng.randrange(1, len(body)) for _ in range(count))


class TestRandomDifferential(unittest.TestCase):
    BODIES = 60
    RANDOM_CUTS_PER_BODY = 20

    def test_random_cuts_match_reference(self):
        rng = random.Random(20260921)
        for _ in range(self.BODIES):
            body = make_body(rng)
            expected = parse_all(body, BOUNDARY)
            # 每个内部偏移都做一次两块对拍,专门压跨块状态
            for cut in range(1, len(body)):
                self.assertEqual(parse_with_cuts(body, [cut]), expected,
                                 (cut, body))
            # 再随机多切几刀
            for _ in range(self.RANDOM_CUTS_PER_BODY):
                cuts = random_cuts(rng, body)
                self.assertEqual(parse_with_cuts(body, cuts), expected,
                                 (cuts, body))

    def test_byte_by_byte_agrees(self):
        rng = random.Random(99)
        for _ in range(6):
            body = make_body(rng)
            expected = parse_all(body, BOUNDARY)
            parts = parse_with_cuts(body, list(range(1, len(body))))
            self.assertEqual(parts, expected)


class TestTruncatedStreams(unittest.TestCase):
    def test_random_truncations_always_error(self):
        rng = random.Random(4242)
        for _ in range(8):
            body = make_body(rng)
            # 完整 body 必须先能过基准
            parse_all(body, BOUNDARY)
            # 收尾 -- 到齐之前的每个真前缀都算半路断掉
            complete = body.index(b"--" + BOUNDARY + b"--",
                                  body.index(b"--" + BOUNDARY)) + len(
                b"--" + BOUNDARY + b"--")
            for end in range(1, complete):
                parser = MultipartParser(BOUNDARY, PartCollector())
                parser.feed(body[:end])
                with self.assertRaises(ParseError):
                    parser.finish()
            # 真前缀再随机切块喂,同样必须报错
            for _ in range(60):
                end = rng.randrange(1, complete)
                prefix = body[:end]
                cuts = sorted({rng.randrange(1, len(prefix))
                               for _ in range(rng.randrange(0, 5))}
                              if len(prefix) > 1 else [])
                parser = MultipartParser(BOUNDARY, PartCollector())
                feed_cuts(parser, prefix, cuts)
                with self.assertRaises(ParseError):
                    parser.finish()


class HashCollector:
    """大文件压测用 sink:只留哈希,不存正文。"""

    def __init__(self):
        self.parts = 0
        self.hash = hashlib.sha256()
        self.bytes_in = 0

    def begin_part(self, headers, params):
        self.parts += 1

    def write(self, data):
        self.bytes_in += len(data)
        self.hash.update(bytes(data))

    def end_part(self):
        pass


class TestLargeFile(unittest.TestCase):
    SIZE = 50 * 1024 * 1024
    CHUNK = 64 * 1024

    def _payload(self):
        # 固定块周期内容,周期里故意放分隔行前缀和假分隔行压跨块逻辑
        tile = (b"the quick brown fox jumps over\r\n--abc1"
                + bytes(range(256)) + b"\r\n--" + BOUNDARY + b"X pad ")
        out = bytearray()
        while len(out) < self.SIZE:
            out += tile
        return bytes(out[:self.SIZE])

    def test_50mb_memory_time_and_content(self):
        payload = self._payload()
        body = build_body([(upload_head(b"big.bin"), payload),
                           (b'Content-Disposition: form-data; name="end"',
                            b"bye")])
        expected_digest = hashlib.sha256(payload + b"bye").digest()
        tracemalloc.start()
        sink = HashCollector()
        parser = MultipartParser(BOUNDARY, sink)
        start = time.monotonic()
        for pos in range(0, len(body), self.CHUNK):
            parser.feed(body[pos:pos + self.CHUNK])
        parser.finish()
        elapsed = time.monotonic() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertEqual(sink.parts, 2)
        self.assertEqual(sink.bytes_in, self.SIZE + 3)
        self.assertEqual(sink.hash.digest(), expected_digest)
        self.assertLess(peak, 8 * 1024 * 1024,
                        "解析器峰值内存 %d 字节超过 8MB" % peak)
        self.assertLess(elapsed, 10.0,
                        "50MB 解析耗时 %.2fs 超过 10s" % elapsed)


if __name__ == "__main__":
    unittest.main()
