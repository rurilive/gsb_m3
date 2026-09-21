"""seal_stream / unseal_stream / rotate_file 的锁定测试。"""

import io
import os
import random
import tempfile
import tracemalloc
import unittest

from vaultfile import (
    AuthError,
    UnknownKeyError,
    rotate_file,
    seal,
    seal_stream,
    unseal_stream,
)
from vaultfile.chunked import (
    CHUNK_HEADER_LEN,
    DEFAULT_CHUNK_SIZE,
    FILE_HEADER_LEN,
    MAGIC_V2,
)
from vaultfile.format import TAG_LEN

KEY1 = b"vault-unit-test-key-01"
KEY2 = b"vault-unit-test-key-02"
PAYLOAD = bytes((i * 37 + 11) % 256 for i in range(10000))


class GreedySource:
    """不听话的源：允许 read 被奇怪使用，但不会吐出多于请求的数据。"""

    def __init__(self, data):
        self.data = data

    def read(self, count):
        if not self.data:
            return b""
        take = min(count, len(self.data))
        piece, self.data = self.data[:take], self.data[take:]
        return piece


class NullSink:
    def write(self, data):
        return len(data)


def chunk_layout(blob):
    """返回 [(chunk 字节, length)]，顺序与文件一致。"""
    assert blob[:4] == MAGIC_V2
    pieces = []
    pos = FILE_HEADER_LEN
    while pos < len(blob):
        length = int.from_bytes(blob[pos + 10 : pos + 14], "big")
        size = CHUNK_HEADER_LEN + length + TAG_LEN
        pieces.append((blob[pos : pos + size], length))
        pos += size
    return pieces


def stream_round_trip(payload, chunk_size, key=KEY1, key_version=None):
    sealed = io.BytesIO()
    seal_stream(
        io.BytesIO(payload),
        sealed,
        key,
        key_version=key_version,
        chunk_size=chunk_size,
    )
    opened = io.BytesIO()
    count = unseal_stream(io.BytesIO(sealed.getvalue()), opened, key)
    return sealed.getvalue(), opened.getvalue(), count


class TestSealUnsealStream(unittest.TestCase):
    def test_round_trip_sizes_and_chunk_sizes(self):
        for payload in (b"", b"a", b"ab", PAYLOAD):
            for chunk_size in (1, 2, 7, 1024):
                blob, plain, count = stream_round_trip(payload, chunk_size)
                self.assertEqual(plain, payload)
                self.assertEqual(count, len(payload))
                self.assertEqual(blob[:4], MAGIC_V2)

    def test_chunk_layout_lengths(self):
        blob, _, _ = stream_round_trip(PAYLOAD, 1000)
        self.assertEqual(
            [length for _, length in chunk_layout(blob)], [1000] * 10
        )
        blob, _, _ = stream_round_trip(PAYLOAD[:5500], 1000)
        self.assertEqual(
            [length for _, length in chunk_layout(blob)],
            [1000] * 5 + [500],
        )

    def test_empty_file_is_one_final_empty_block(self):
        blob, plain, count = stream_round_trip(b"", 128)
        self.assertEqual(
            len(blob), FILE_HEADER_LEN + CHUNK_HEADER_LEN + TAG_LEN
        )
        self.assertEqual(plain, b"")
        self.assertEqual(count, 0)

    def test_greedy_source_round_trips(self):
        sealed = io.BytesIO()
        seal_stream(GreedySource(PAYLOAD), sealed, KEY1, chunk_size=123)
        opened = io.BytesIO()
        unseal_stream(io.BytesIO(sealed.getvalue()), opened, KEY1)
        self.assertEqual(opened.getvalue(), PAYLOAD)

    def test_salt_is_fresh_per_file(self):
        first = io.BytesIO()
        second = io.BytesIO()
        seal_stream(io.BytesIO(PAYLOAD), first, KEY1, chunk_size=64)
        seal_stream(io.BytesIO(PAYLOAD), second, KEY1, chunk_size=64)
        self.assertNotEqual(first.getvalue(), second.getvalue())

    def test_disk_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            plain_path = os.path.join(tmp, "report.bin")
            sealed_path = os.path.join(tmp, "report.vlt")
            opened_path = os.path.join(tmp, "out.bin")
            with open(plain_path, "wb") as handle:
                handle.write(PAYLOAD)
            written = seal_stream(plain_path, sealed_path, KEY1, chunk_size=4096)
            self.assertEqual(written, os.path.getsize(sealed_path))
            unseal_stream(sealed_path, opened_path, KEY1)
            with open(opened_path, "rb") as handle:
                self.assertEqual(handle.read(), PAYLOAD)

    def test_wrong_key_fails(self):
        blob, _, _ = stream_round_trip(PAYLOAD, 500)
        with self.assertRaises(AuthError):
            unseal_stream(io.BytesIO(blob), io.BytesIO(), KEY2)

    def test_legacy_v1_container_unseals(self):
        v1 = seal(PAYLOAD, KEY1)
        opened = io.BytesIO()
        count = unseal_stream(io.BytesIO(v1), opened, KEY1)
        self.assertEqual(opened.getvalue(), PAYLOAD)
        self.assertEqual(count, len(PAYLOAD))

    def test_garbage_and_empty_fail(self):
        for bad in (b"", b"not a container", b"XXXX" + os.urandom(100)):
            with self.assertRaises(AuthError):
                unseal_stream(io.BytesIO(bad), io.BytesIO(), KEY1)

    def test_invalid_chunk_size(self):
        for bad in (0, -1, 2 ** 32):
            with self.assertRaises(ValueError):
                seal_stream(io.BytesIO(b"x"), io.BytesIO(), KEY1, chunk_size=bad)
        with self.assertRaises(TypeError):
            seal_stream(io.BytesIO(b"x"), io.BytesIO(), KEY1, chunk_size=True)


