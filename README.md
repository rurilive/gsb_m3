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

以下四个机房断电后暴露的恢复缺陷已修复（对应回归测试见 `tests/test_wal.py`）：

1. **断电半帧被当成有效记录应用**
   根因：`_read_frames` 在尾部 CRC 不足 4 字节时把校验值置 0，并用 `if crc_val` 跳过比对，于是只写了一半的帧（payload 恰好是合法 JSON、CRC 缺失）直接通过；此外 CRC 恰好为 0 的合法帧与“无校验”无法区分。修复：CRC 必须读满 4 字节，且无条件与 `zlib.crc32(head + payload)` 比对，payload 截断同样视为坏帧；遇坏帧即停，丢弃断电残尾。

2. **300+ 字节字段每次重启必丢**
   根因：长度头写入用 `struct.pack("<H", n)`（2 字节小端），读取却用 `int.from_bytes(head[:1], "big")`（只取 1 字节），读写不对称。payload ≥ 256 字节时读出的长度被截断（300 变成 44），后续按错误偏移解析，整段日志从该帧起全部解码失败。修复：读取统一改为 `struct.unpack("<H", head)`，并对超过 65535 字节的 payload 显式报错。

3. **重启后旧值覆盖新值**
   根因：段文件按文件名字典序排序，`wal-10.log`、`wal-11.log` 排在 `wal-2.log` 之前，超过 9 个段后重放顺序错乱，更早的旧值后应用、覆盖新值。修复：从文件名解析段编号，按数字序排序重放；启动时也以磁盘上的最大段编号为基准开新段，不再复用旧编号。

4. **写入成功的记录断电后偶发消失**
   根因：`append` 只把帧写进 Python 文件对象的用户态缓冲区，从不 `flush()/fsync()`，只有切段（`checkpoint`）或 `close` 时才落盘；进程被直接杀掉或掉电时缓冲区数据丢失，造成“内存读得到、盘上没有”。修复：每条帧 append 返回前强制 `flush()` + `os.fsync()`；新建段时额外 fsync 目录，保证段文件目录项落盘。
