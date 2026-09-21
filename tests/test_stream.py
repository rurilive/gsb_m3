"""seal_stream / unseal_stream / rotate_file 的锁定测试。"""

import io
import os
import tempfile
import time
import unittest

from vaultfile import (
    AuthError,
    UnknownKeyError,
    VaultError,
    rotate_file,
    seal,
    seal_stream,
    unseal,
    unseal_stream,
)
from vaultfile.format import (
    CHUNK_HEADER_LEN,
    FMT_V2,
    MAGIC_V2,
    TAG_LEN,
    V2_HEADER_LEN,
)
from vaultfile.vault import DEFAULT_CHUNK_SIZE

KEY = b"vault-unit-test-key-01"
OTHER_KEY = b"vault-unit-test-key-02"
THIRD_KEY = b"vault-unit-test-key-03"
KEYRING = {1: KEY, 2: OTHER_KEY, 3: THIRD_KEY}


def seal_blob(data, key=KEY, key_version=1, chunk_size=16):
    dest = io.BytesIO()
    seal_stream(dest, io.BytesIO(data), key, key_version=key_version,
                chunk_size=chunk_size)
    return dest.getvalue()


def unseal_blob(blob, key=KEY):
    return b"".join(unseal_stream(io.BytesIO(blob), key))


def iter_frames(blob):
    """按 v2 布局切成 [(块号, flags, 块头, 密文, tag)]，调包测试用。"""
    frames = []
    pos = V2_HEADER_LEN
    while pos < len(blob):
        header = blob[pos:pos + CHUNK_HEADER_LEN]
        index = int.from_bytes(header[0:4], "big")
        flags = header[4]
        length = int.from_bytes(header[5:9], "big")
        body_start = pos + CHUNK_HEADER_LEN
        ciphertext = blob[body_start:body_start + length]
        tag = blob[body_start + length:body_start + length + TAG_LEN]
        frames.append((index, flags, header, ciphertext, tag))
        pos = body_start + length + TAG_LEN
    return frames


class BoundedReader:
    """每次 read 不许超过 limit：卡死峰值内存只跟块大小走。"""

    def __init__(self, data, limit):
        self._data = data
        self._pos = 0
        self.limit = limit
        self.max_read = 0

    def read(self, size=-1):
        if size is None or size < 0:
            raise AssertionError("unbounded read(-1) on streaming source")
        if size > self.limit:
            raise AssertionError(
                "read %d bytes with chunk-bounded limit %d" % (size, self.limit)
            )
        self.max_read = max(self.max_read, size)
        piece = self._data[self._pos:self._pos + size]
        self._pos += len(piece)
        return piece


class BoundedWriter:
    def __init__(self, limit):
        self.parts = []
        self.limit = limit
        self.max_write = 0

    def write(self, data):
        if len(data) > self.limit:
            raise AssertionError(
                "write %d bytes with chunk-bounded limit %d"
                % (len(data), self.limit)
            )
        self.max_write = max(self.max_write, len(data))
        self.parts.append(data)
        return len(data)

    def getvalue(self):
        return b"".join(self.parts)


