"""resumex 演示：按批推送、断点续传、丢弃计数、半截水位判废与背压。"""

import os
import tempfile
import threading
import time

from resumex.stream import (
    MemorySink,
    MemorySource,
    Record,
    StreamRunner,
    WatermarkStore,
)


def main():
    print("=== 按批推送（每批 3 条） ===")
    source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 8)])
    sink = MemorySink()
    runner = StreamRunner(source, sink, batch_size=3)
    moved = runner.run()
    for record in sink.received():
        print("  seq=%d payload=%r" % (record.seq, record.payload))
    progress = runner.progress()
    print("  本次推送 %d 条，下游水位 %d" % (moved, sink.watermark))
    print(
        "  进度: last_seq=%d pushed=%d batches=%d"
        % (progress["last_seq"], progress["pushed"], progress["batches"])
    )

    tmp = tempfile.mkdtemp(prefix="resumex-demo-")
    path = os.path.join(tmp, "watermarks.rx")

    print("\n=== 断点续传：水位落盘后重启，接着水位推 ===")
    source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 11)])
    sink = MemorySink()
    runner = StreamRunner(source, sink, batch_size=4, store=WatermarkStore(path))
    first = runner.run()
    print("  首次搬运 %d 条，落盘水位点 %s" % (first, [p[0] for p in WatermarkStore(path).history()]))

    # 进程重启：用同一份水位文件新建搬运器，来源此时追加了新记录。
    source.append(11, "订单-011")
    source.append(12, "订单-012")
    sink2 = MemorySink()
    runner2 = StreamRunner(source, sink2, batch_size=4, store=WatermarkStore(path))
    second = runner2.run()
    print("  重启后只推水位之后的 %d 条：%s" % (second, [r.seq for r in sink2.received()]))

    print("\n=== 重复与乱序：序号 <= 水位的一律丢弃 ===")
    sink = MemorySink()
    sink.push([Record(4, "订单-004")])
    sink.push(
        [
            Record(2, "订单-002-迟到"),
            Record(4, "订单-004-重复"),
            Record(5, "订单-005"),
        ]
    )
    print("  水位 %d，丢弃 %d 条，收下 %s" % (sink.watermark, sink.discarded, [r.seq for r in sink.received()]))

    print("\n=== 半截水位记录判废：水位停在上一处完好值 ===")
    crash_path = os.path.join(tmp, "crash.rx")
    crashed = WatermarkStore(crash_path)
    crashed.save(8, time.monotonic(), b"batch-to-8")
    with open(crash_path, "ab") as fh:  # 模拟崩在写入中途
        torn = b"RX1\t99\t1.0\t9\tdeadbeef"
        fh.write(torn)
    recovered = WatermarkStore(crash_path)
    print("  读到半截尾巴，最新水位仍为 %d（不是 99）" % recovered.latest_seq)
    with open(crash_path, "r+b") as fh:  # 恢复时截掉废行再继续
        fh.seek(0, os.SEEK_END)
        fh.truncate(fh.tell() - len(torn))
    WatermarkStore(crash_path).save(12, time.monotonic(), b"batch-to-12")
    print("  截掉废行续传后，最新水位推进到 %d" % WatermarkStore(crash_path).latest_seq)

    print("\n=== 下游变慢：有界缓冲满了就背压，阻塞也计数 ===")

    class SlowSink:
        def __init__(self):
            self.watermark = 0
            self._lock = threading.Lock()
            self._n = 0

        def push(self, records):
            time.sleep(0.02)  # 下游吞吐掉下来
            with self._lock:
                for record in records:
                    if record.seq > self.watermark:
                        self.watermark = record.seq
                        self._n += 1
            return self.watermark

        def received_count(self):
            with self._lock:
                return self._n

        def stats(self):
            return {"discarded": 0}

    source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 13)])
    slow = SlowSink()
    runner = StreamRunner(source, slow, batch_size=2, max_buffered=4)
    total = runner.run()
    p = runner.progress()
    print(
        "  缓冲上限 4 条，共推 %d 条，最终水位 %d，取数被背压阻塞 %d 次"
        % (total, slow.watermark, p["blocked"])
    )


if __name__ == "__main__":
    main()
