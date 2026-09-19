# walog

元数据服务的预写日志与小型 KV 存储，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `walog/wal.py`：`WriteAheadLog`——帧格式 `[2B 长度][JSON 载荷][4B CRC]`，append / replay / checkpoint，超过段大小自动切段（`wal-N.log`）
- `walog/store.py`：`KVStore`——内存视图 + 日志持久化，`recover()` 重放重建

## 运行

```bash
python3 demo.py
```

## Known Issues
