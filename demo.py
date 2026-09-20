"""resumex 现状演示。

第一段：来源放几条记录，搬运器按批推给下游，看进度。
第二段：断点续传与水位演示（落盘、重启续推、去重、背压）。
"""

import os
import tempfile

from resumex.resume import ResumableRunner, WatermarkStore
from resumex.stream import MemorySink, MemorySource, Record, StreamRunner


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

    print("=== 断点续传：水位落盘，重启接着推 ===")
    tmpdir = tempfile.mkdtemp(prefix="resumex-demo-")
    path = os.path.join(tmpdir, "watermark.log")
    source2 = MemorySource([(seq, "运单-%03d" % seq) for seq in range(1, 5)])
    sink2 = MemorySink()
    runner_a = ResumableRunner(source2, sink2, WatermarkStore(path),
                               batch_size=2)
    runner_a.run()
    print("  首次推送 %d 条，水位落盘到 %d，历史点 %s"
          % (runner_a.stats()["pushed"], runner_a.watermark,
             WatermarkStore(path).history()))

    source2.append(5, "运单-005")
    source2.append(6, "运单-006")
    # 模拟重启：同一份水位文件、同一个下游，新建搬运器。
    runner_b = ResumableRunner(source2, sink2, WatermarkStore(path),
                               batch_size=2)
    print("  重启后认出水位 %d，只补推 %d 条，下游共 %d 条无重复"
          % (runner_b.watermark, runner_b.run(), len(sink2.received())))

    print("=== 重复与乱序：水位及以下一律丢弃 ===")

    class ReplaySource:
        def __init__(self, batches):
            self._batches = [list(b) for b in batches]

        def fetch(self, after_seq, limit):
            return self._batches.pop(0) if self._batches else []

    replay = ReplaySource([
        [Record(1, "a"), Record(2, "b")],
        [Record(2, "b"), Record(3, "c")],  # 2 重复
        [Record(1, "a")],                  # 1 乱序迟到
    ])
    runner_c = ResumableRunner(replay, MemorySink(), WatermarkStore(
        os.path.join(tmpdir, "dedup.log")), batch_size=2)
    runner_c.run()
    stats = runner_c.stats()
    print("  推了 %d 条，丢掉重复/乱序 %d 条，水位只增到 %d"
          % (stats["pushed"], stats["dropped"], stats["watermark"]))

    print("=== 半截水位：写一半的记录不算数 ===")
    with open(path, "ab") as fh:
        fh.write(b'{"seq": 100, "cr')  # 模拟落盘崩在中途
    reloaded = WatermarkStore(path)
    print("  半截记录被拒，水位停在上一处完好值 %d，历史点 %s"
          % (reloaded.latest(), reloaded.history()))

    print("=== 背压：缓冲到上限就暂停取数 ===")
    runner_d = ResumableRunner(
        MemorySource([(seq, "批-%d" % seq) for seq in range(1, 9)]),
        MemorySink(), WatermarkStore(os.path.join(tmpdir, "bp.log")),
        batch_size=2, buffer_size=2)
    runner_d.run()
    stats = runner_d.stats()
    print("  缓冲上限 2，推完 %d 条，因缓冲满暂停取数 %d 次"
          % (stats["pushed"], stats["blocked"]))


if __name__ == "__main__":
    main()
