"""多路归并：把若干有序 run 文件合成一个有序 run 文件。

每个 run 文件内部按 (key(record), seq) 有序，seq 是记录进入排序器时的
全局序号。归并输出同样按 (key, seq) 有序；同一个 key 分散在不同 run
里时，只保留 seq 最小（最早进入排序器）的那一条。

一次归并最多同时打开 len(paths) 个输入读者加一个输出写者，因此调用方
必须保证 len(paths) + 1 <= guard.fd_limit；run 太多时由上层分趟级联。
"""

import heapq

from spillkit.runfile import RunReader, write_run

_MISSING = object()


def merge_runs(paths, key, out_path, guard):
    """归并 paths 里的全部 run 文件，写入 out_path，返回写出条数。

    跨 run 的同 key 记录在这里收敛：每路输入各自有序，堆顶永远是当前
    最小的 (record_key, seq)，同一 key 第一次弹出的就是全局最早一条，
    之后同 key 的记录全部丢弃。
    """
    readers = [RunReader(path, guard) for path in paths]
    try:
        def stream():
            heap = []
            for index, reader in enumerate(readers):
                item = reader.next()
                if item is not None:
                    seq, record = item
                    record_key = key(record)
                    heapq.heappush(heap, (record_key, seq, index, record))
            last_key = _MISSING
            while heap:
                record_key, seq, index, record = heapq.heappop(heap)
                item = readers[index].next()
                if item is not None:
                    next_seq, next_record = item
                    next_key = key(next_record)
                    heapq.heappush(
                        heap, (next_key, next_seq, index, next_record)
                    )
                if record_key != last_key:
                    yield seq, record
                    last_key = record_key

        return write_run(out_path, stream(), guard)
    finally:
        for reader in readers:
            reader.close()
