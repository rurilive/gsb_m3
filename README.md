# kvsec

订单服务旁的本地键值存储与字段二级索引，纯标准库，无外部依赖。

## 现状

`kvsec/store.py` 提供 `KVStore`：

- 主数据落在目录下的 `data.log`，按行追加，`put(key, rec)` 覆盖写、`delete(key)` 删除（返回是否删掉）
- `get(key)` 取记录（独立副本，不存在返回 `None`），`keys()` 与 `scan()` 按主键排序
- 内存里只有主键到文件位置的目录，记录本体在文件里
- 打开时重放数据文件重建目录，末尾写了一半的记录截掉
- `sequence()` 给当前序号，每次写删加一；`stats()` 给主键数、读写计数与序号
- `subscribe(cb)` / `unsubscribe(cb)`：写删时同步回调 `(key, old, new)`，删除时 `new` 为 `None`

`kvsec/index.py` 提供 `SecondaryIndex(store, field)`：

- `lookup(value)` 查该值下的全部主键，排序返回，未命中给空列表
- `values()` 给全部索引值（排序），`rebuild()` 全量重建并返回条目数
- 记录里该字段缺失或不是字符串的，不进索引
- `stats()` 给 `rebuilds` / `lookups` / `records_scanned` / `entries`

## 问题

`lookup` 每次调用都要把主数据从头全量扫一遍，订单十万之后按状态查一页明显发卡，
写路径也指望不上它。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖、删除与索引查询演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
