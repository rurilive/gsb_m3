"""预写日志演示。"""
import os
import tempfile
import threading
import time

from walg import WriteAheadLog

wal_path = os.path.join(tempfile.mkdtemp(), "wal.log")

with WriteAheadLog(wal_path) as wal:
    for i in range(5):
        lsn = wal.append(b"set balance=%d" % (i * 100))
        print("append lsn=%d -> %r" % (lsn, wal.read_from(lsn)[-1]))

    # 第二段：并发写入演示（组提交把一批 append 合并成一次刷盘）
    threads, per_thread = 8, 200
    barrier = threading.Barrier(threads)

    def worker(tag):
        barrier.wait()
        for i in range(per_thread):
            wal.append(b"transfer t%d-%d" % (tag, i))

    pool = [threading.Thread(target=worker, args=(t,)) for t in range(threads)]
    start = time.monotonic()
    for t in pool:
        t.start()
    for t in pool:
        t.join()
    cost = time.monotonic() - start
    total = threads * per_thread
    print("concurrent: %d appends in %.3fs (%.0f/s), last_lsn=%d"
          % (total, cost, total / cost, wal.last_lsn))

print("wal file:", wal_path, os.path.getsize(wal_path), "bytes")
