# evschema

审计事件存储，纯标准库，无外部依赖。

## 现状

- `evschema/schema.py`：`Schema` 声明一个事件类型某个版本的字段（名到类型的映射）、必填字段、默认值表与重命名表；`validate(data)` 返回问题描述列表，`type_ok(value, name)` 是类型判据
- `evschema/registry.py`：`SchemaRegistry` 在内存里按类型和版本保管 Schema，提供 `register` / `get` / `latest` / `versions` / `names`
- `evschema/store.py`：`EventStore` 追加写行式 JSON 文件，`append(etype, data, version=None)` 按对应版本的 schema 校验后落盘并返回序号，`read()` 按写入顺序读回，`count()` 数条数，`stats()` 给计数快照

数据文件一行一个事件：`{"seq": 1, "type": "order", "v": 1, "data": {...}}`。

## 目标

见任务描述。约束：现有行为与 `tests/` 基线保持不变，纯标准库。

## 运行

```bash
python3 demo.py                           # 追加、校验、读回现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```
