# archlite

内部备份工具用的 tar-lite 归档格式读写：512 字节块 + 头部字段 + 校验和，无压缩。纯标准库，无外部依赖。

## 格式

每个条目 = 512 字节头 + 数据（补零到 512 的倍数），归档以两个全零块结尾。头部：0-4 魔数 `ARCL`；4-68 名字（utf-8，NUL 补齐，最长 64 字节）；68-76 数据长度（大端 u64）；76-80 校验和（大端 u32，对校验和字段置零后的整个头部按字节求和）；80-512 全零填充。

## 对外 API（不可变更）

- `ArchiveEntry(name, data)`：`name`/`data` 属性，按值比较
- `pack_bytes(entries) -> bytes` / `unpack_bytes(blob) -> [ArchiveEntry]`
- `write_archive(path, entries)` / `read_archive(path) -> [ArchiveEntry]`
- `find_entry(blob, name) -> ArchiveEntry | None`：找不到返回 None；遇到坏归档也返回 None（恢复工具依赖的历史行为）

错误口径以 `tests/test_archlite.py` 为准（魔数/校验和/截断各自的文案逐字锁定）。打包时条目顺序保持不变，输出字节级确定（无时间戳等易变字段）。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 两层职责：`writer.py`（写层，`pack_bytes`/`write_archive` 共用 `iter_blocks`）与 `reader.py`（读层，`unpack_bytes`/`read_archive` 共用流式核心 `_read_entries`）
- `format.py` 是头部布局唯一事实来源：所有偏移/长度常量（魔数 0、名字 4、长度 68、校验和 76）、`header_checksum`、`build_header`/`parse_header`；加版本字段只改这里
- `entry.py` 放 `ArchiveEntry` 与写侧校验 `check_entry`
- 错误路径分类：归档损坏（魔数/校验和/截断）由 `format`/`reader` 抛 `ValueError`，名字非 utf-8 抛 `UnicodeDecodeError`，入参类型错抛 `TypeError`，文件 IO 错误原样传播
- `find_entry` 在边界统一吞 `ValueError` 返回 `None`；不足一块的尾部字节与结束块之后的字节一律忽略
- `archive.py` 仅作重新导出的兼容层，`__init__.py` 导出的名字与签名不变
