"""resumex 演示。

第一段：来源放几条记录，搬运器按批推给下游，看进度。
第二段：断点续传、重复/乱序丢弃、半截水位拒读与背压。
"""

import os
import tempfile
import time

from resumex.checkpoint import WatermarkLog
from resumex.stream import MemorySink, MemorySource, Record, StreamRunner, WatermarkSink


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

    workdir = tempfile.mkdtemp(prefix="resumex-demo-")
    log_path = os.path.join(workdir, "watermarks.log")

    print("=== 断点续传：水位落盘，重启后接着推 ===")
    source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 7)])
    sink = WatermarkSink()
    first = StreamRunner(source, sink, batch_size=3, store=WatermarkLog(log_path))
    first.run()
    print("  首次跑到水位 %d，落盘点 %s" % (sink.watermark, WatermarkLog(log_path).points()))

    source.append(7, "订单-007")
    # 同一份水位日志新建搬运器，就是一次“重启”。
    resumed_store = WatermarkLog(log_path)
    second = StreamRunner(source, WatermarkSink(), batch_size=3, store=resumed_store)
    resume_from = second.progress()["last_seq"]
    second.run()
    print("  重启先认水位 %d，只补推了 seq=7，新水位 %d" % (
        resume_from, second.progress()["last_seq"]))

    print("=== 重复与乱序：水位及以下一律丢并计数 ===")
    picky = WatermarkSink(watermark=5)
    picky.push([
        Record(4, "订单-004"),  # 乱序迟到，丢
    ])
    picky.push([Record(5, "订单-005"), Record(6, "订单-006")])  # seq=5 重复，seq=6 收
    print("  下游水位 %d，丢弃 %d 条" % (picky.watermark, picky.dropped))

    print("=== 半截水位：写崩的尾行被拒，停在上一处完好值 ===")
    before = WatermarkLog(log_path).load()
    with open(log_path, "ab") as handle:
        handle.write(b"resumex-v1\t99\t123.0\t0000-half-written-crash")
    after = WatermarkLog(log_path).load()
    print("  完好水位 %d，追加半截尾行后仍读回 %d" % (before, after))

    print("=== 背压：缓冲到上限就停取，阻塞计入进度 ===")
    back_source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 8)])

    class SlowMemorySink(MemorySink):
        """每批歇一下，模拟下游吞吐掉下来。"""

        def push(self, records):
            time.sleep(0.01)
            return super().push(records)

    back = StreamRunner(back_source, SlowMemorySink(), batch_size=2, buffer_size=2)
    back.run()
    bp = back.progress()
    print("  有限缓冲下推完 %d 条，阻塞 %d 次、累计等待 %.3fs" % (
        bp["pushed"], bp["blocked"], bp["blocked_for"],
    ))


if __name__ == "__main__":
    main()
