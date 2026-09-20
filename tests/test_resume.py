"""断点续传、去重、背压与水位一致性的测试。"""

import os
import shutil
import tempfile
import unittest

from resumex.resume import ResumableRunner, WatermarkStore
from resumex.stream import MemorySink, MemorySource, Record


class StubSource:
    """按预定批次返回记录的来源，用来模拟重复与乱序。"""

    def __init__(self, batches):
        self._batches = [list(b) for b in batches]

    def fetch(self, after_seq, limit):
        if not self._batches:
            return []
        return self._batches.pop(0)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = os.path.join(self.dir, "watermark.log")


class TestWatermarkStore(TempDirCase):
    def test_empty_store_latest_is_zero(self):
        self.assertEqual(WatermarkStore(self.path).latest(), 0)
        self.assertEqual(WatermarkStore(self.path).history(), [])

    def test_append_persists_and_keeps_multiple_points(self):
        store = WatermarkStore(self.path, keep=2)
        for seq in (3, 5, 9):
            store.append(seq)
        reloaded = WatermarkStore(self.path, keep=2)
        self.assertEqual(reloaded.latest(), 9)
        self.assertEqual(reloaded.history(), [5, 9])

    def test_watermark_never_goes_backward(self):
        store = WatermarkStore(self.path)
        store.append(5)
        with self.assertRaises(ValueError):
            store.append(4)
        self.assertEqual(WatermarkStore(self.path).latest(), 5)

    def test_rejects_negative_and_non_int(self):
        store = WatermarkStore(self.path)
        with self.assertRaises(ValueError):
            store.append(-1)
        with self.assertRaises(ValueError):
            store.append("3")

    def test_half_written_tail_record_is_rejected(self):
        store = WatermarkStore(self.path)
        store.append(3)
        store.append(5)
        with open(self.path, "ab") as fh:
            fh.write(b'{"seq": 99, "crc": 12')  # 崩在中途，没有换行
        reloaded = WatermarkStore(self.path)
        self.assertEqual(reloaded.latest(), 5)
        self.assertEqual(reloaded.history(), [3, 5])

    def test_corrupt_checksum_line_is_rejected(self):
        store = WatermarkStore(self.path)
        store.append(3)
        with open(self.path, "ab") as fh:
            fh.write(b'{"seq": 77, "crc": 1}\n')  # 校验和对不上
        reloaded = WatermarkStore(self.path)
        self.assertEqual(reloaded.latest(), 3)


class TestResumableRunner(TempDirCase):
    def test_resume_after_restart_pushes_only_new_records(self):
        source = MemorySource([(i, "k%d" % i) for i in range(1, 5)])
        sink = MemorySink()
        first = ResumableRunner(source, sink, WatermarkStore(self.path),
                                batch_size=2)
        self.assertEqual(first.run(), 4)
        self.assertEqual(first.watermark, 4)

        source.append(5, "k5")
        source.append(6, "k6")
        # 模拟重启：同一份水位文件、同一个下游，新建搬运器。
        second = ResumableRunner(source, sink, WatermarkStore(self.path),
                                 batch_size=2)
        self.assertEqual(second.watermark, 4)
        self.assertEqual(second.run(), 2)
        self.assertEqual([r.seq for r in sink.received()], [1, 2, 3, 4, 5, 6])
        self.assertEqual(second.run(), 0)

    def test_restart_with_no_new_records_pushes_nothing(self):
        source = MemorySource([(1, "a"), (2, "b")])
        sink = MemorySink()
        ResumableRunner(source, sink, WatermarkStore(self.path)).run()
        again = ResumableRunner(source, sink, WatermarkStore(self.path))
        self.assertEqual(again.run(), 0)
        self.assertEqual(len(sink.received()), 2)

    def test_duplicate_records_are_dropped_and_counted(self):
        source = StubSource([
            [Record(1, "a"), Record(2, "b")],
            [Record(2, "b"), Record(3, "c")],
            [Record(3, "c")],
        ])
        sink = MemorySink()
        runner = ResumableRunner(source, sink, WatermarkStore(self.path),
                                 batch_size=2)
        self.assertEqual(runner.run(), 3)
        self.assertEqual([r.seq for r in sink.received()], [1, 2, 3])
        stats = runner.stats()
        self.assertEqual(stats["dropped"], 2)
        self.assertEqual(stats["watermark"], 3)

    def test_out_of_order_below_watermark_is_dropped(self):
        source = StubSource([
            [Record(1, "a"), Record(2, "b"), Record(3, "c")],
            [Record(2, "b")],
            [Record(1, "a")],
        ])
        sink = MemorySink()
        runner = ResumableRunner(source, sink, WatermarkStore(self.path),
                                 batch_size=3)
        self.assertEqual(runner.run(), 3)
        self.assertEqual(runner.stats()["dropped"], 2)
        self.assertEqual(runner.watermark, 3)
        self.assertEqual(WatermarkStore(self.path).latest(), 3)

    def test_watermark_only_advances(self):
        source = StubSource([
            [Record(5, "e")],
            [Record(3, "c"), Record(4, "d")],
        ])
        runner = ResumableRunner(source, MemorySink(),
                                 WatermarkStore(self.path), batch_size=1)
        runner.run()
        self.assertEqual(runner.watermark, 5)
        self.assertEqual(runner.stats()["dropped"], 2)

    def test_backpressure_when_buffer_is_full(self):
        source = MemorySource([(i, "k%d" % i) for i in range(1, 11)])
        sink = MemorySink()
        runner = ResumableRunner(source, sink, WatermarkStore(self.path),
                                 batch_size=2, buffer_size=2)
        self.assertEqual(runner.run(), 10)
        stats = runner.stats()
        self.assertGreater(stats["blocked"], 0)
        self.assertEqual(stats["pushed"], 10)
        self.assertEqual([r.seq for r in sink.received()],
                         list(range(1, 11)))
        self.assertEqual(WatermarkStore(self.path).latest(), 10)

    def test_partial_watermark_tail_does_not_skip_records(self):
        source = MemorySource([(i, "k%d" % i) for i in range(1, 7)])
        sink = MemorySink()
        ResumableRunner(source, sink, WatermarkStore(self.path),
                        batch_size=2).run()
        self.assertEqual(WatermarkStore(self.path).latest(), 6)
        # 伪造一次落盘崩在中途：尾部半截写着更大的水位，绝不能当真。
        with open(self.path, "ab") as fh:
            fh.write(b'{"seq": 100, "cr')
        source.append(7, "k7")
        runner = ResumableRunner(source, sink, WatermarkStore(self.path),
                                 batch_size=2)
        self.assertEqual(runner.watermark, 6)
        self.assertEqual(runner.run(), 1)
        self.assertEqual([r.seq for r in sink.received()],
                         [1, 2, 3, 4, 5, 6, 7])

    def test_invalid_buffer_size_raises(self):
        with self.assertRaises(ValueError):
            ResumableRunner(MemorySource(), MemorySink(),
                            WatermarkStore(self.path), buffer_size=0)


if __name__ == "__main__":
    unittest.main()
