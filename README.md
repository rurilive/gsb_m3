# walg

账本服务的单机预写日志，纯标准库。

- `walg/wal.py`：`WriteAheadLog.append()` 追加记录并同步刷盘，`read_from()` 按 LSN 重放
- `tests/test_wal.py`：行为与磁盘格式基线
- `demo.py`：顺序写入演示
