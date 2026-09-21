"""断点续传、水位一致性、重复乱序丢弃与背压的新行为测试。"""

import os
import tempfile
import threading
import time
import unittest

from resumex.stream import (
    MemorySink,
    MemorySource,
    Record,
    StreamRunner,
    WatermarkStore,
)


class TestWatermarkStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "watermarks.rx")

    def tearDown(self):
        self.tmp.cleanup()

    def test_keeps_multiple_increasing_points(self):
        store = WatermarkStore(self.path)
        store.save(3, 10.0, b"batch-1")
        store.save(6, 11.0, b"batch-2")
        store.save(9, 12.0, b"batch-3")
        reloaded = WatermarkStore(self.path)
        self.assertEqual(reloaded.latest_seq, 9)
        seqs = [point[0] for point in reloaded.history()]
        self.assertEqual(seqs, [3, 6, 9])
        self.assertEqual(reloaded.history()[-1][2], b"batch-3")

    def test_save_rejects_non_increasing_seq(self):
        store = WatermarkStore(self.path)
        store.save(5, 10.0)
        with self.assertRaises(ValueError):
            store.save(5, 11.0)
        with self.assertRaises(ValueError):
            store.save(4, 12.0)
        self.assertEqual(WatermarkStore(self.path).latest_seq, 5)

    def test_missing_file_starts_at_zero(self):
        missing = os.path.join(self.tmp.name, "nope.rx")
        self.assertEqual(WatermarkStore(missing).latest_seq, 0)

    def test_torn_half_line_is_rejected(self):
        store = WatermarkStore(self.path)
        store.save(4, 10.0, b"ok-1")
        with open(self.path, "rb") as good_fh:
            good_lines = good_fh.read()
        # 模拟崩在写入中途：末尾只留下半条记录。
        with open(self.path, "ab") as fh:
            fh.write(b"RX1\t9\t12.0\t7\tab12cd")
        reloaded = WatermarkStore(self.path)
        self.assertEqual(reloaded.latest_seq, 4)
        self.assertEqual([p[0] for p in reloaded.history()], [4])
        # 重启时按最后一个完好点定位，截掉末尾半截尾巴后再继续落盘。
        with open(self.path, "r+b") as trim_fh:
            trim_fh.truncate(len(good_lines))
        store2 = WatermarkStore(self.path)
        store2.save(7, 13.0, b"ok-2")
        self.assertEqual(WatermarkStore(self.path).latest_seq, 7)
        with open(self.path, "rb") as tail_fh:
            self.assertTrue(tail_fh.read().startswith(good_lines))

    def test_corrupted_checksum_line_is_rejected(self):
        store = WatermarkStore(self.path)
        store.save(4, 10.0)
        with open(self.path, "ab") as fh:
            fh.write(b"RX1\t8\t12.0\t0\t\tdeadbeef\n")
        reloaded = WatermarkStore(self.path)
        self.assertEqual(reloaded.latest_seq, 4)

    def test_regressing_line_is_rejected_on_reload(self):
        store = WatermarkStore(self.path)
        store.save(6, 10.0)
        line = WatermarkStore._encode_line(3, 11.0, b"")  # 完好但回退
        with open(self.path, "ab") as fh:
            fh.write(line)
        reloaded = WatermarkStore(self.path)
        self.assertEqual(reloaded.latest_seq, 6)


