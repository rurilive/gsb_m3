# schemakit

一个纯标准库的记录模式迁移器，无外部依赖。记录随着业务演进要换字段、加
必填、改类型，schema 一版一版往前走，就需要一层能把记录从旧版本按序搬到
新版本、还能搬回去的机制，schemakit 就是干这件事的那一层。

## 现状

- `schemakit/migrate.py`：`migrate(record)`，按固定规则把一条记录改到 v1 格式。
  - `nickname` 重命名为 `name`（两者同时存在时 `nickname` 胜出）
  - 缺失 `name` 时补空串
  - `version` 一律置 1
  - 入参记录不被改写，返回新字典；非字典入参抛 `MigrationError`
  - `VERSION_KEY`：版本字段名，固定为 `"version"`
- `schemakit/errors.py`：`SchemaKitError` 基类，`MigrationError` /
  `UnknownVersionError` / `VersionGapError` / `CycleError` / `BranchError` /
  `ValidationError` 六种具体错误。

## 问题

迁移规则写死在一个函数里，只认一个终点版本；两个版本之间怎么连、连不上时
差哪一版，全靠调用方自己拼；前向做了没处回退，想按版本倒回去无从下手；
一批记录迁到一半失败会留下半迁移状态；字段类型与必填既无声明也无处校验；
对已经处于目标版本的记录也会白跑一遍。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
