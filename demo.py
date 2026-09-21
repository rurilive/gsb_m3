"""resumex 现状演示。

第一段：来源放几条记录，搬运器按批推给下游，看进度。
第二段：水位落盘后“重启”，从水位接着推；重复乱序被丢、
半截水位被拒、下游变慢时缓冲打满触发背压。
"""

import os
import tempfile
import threading
import time

from resumex.stream import (
    DedupSink,
    MemorySink,
    MemorySource,
    Record,
    StreamRunner,
    WatermarkStore,
)


ticks = iter(float(n) for n in range(10000))


def clock():
    return next(ticks)


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

    print()
    print("=== 断点续传：水位落盘，重启后从水位接着推 ===")
    tmp = tempfile.mkdtemp(prefix="resumex-")
    path = os.path.join(tmp, "watermark.log")
    source = MemorySource([(seq, "订单-%03d" % seq) for seq in range(1, 6)])
    sink = DedupSink()
    runner = StreamRunner(
        source, sink, batch_size=2, clock=clock, store=WatermarkStore(path, fsync=False)
    )
    runner.run()
    store = WatermarkStore(path, fsync=False)
    store.load()
    print(
        "  首次推完，下游水位 %d，落盘水位点 %s"
        % (sink.watermark, ",".join(str(point[0]) for point in store.points()))
    )

    # 模拟重启：新进程、新来源（重放旧记录并追加新记录），同一份水位文件
    source2 = MemorySource(
        [(seq, "订单-%03d" % seq) for seq in range(1, 9)]
    )
    sink2 = DedupSink()
    runner2 = StreamRunner(
        source2,
        sink2,
        batch_size=2,
        clock=clock,
        store=WatermarkStore(path, fsync=False),
    )
    print("  重启先认水位：起点 last_seq=%d" % runner2.progress()["last_seq"])
    # 上游不可靠地重放/乱序：手动塞一条水位以下的记录给下游
    sink2.push([Record(2, "迟到的重复单")])
    runner2.run()
    print(
        "  续推后下游水位 %d，丢弃 %d 条，真正新收 seq=%s"
        % (
            sink2.watermark,
            sink2.stats()["dropped"],
            [record.seq for record in sink2.received()],
        )
    )

    print()
    print("=== 半截水位判废 ===")
    with open(path, "ab") as fh:
        fh.write(b"RXC1\t99\t99\t0.0\tdead")  # 崩在半道：无校验和无换行
    store = WatermarkStore(path, fsync=False)
    print("  半截尾行被拒，恢复水位停在 %d（不是 99）" % store.load())

    print()
    print("=== 背压：下游变慢，缓冲打满即停取 ===")
    release = threading.Event()
    blocked = threading.Event()
    source3 = MemorySource([(seq, "慢单-%02d" % seq) for seq in range(1, 11)])
    sink3 = DedupSink()

    def pre_push(batch):
        if batch[0].seq == 1:
            release.wait(2)  # 下游第一批就卡住

    runner3 = StreamRunner(
        source3,
        sink3,
        batch_size=2,
        clock=clock,
        buffer_size=2,
        on_block=blocked.set,
        pre_push=pre_push,
    )
    done = threading.Event()
    threading.Thread(
        target=lambda: (runner3.run(), done.set()), daemon=True
    ).start()
    blocked.wait(2)
    print("  缓冲打满，来源侧已阻塞：blocked=%d" % runner3.progress()["blocked"])
    release.set()
    done.wait(2)
    print("  下游恢复后全部推完：last_seq=%d" % runner3.progress()["last_seq"])


if __name__ == "__main__":
    main()