class TestSealStreamRoundTrip(unittest.TestCase):
    def test_basic_round_trip(self):
        data = bytes(range(256))
        blob = seal_blob(data, chunk_size=32)
        self.assertEqual(blob[:4], MAGIC_V2)
        self.assertEqual(blob[4], FMT_V2)
        self.assertEqual(unseal_blob(blob), data)

    def test_empty_file_round_trip(self):
        blob = seal_blob(b"", chunk_size=16)
        frames = iter_frames(blob)
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0][0], 0)
        self.assertTrue(frames[0][1] & 1)
        self.assertEqual(frames[0][3], b"")
        self.assertEqual(unseal_blob(blob), b"")

    def test_sizes_around_chunk_boundaries(self):
        for chunk_size in (1, 7, 16, 64):
            for extra in range(0, chunk_size + 2):
                data = bytes((i % 251 for i in range(chunk_size * 3 + extra)))
                blob = seal_blob(data, chunk_size=chunk_size)
                self.assertEqual(unseal_blob(blob), data)

    def test_exact_multiple_ends_with_full_final_chunk(self):
        data = b"x" * 64
        blob = seal_blob(data, chunk_size=16)
        frames = iter_frames(blob)
        # 非空文件：4 个满块，第 4 块带 final 标记；空文件才用零长末块。
        self.assertEqual([f[0] for f in frames], [0, 1, 2, 3])
        self.assertEqual(len(frames[-1][3]), 16)
        self.assertTrue(frames[-1][1] & 1)

    def test_short_reads_from_stream_are_handled(self):
        data = os.urandom(200)

        class TrickleReader:
            def __init__(self):
                self.buf = data

            def read(self, size=-1):
                if size <= 0:
                    return b""
                take = min(size, 3)
                piece, self.buf = self.buf[:take], self.buf[take:]
                return piece

        dest = io.BytesIO()
        seal_stream(dest, TrickleReader(), KEY, chunk_size=16)
        self.assertEqual(unseal_blob(dest.getvalue()), data)

    def test_returns_bytes_written(self):
        data = os.urandom(50)
        dest = io.BytesIO()
        written = seal_stream(dest, io.BytesIO(data), KEY, chunk_size=16)
        self.assertEqual(written, len(dest.getvalue()))

    def test_default_chunk_size_is_large(self):
        self.assertGreaterEqual(DEFAULT_CHUNK_SIZE, 1 << 16)

    def test_rejects_bad_chunk_size(self):
        for bad in (0, -1, "16", 1.5):
            with self.assertRaises(ValueError):
                seal_stream(io.BytesIO(), io.BytesIO(b"x"), KEY, chunk_size=bad)


class TestStreamMemoryBound(unittest.TestCase):
    def test_seal_reads_never_exceed_chunk_size(self):
        data = os.urandom(10_000)
        chunk_size = 64
        reader = BoundedReader(data, chunk_size)
        writer = BoundedWriter(chunk_size)
        seal_stream(writer, reader, KEY, chunk_size=chunk_size)
        self.assertEqual(unseal_blob(writer.getvalue()), data)
        self.assertLessEqual(reader.max_read, chunk_size)
        self.assertLessEqual(writer.max_write, chunk_size)

    def test_unseal_reads_stay_chunk_bounded(self):
        data = os.urandom(10_000)
        blob = seal_blob(data, chunk_size=64)
        reader = BoundedReader(blob, max(64, TAG_LEN))
        out = b"".join(unseal_stream(reader, KEY))
        self.assertEqual(out, data)
        self.assertLessEqual(reader.max_read, max(64, TAG_LEN))


class TestTamperEveryByte(unittest.TestCase):
    """翻一个字节就得炸一个：容器里每个字节翻 0x01 都必须解不开。"""

    def test_flip_every_single_byte(self):
        data = "期初余额 1204332.00 元".encode("utf-8") * 3
        blob = seal_blob(data, chunk_size=16)
        self.assertGreater(len(blob), V2_HEADER_LEN)
        for pos in range(len(blob)):
            broken = bytearray(blob)
            broken[pos] ^= 0x01
            with self.assertRaises(VaultError, msg="byte %d flipped" % pos):
                b"".join(unseal_stream(io.BytesIO(bytes(broken)), KEY))

    def test_auth_error_carries_chunk_index(self):
        blob = seal_blob(b"x" * 80, chunk_size=16)
        frames = iter_frames(blob)
        pos = V2_HEADER_LEN
        hit = False
        for index, _flags, header, ciphertext, _tag in frames:
            if index == 2:
                pos += CHUNK_HEADER_LEN
                hit = True
                break
            pos += CHUNK_HEADER_LEN + len(ciphertext) + TAG_LEN
        self.assertTrue(hit)
        broken = bytearray(blob)
        broken[pos] ^= 0x01
        try:
            unseal_blob(bytes(broken))
        except AuthError as exc:
            self.assertEqual(exc.chunk_index, 2)
            self.assertIn("chunk 2", str(exc))
        else:
            self.fail("tampered chunk unsealed")


