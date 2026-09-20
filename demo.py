"""预写日志演示。"""
import os
import tempfile

from walg import WriteAheadLog

wal_path = os.path.join(tempfile.mkdtemp(), "wal.log")

with WriteAheadLog(wal_path) as wal:
    for i in range(5):
        lsn = wal.append(b"set balance=%d" % (i * 100))
        print("append lsn=%d -> %r" % (lsn, wal.read_from(lsn)[-1]))

    # 第二段：并发写入演示（留给实现者补）

print("wal file:", wal_path, os.path.getsize(wal_path), "bytes")
