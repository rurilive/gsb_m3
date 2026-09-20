# evschema

审计事件存储，纯标准库，无外部依赖。

## 现状

- `evschema/schema.py`：`Schema` 声明一个事件类型某个版本的字段（名到类型的映射）、必填字段、默认值表与重命名表；`validate(data)` 返回问题描述列表，`type_ok(value, name)` 是类型判据
- `evschema/compat.py`：`check_compatibility(old, new)` 返回 `Compatibility(ok, reasons)`，判定与理由见文末
- `evschema/registry.py`：`SchemaRegistry` 按类型和版本保管 Schema，提供 `register` / `get` / `latest` / `versions` / `names`；`register` 先对相邻旧版本判兼容，不兼容拒绝；构造传 `path` 即落盘，同路径重建实例可恢复
- `evschema/store.py`：`EventStore` 追加写行式 JSON 文件，`append(etype, data, version=None)` 按对应版本的 schema 校验后落盘并返回序号，`read(version=None)` 按写入顺序读回（默认升级到最新，传旧版本号则降级读），`count()` 数条数，`stats()` 给计数快照

数据文件一行一个事件：`{"seq": 1, "type": "order", "v": 1, "data": {...}}`。

## 目标

见任务描述。约束：现有行为与 `tests/` 基线保持不变，纯标准库。

## 运行

```bash
python3 demo.py                           # 追加、校验、读回现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

## 实现说明

- 兼容判据：删字段、改类型、旧可选字段收紧成必填均拒绝；新增字段必须带默认值；`renames` 声明的改名视为同一字段，判定与升级都认
- `register` 对新版本自动判定，不兼容抛 `SchemaError`（含全部理由）且不落盘；注册表落盘为 JSON 原子替换，恢复后版本与判定一致
- 升级（`read()` 默认）：逐级应用改名链并补各版本默认值，`v` 更新到最新；已在最新的事件原样返回
- 降级（`read(version=k)`）：反向应用改名，只保留目标版本声明的字段，其余直接丢弃，不回补默认值
- 升降级只在读路径发生，数据文件字节不变；方案按 （类型， 源版本， 目标版本） 缓存只建一次
- `stats()` 的 `upgrades` 是升级条数，`plans` 是方案构建次数；十万条升级读一遍压在十秒内