class TestTruncationAndStructure(unittest.TestCase):
    def test_truncated_at_every_length_fails(self):
        blob = seal_blob(b"y" * 70, chunk_size=16)
        for cut in range(0, len(blob)):
            with self.assertRaises(VaultError, msg="cut at %d" % cut):
                unseal_blob(blob[:cut])

    def test_appended_bytes_after_final_fail(self):
        blob = bytearray(seal_blob(b"z" * 40, chunk_size=16))
        blob += b"extra"
        with self.assertRaises(AuthError):
            unseal_blob(bytes(blob))

    def test_non_final_chunk_with_wrong_length_fails(self):
        blob = bytearray(seal_blob(b"a" * 40, chunk_size=16))
        blob[V2_HEADER_LEN + 5:V2_HEADER_LEN + 9] = (15).to_bytes(4, "big")
        with self.assertRaises(AuthError):
            unseal_blob(bytes(blob))

    def test_chunk_size_field_tamper_fails(self):
        blob = bytearray(seal_blob(b"a" * 40, chunk_size=16))
        blob[V2_HEADER_LEN - 1] ^= 0x01
        with self.assertRaises(VaultError):
            unseal_blob(bytes(blob))

    def test_garbage_fails(self):
        for bad in (b"", b"not a container", os.urandom(100)):
            with self.assertRaises(AuthError):
                list(unseal_stream(io.BytesIO(bad), KEY))


class TestChunkSwapAndReorder(unittest.TestCase):
    def test_swap_two_chunk_bodies_fails(self):
        blob = seal_blob(bytes(range(256)) * 2, chunk_size=16)
        frames = iter_frames(blob)
        rebuilt = bytearray(blob[:V2_HEADER_LEN])
        bodies = [(h, c, t) for _i, _f, h, c, t in frames]
        bodies[1], bodies[2] = bodies[2], bodies[1]
        for h, c, t in bodies:
            rebuilt += h + c + t
        with self.assertRaises(AuthError):
            unseal_blob(bytes(rebuilt))

    def test_drop_a_chunk_fails(self):
        blob = seal_blob(bytes(range(256)), chunk_size=16)
        frames = iter_frames(blob)
        rebuilt = bytearray(blob[:V2_HEADER_LEN])
        for index, _f, h, c, t in frames:
            if index == 3:
                continue
            rebuilt += h + c + t
        with self.assertRaises(AuthError):
            unseal_blob(bytes(rebuilt))

    def test_chunk_from_another_file_fails(self):
        blob_a = seal_blob(b"AAAA" * 20, chunk_size=16)
        blob_b = seal_blob(b"BBBB" * 20, chunk_size=16)
        frames_a = iter_frames(blob_a)
        frames_b = iter_frames(blob_b)
        rebuilt = bytearray(blob_a[:V2_HEADER_LEN])
        for index, _f, h, c, t in frames_a:
            if index == 2:
                _i, _fl, h, c, t = frames_b[2]
            rebuilt += h + c + t
        with self.assertRaises(AuthError):
            unseal_blob(bytes(rebuilt))

    def test_old_frames_under_another_file_header_fail(self):
        blob_a = seal_blob(b"AAAA" * 20, chunk_size=16)
        blob_b = seal_blob(b"BBBB" * 20, chunk_size=16)
        frames_a = iter_frames(blob_a)
        rebuilt = bytearray(blob_b[:V2_HEADER_LEN])
        for _i, _f, h, c, t in frames_a:
            rebuilt += h + c + t
        with self.assertRaises(VaultError):
            unseal_blob(bytes(rebuilt))


class TestKeyVersions(unittest.TestCase):
    def test_seal_with_named_version_and_unseal(self):
        data = b"versioned report" * 4
        blob = seal_blob(data, key=KEYRING, key_version=2)
        self.assertEqual(blob[V2_HEADER_LEN + 9], 2)
        self.assertEqual(unseal_blob(blob, KEYRING), data)

    def test_missing_version_raises_unknown_key(self):
        blob = seal_blob(b"x" * 40, key={2: OTHER_KEY}, key_version=2,
                         chunk_size=16)
        with self.assertRaises(UnknownKeyError):
            unseal_blob(blob, {1: KEY})

    def test_wrong_key_for_version_fails(self):
        blob = seal_blob(b"x" * 40, key={2: OTHER_KEY}, key_version=2,
                         chunk_size=16)
        with self.assertRaises(AuthError):
            unseal_blob(blob, {2: KEY})

    def test_seal_rejects_version_missing_from_keyring(self):
        with self.assertRaises(UnknownKeyError):
            seal_blob(b"x", key={1: KEY}, key_version=9)

    def test_bare_key_ignores_version(self):
        blob = seal_blob(b"x" * 40, key=KEY, key_version=42, chunk_size=16)
        self.assertEqual(unseal_blob(blob, KEY), b"x" * 40)


