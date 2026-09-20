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

- 分两层：`writer.py` 负责条目→字节（`pack_bytes`/`write_archive` 共用一套头块拼装），`reader.py` 负责字节→条目（`unpack_bytes`/`read_archive` 共用 `_parse_header`，各自只做取块取数的驱动）
- 头部字段与偏移（0/4/68/76/80、块长、结束块）及校验和算法只收在 `format.py` 一份常量里；`entry.py` 放 `ArchiveEntry` 与入包校验
- 错误归类：输入类型错误抛 `TypeError`（"expected bytes" 等），头部魔数/校验和/截断抛 `ValueError`，文案集中在 `reader.py` 的构造函数里逐字锁定；坏 utf-8 维持原生 `UnicodeDecodeError`
- `find_entry` 不抛归档损坏错误，捕获 `ValueError` 返回 `None`；`FileNotFoundError` 由文件驱动原样上抛
- 不足一块的尾部字节、结束块之后的字节一律忽略（读层两个驱动同口径）