class TestTamperReportsBlock(unittest.TestCase):
    def _blob(self, chunk_size=37):
        sealed = io.BytesIO()
        seal_stream(io.BytesIO(PAYLOAD), sealed, KEY1, chunk_size=chunk_size)
        return sealed.getvalue()

    def test_random_flipped_bytes_all_fail_with_block_number(self):
        blob = self._blob()
        rng = random.Random(20260921)
        for pos in sorted(rng.sample(range(len(blob)), 60)):
            bad = bytearray(blob)
            bad[pos] ^= rng.randrange(1, 256)
            with self.assertRaises(AuthError) as ctx:
                unseal_stream(io.BytesIO(bytes(bad)), io.BytesIO(), KEY1)
            self.assertIn("block", str(ctx.exception))

    def test_every_block_can_be_individually_broken(self):
        blob = self._blob()
        pieces = chunk_layout(blob)
        self.assertGreater(len(pieces), 5)
        offset = FILE_HEADER_LEN
        for i, (chunk, length) in enumerate(pieces):
            bad = bytearray(blob)
            flip_at = offset + CHUNK_HEADER_LEN + (i % max(length, 1))
            bad[flip_at] ^= 0x5A
            with self.assertRaises(AuthError) as ctx:
                unseal_stream(io.BytesIO(bytes(bad)), io.BytesIO(), KEY1)
            self.assertIn("block %d" % i, str(ctx.exception))
            offset += len(chunk)

    def test_swapped_blocks_reported_out_of_place(self):
        blob = self._blob()
        pieces = [piece for piece, _ in chunk_layout(blob)]
        self.assertGreater(len(pieces), 3)
        reordered = pieces[:]
        reordered[1], reordered[3] = reordered[3], reordered[1]
        bad = blob[:FILE_HEADER_LEN] + b"".join(reordered)
        with self.assertRaises(AuthError) as ctx:
            unseal_stream(io.BytesIO(bad), io.BytesIO(), KEY1)
        message = str(ctx.exception)
        self.assertIn("out of place", message)
        self.assertIn("block 3", message)

    def test_truncation_caught(self):
        blob = self._blob()
        for cut in (
            1,
            FILE_HEADER_LEN,
            len(blob) - 1,
            len(blob) - TAG_LEN,
            len(blob) - CHUNK_HEADER_LEN,
        ):
            with self.assertRaises(AuthError):
                unseal_stream(io.BytesIO(blob[:cut]), io.BytesIO(), KEY1)

    def test_tampered_block_does_not_leak_plaintext(self):
        blob = bytearray(self._blob())
        blob[FILE_HEADER_LEN + CHUNK_HEADER_LEN + 1] ^= 0x01
        sink = io.BytesIO()
        with self.assertRaises(AuthError):
            unseal_stream(io.BytesIO(bytes(blob)), sink, KEY1)
        self.assertEqual(sink.getvalue(), b"")


