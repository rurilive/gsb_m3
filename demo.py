"""预写日志演示。"""
import os
import tempfile
import threading

from walg import WriteAheadLog

wal_path = os.path.join(tempfile.mkdtemp(), "wal.log")

with WriteAheadLog(wal_path) as wal:
    for i in range(5):
        lsn = wal.append(b"set balance=%d" % (i * 100))
        print("append lsn=%d -> %r" % (lsn, wal.read_from(lsn)[-1]))

    # 第二段：并发写入演示。多线程同时 append，写线程凑一批只 fsync 一次，
    # 每个调用方在自己那条刷盘完成后才拿到 LSN。
    threads, per_thread = 8, 20
    barrier = threading.Barrier(threads)
    assigned = []
    assigned_lock = threading.Lock()

    def worker(tag):
        barrier.wait()
        for i in range(per_thread):
            lsn = wal.append(b"thread %d set x=%d" % (tag, i))
            with assigned_lock:
                assigned.append((tag, i, lsn))

    pool = [threading.Thread(target=worker, args=(t,)) for t in range(threads)]
    for t in pool:
        t.start()
    for t in pool:
        t.join()

    print("concurrent: %d 条记录，LSN 1..%d，%d 个线程共享组提交刷盘"
          % (len(assigned), wal.last_lsn, threads))

print("wal file:", wal_path, os.path.getsize(wal_path), "bytes")