class TestDuplicateAndOutOfOrder(unittest.TestCase):
    def test_duplicate_seq_at_or_below_watermark_dropped(self):
        sink = MemorySink()
        sink.push([Record(1, "a"), Record(2, "b")])
        sink.push([Record(2, "b-again"), Record(1, "a-again")])
        self.assertEqual(sink.watermark, 2)
        self.assertEqual(sink.discarded, 2)
        self.assertEqual(sink.stats()["discarded"], 2)
        self.assertEqual(sink.received(), [Record(1, "a"), Record(2, "b")])

    def test_late_out_of_order_seq_dropped_but_higher_advances(self):
        sink = MemorySink()
        sink.push([Record(5, "e")])
        sink.push([Record(3, "c-late"), Record(6, "f"), Record(5, "e-again")])
        self.assertEqual(sink.watermark, 6)
        self.assertEqual(sink.discarded, 2)  # seq 3 乱序迟到、seq 5 重复
        self.assertEqual(
            sink.received(), [Record(5, "e"), Record(6, "f")]
        )

    def test_runner_redelivers_after_restart_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wm.rx")
            source = MemorySource([(i, "v%d" % i) for i in range(1, 7)])
            sink = MemorySink()
            runner = StreamRunner(source, sink, batch_size=2, store=WatermarkStore(path))
            self.assertEqual(runner.run(), 6)
            self.assertEqual(WatermarkStore(path).latest_seq, 6)

            # 进程重启：同一份水位、同一来源、一个干净的下游。
            sink2 = MemorySink()
            runner2 = StreamRunner(
                source, sink2, batch_size=2, store=WatermarkStore(path)
            )
            self.assertEqual(runner2.progress()["last_seq"], 6)
            self.assertEqual(runner2.run(), 0)
            self.assertEqual(sink2.received(), [])

            # 新记录到达后从水位之后接着推。
            source.append(7, "v7")
            source.append(8, "v8")
            self.assertEqual(runner2.run(), 2)
            self.assertEqual(
                sink2.received(), [Record(7, "v7"), Record(8, "v8")]
            )
            self.assertEqual(WatermarkStore(path).latest_seq, 8)

    def test_runner_restart_mid_batch_resumes_after_last_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wm.rx")
            source = MemorySource([(i, "v%d" % i) for i in range(1, 6)])
            sink = MemorySink()
            StreamRunner(
                source, sink, batch_size=3, store=WatermarkStore(path)
            ).run()
            self.assertEqual([p[0] for p in WatermarkStore(path).history()], [3, 5])

            # 水位已认到 6，重跑从水位之后取，没有任何重发。
            runner2 = StreamRunner(
                source, sink, batch_size=3, store=WatermarkStore(path)
            )
            self.assertEqual(runner2.run(), 0)
            self.assertEqual(sink.discarded, 0)  # 从水位 6 之后取，无重发


class TestBackpressure(unittest.TestCase):
    def test_buffer_cap_blocks_source_fetch_and_counts(self):
        gate = threading.Event()

        class SlowSink:
            def __init__(self):
                self.watermark = 0
                self._count = 0
                self._lock = threading.Lock()
                self.batches_in_flight = 0

            def push(self, records):
                gate.wait(timeout=5.0)
                with self._lock:
                    for record in records:
                        if record.seq > self.watermark:
                            self.watermark = record.seq
                            self._count += 1
                return self.watermark

            def received_count(self):
                with self._lock:
                    return self._count

            def stats(self):
                return {"discarded": 0}

        fetches = []

        class CountingSource(MemorySource):
            def fetch(self, after_seq, limit):
                fetches.append(after_seq)
                return super().fetch(after_seq, limit)

        source = CountingSource([(i, "v%d" % i) for i in range(1, 9)])
        sink = SlowSink()
        runner = StreamRunner(
            source, sink, batch_size=2, max_buffered=4, store=None
        )
        done = threading.Event()
        result = []

        def drive():
            result.append(runner.run())
            done.set()

        thread = threading.Thread(target=drive)
        thread.start()

        # 缓冲只能放 2 批（4 条）：worker 卡在第 1 批，队列塞满后，
        # 生产者必须停在来源取数上，不能把 8 条全捞进内存。
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if runner.progress()["blocked"] >= 1:
                break
            time.sleep(0.01)
        self.assertGreaterEqual(runner.progress()["blocked"], 1)
        self.assertLessEqual(len(source), 8)
        self.assertLessEqual(len(fetches), 4)

        gate.set()
        self.assertTrue(done.wait(timeout=5.0))
        thread.join(timeout=5.0)
        self.assertEqual(result[0], 8)
        self.assertEqual(sink.watermark, 8)

    def test_invalid_max_buffered_raises(self):
        with self.assertRaises(ValueError):
            StreamRunner(MemorySource(), MemorySink(), max_buffered=0)

    def test_buffered_run_delivers_every_record_and_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "wm.rx")
            source = MemorySource([(i, "v%d" % i) for i in range(1, 7)])
            sink = MemorySink()
            runner = StreamRunner(
                source,
                sink,
                batch_size=2,
                max_buffered=2,
                store=WatermarkStore(path),
            )
            self.assertEqual(runner.run(), 6)
            self.assertEqual(sink.watermark, 6)
            self.assertEqual(WatermarkStore(path).latest_seq, 6)


if __name__ == "__main__":
    unittest.main()