class TestRotateFile(unittest.TestCase):
    def _sealed_file(self, tmp, chunk_size=37, version=1, key=KEY1):
        plain_path = os.path.join(tmp, "plain.bin")
        path = os.path.join(tmp, "mixed.vlt")
        with open(plain_path, "wb") as handle:
            handle.write(PAYLOAD)
        seal_stream(
            plain_path,
            path,
            {version: key},
            key_version=version,
            chunk_size=chunk_size,
        )
        return path

    def _read(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def test_rotate_middle_range_mixed_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._sealed_file(tmp)
            nblocks = len(chunk_layout(self._read(path)))
            rotated = rotate_file(
                path,
                new_key={1: KEY1, 2: KEY2},
                start=10,
                end=50,
                new_key_version=2,
            )
            self.assertEqual(rotated, 40)
            raw = self._read(path)
            pieces = chunk_layout(raw)
            self.assertEqual(len(pieces), nblocks)
            versions = [chunk[0] for chunk, _ in pieces]
            self.assertEqual(versions[:10], [1] * 10)
            self.assertEqual(versions[10:50], [2] * 40)
            self.assertEqual(versions[50:], [1] * (nblocks - 50))
            opened = os.path.join(tmp, "out.bin")
            unseal_stream(path, opened, {1: KEY1, 2: KEY2})
            self.assertEqual(self._read(opened), PAYLOAD)

    def test_blocks_outside_range_are_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._sealed_file(tmp)
            before = self._read(path)
            rotate_file(
                path,
                new_key={1: KEY1, 2: KEY2},
                start=10,
                end=50,
                new_key_version=2,
            )
            after = self._read(path)
            self.assertEqual(before[:FILE_HEADER_LEN], after[:FILE_HEADER_LEN])
            before_pieces = chunk_layout(before)
            after_pieces = chunk_layout(after)
            for i, ((before_chunk, _), (after_chunk, _)) in enumerate(
                zip(before_pieces, after_pieces)
            ):
                if not (10 <= i < 50):
                    self.assertEqual(before_chunk, after_chunk)

    def test_rotate_to_separate_dest_leaves_source_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = self._sealed_file(tmp)
            dst = os.path.join(tmp, "rotated.vlt")
            with open(src, "rb") as handle:
                before = handle.read()
            rotate_file(
                src,
                dst,
                new_key={1: KEY1, 2: KEY2},
                start=0,
                end=5,
                new_key_version=2,
            )
            with open(src, "rb") as handle:
                self.assertEqual(handle.read(), before)
            out_path = os.path.join(tmp, "o.bin")
            unseal_stream(dst, out_path, {1: KEY1, 2: KEY2})
            with open(out_path, "rb") as handle:
                self.assertEqual(handle.read(), PAYLOAD)

    def test_open_ended_end_rotates_through_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._sealed_file(tmp)
            nblocks = len(chunk_layout(self._read(path)))
            rotated = rotate_file(
                path,
                new_key={1: KEY1, 2: KEY2},
                start=nblocks - 3,
                new_key_version=2,
            )
            self.assertEqual(rotated, 3)
            out_path = os.path.join(tmp, "o.bin")
            unseal_stream(path, out_path, {1: KEY1, 2: KEY2})
            self.assertEqual(self._read(out_path), PAYLOAD)

    def test_old_keyring_cannot_unseal_rotated_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._sealed_file(tmp)
            rotate_file(
                path,
                new_key={1: KEY1, 2: KEY2},
                start=0,
                end=5,
                new_key_version=2,
            )
            with self.assertRaises(UnknownKeyError):
                unseal_stream(path, os.path.join(tmp, "o.bin"), {1: KEY1})

    def test_rotate_rejects_bad_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._sealed_file(tmp)
            ring = {1: KEY1, 2: KEY2}
            for kwargs in (
                {"start": -1},
                {"end": -1},
                {"start": 10, "end": 3},
            ):
                with self.assertRaises(ValueError):
                    rotate_file(
                        path,
                        os.path.join(tmp, "r%r.vlt" % kwargs),
                        new_key=ring,
                        new_key_version=2,
                        **kwargs
                    )
            self.assertTrue(os.path.exists(path))


class TestPeakMemory(unittest.TestCase):
    def test_peak_grows_with_chunk_size_not_file_size(self):
        # 走真实文件源（内存源自己持有整份明文，那不算处理侧占用）。
        with tempfile.TemporaryDirectory() as tmp:
            small_path = os.path.join(tmp, "small.bin")
            big_path = os.path.join(tmp, "big.bin")
            with open(small_path, "wb") as handle:
                handle.write(b"x" * 2_000_000)
            with open(big_path, "wb") as handle:
                handle.write(b"x" * 8_000_000)
            peaks = []
            tracemalloc.start()
            try:
                for path in (small_path, big_path):
                    tracemalloc.reset_peak()
                    seal_stream(path, NullSink(), KEY1, chunk_size=65536)
                    _, peak = tracemalloc.get_traced_memory()
                    peaks.append(peak)
            finally:
                tracemalloc.stop()
        self.assertLess(peaks[0], 1_000_000)
        self.assertLess(peaks[1], 1_000_000)
        self.assertLess(abs(peaks[1] - peaks[0]), 500_000)

    def test_default_chunk_size_is_sane(self):
        self.assertIsInstance(DEFAULT_CHUNK_SIZE, int)
        self.assertGreaterEqual(DEFAULT_CHUNK_SIZE, 1)