class TestNonceDerivation(unittest.TestCase):
    def test_same_plaintext_chunks_have_distinct_ciphertext(self):
        blob = seal_blob(b"same" * 40, chunk_size=16)
        frames = iter_frames(blob)
        bodies = [f[3] for f in frames if len(f[3]) == 16]
        self.assertEqual(len(bodies), 10)
        self.assertEqual(len(set(bodies)), len(bodies))

    def test_same_plaintext_two_files_have_distinct_ciphertext(self):
        first = seal_blob(b"same" * 40, chunk_size=16)
        second = seal_blob(b"same" * 40, chunk_size=16)
        self.assertNotEqual(first, second)
        first_frames = iter_frames(first)
        second_frames = iter_frames(second)
        for (_, _, _, c1, _), (_, _, _, c2, _) in zip(first_frames, second_frames):
            self.assertNotEqual(c1, c2)


class TestV1Compat(unittest.TestCase):
    def test_legacy_single_chunk_container_unseals_via_stream(self):
        data = MESSAGE = "期初余额 1204332.00 元".encode("utf-8")
        blob = seal(data, KEY)
        self.assertEqual(b"".join(unseal_stream(io.BytesIO(blob), KEY)), data)

    def test_legacy_container_tampered_still_rejected_via_stream(self):
        blob = bytearray(seal(b"legacy payload" * 4, KEY))
        blob[len(blob) // 2] ^= 0x01
        with self.assertRaises(AuthError):
            b"".join(unseal_stream(io.BytesIO(bytes(blob)), KEY))

    def test_legacy_container_wrong_key_via_stream(self):
        blob = seal(b"legacy payload", KEY)
        with self.assertRaises(AuthError):
            b"".join(unseal_stream(io.BytesIO(blob), OTHER_KEY))

    def test_legacy_empty_container_via_stream(self):
        blob = seal(b"", KEY)
        self.assertEqual(b"".join(unseal_stream(io.BytesIO(blob), KEY)), b"")


class TestRotateFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "report.vlt")
        self.data = bytes((i * 7 % 256 for i in range(10 * 16 + 9)))
        with open(self.path, "wb") as dest, io.BytesIO(self.data) as src:
            seal_stream(dest, src, KEY, chunk_size=16)

    def tearDown(self):
        self.tmp.cleanup()

    def _read(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def _write_raw(self, raw):
        with open(self.path, "wb") as handle:
            handle.write(raw)

    def test_rotate_middle_range_only(self):
        before = self._read()
        moved = rotate_file(self.path, 2, KEYRING, start=3, end=7)
        self.assertEqual(moved, 4)
        after = self._read()
        before_frames = iter_frames(before)
        after_frames = iter_frames(after)
        self.assertEqual(len(before_frames), len(after_frames))
        for (bi, bf, bh, bc, bt), (ai, af, ah, ac, at) in zip(
            before_frames, after_frames
        ):
            self.assertEqual(bi, ai)
            self.assertEqual(bf, af)
            if 3 <= bi < 7:
                self.assertEqual(ah[9], 2)
                self.assertNotEqual(bh + bc + bt, ah + ac + at)
            else:
                # 区间外逐字节原样搬运。
                self.assertEqual(bh, ah)
                self.assertEqual(bc, ac)
                self.assertEqual(bt, at)
        with open(self.path, "rb") as handle:
            self.assertEqual(b"".join(unseal_stream(handle, KEYRING)), self.data)

    def test_unseal_mixed_versions_with_matching_keyring(self):
        rotate_file(self.path, 2, KEYRING, start=2, end=5)
        with open(self.path, "rb") as handle:
            frames = iter_frames(handle.read())
        versions = [h[9] for _i, _f, h, _c, _t in frames]
        self.assertEqual(versions.count(2), 3)
        self.assertEqual(versions.count(1), len(versions) - 3)

    def test_old_keyring_fails_on_rotated_chunk(self):
        rotate_file(self.path, 2, KEYRING, start=2, end=5)
        with open(self.path, "rb") as handle:
            with self.assertRaises(UnknownKeyError):
                b"".join(unseal_stream(handle, {1: KEY}))

    def test_rotate_default_range_covers_everything(self):
        moved = rotate_file(self.path, 3, KEYRING)
        frames = iter_frames(self._read())
        self.assertEqual(moved, len(frames))
        self.assertTrue(all(h[9] == 3 for _i, _f, h, _c, _t in frames))
        with open(self.path, "rb") as handle:
            self.assertEqual(b"".join(unseal_stream(handle, KEYRING)), self.data)

    def test_rotate_open_ended_tail(self):
        frames = iter_frames(self._read())
        total = len(frames)
        moved = rotate_file(self.path, 2, KEYRING, start=8)
        self.assertEqual(moved, total - 8)
        with open(self.path, "rb") as handle:
            self.assertEqual(b"".join(unseal_stream(handle, KEYRING)), self.data)

    def test_rotate_is_idempotent_for_content(self):
        rotate_file(self.path, 2, KEYRING, start=0, end=4)
        rotate_file(self.path, 3, KEYRING, start=2, end=6)
        with open(self.path, "rb") as handle:
            self.assertEqual(b"".join(unseal_stream(handle, KEYRING)), self.data)

    def test_rotate_empty_range_rotates_zero(self):
        self.assertEqual(rotate_file(self.path, 2, KEYRING, start=3, end=3), 0)
        before = self._read()
        rotate_file(self.path, 2, KEYRING, start=3, end=3)
        self.assertEqual(self._read(), before)

    def test_rotate_rejects_bad_range(self):
        frames = iter_frames(self._read())
        total = len(frames)
        with self.assertRaises(ValueError):
            rotate_file(self.path, 2, KEYRING, start=total)
        with self.assertRaises(ValueError):
            rotate_file(self.path, 2, KEYRING, start=-1)
        with self.assertRaises(ValueError):
            rotate_file(self.path, 2, KEYRING, start=2, end=1)
        with self.assertRaises(ValueError):
            rotate_file(self.path, 2, KEYRING, start=0, end=total + 1)

    def test_rotate_unknown_new_version_raises(self):
        with self.assertRaises(UnknownKeyError):
            rotate_file(self.path, 9, {1: KEY})

    def test_rotate_tampered_container_fails_and_keeps_original(self):
        raw = bytearray(self._read())
        raw[-5] ^= 0x01
        self._write_raw(bytes(raw))
        original = self._read()
        with self.assertRaises(VaultError):
            rotate_file(self.path, 2, KEYRING)
        self.assertEqual(self._read(), original)

    def test_rotate_rejects_v1_container(self):
        v1_path = os.path.join(self.tmp.name, "old.vlt")
        with open(v1_path, "wb") as handle:
            handle.write(seal(b"old style", KEY))
        with self.assertRaises(Exception):
            rotate_file(v1_path, 2, KEYRING)

    def test_rotate_with_relative_path(self):
        # 原子替换必须落在同一个文件上：路径解析不能受当前工作目录影响。
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            moved = rotate_file("report.vlt", 2, KEYRING, start=1, end=4)
            self.assertEqual(moved, 3)
            with open("report.vlt", "rb") as handle:
                self.assertEqual(
                    b"".join(unseal_stream(handle, KEYRING)), self.data
                )
        finally:
            os.chdir(cwd)


class TestThroughput(unittest.TestCase):
    def test_50mb_stream_not_order_of_magnitude_slower(self):
        size = 50 * 1024 * 1024
        data = os.urandom(size)
        # 整段实现基线
        t0 = time.perf_counter()
        blob = seal(data, KEY)
        t_seal = time.perf_counter() - t0
        t0 = time.perf_counter()
        self.assertEqual(unseal(blob, KEY), data)
        t_unseal = time.perf_counter() - t0

        dest = io.BytesIO()
        t0 = time.perf_counter()
        seal_stream(dest, io.BytesIO(data), KEY, chunk_size=4 * 1024 * 1024)
        t_seal_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        out = b"".join(unseal_stream(io.BytesIO(dest.getvalue()), KEY))
        t_unseal_s = time.perf_counter() - t0
        self.assertEqual(out, data)
        # 不许慢一个量级：10 倍以内。
        self.assertLess(t_seal_s, t_seal * 10 + 0.05)
        self.assertLess(t_unseal_s, t_unseal * 10 + 0.05)


if __name__ == "__main__":
    unittest.main()
