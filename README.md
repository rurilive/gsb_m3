# evschema

审计事件存储，纯标准库，无外部依赖。

## 模块

- `evschema/schema.py`：`Schema` 声明一个事件类型某个版本的字段（名到类型的映射）、必填字段、默认值表与改名表（`renames`，旧名 -> 新名）；`validate(data)` 返回问题描述列表，`type_ok(value, name)` 是类型判据
- `evschema/evolution.py`：`check_compatibility(old, new)` 返回 `(ok, reason)`；`EdgePlan` 是相邻两版之间的升级/降级方案，`build_edge` 构建时再过一遍兼容闸门
- `evschema/registry.py`：`SchemaRegistry(path=None)` 按类型和版本保管 Schema，`register` 拒绝重复版本与不兼容的新版本；传入 `path` 时注册表落盘为行式 JSON，同路径重建自动恢复
- `evschema/store.py`：`EventStore` 追加写行式 JSON 文件，`append(etype, data, version=None)` 按对应版本校验后落盘并返回序号，`read(version=None)` 按版本投影读回，`count()` 数条数，`stats()` 给计数快照

数据文件一行一个事件：`{"seq": 1, "type": "order", "v": 1, "data": {...}}`。

## 兼容判据

注册新版本前，与版本号相邻的旧版本做判定，任一不满足即拒绝（`check_compatibility` 返回理由，`register` 抛 `SchemaError`）：

- 删字段（且没在 `renames` 里声明去向）拒绝；
- 改类型拒绝，改名后新名类型与旧名不一致同样拒绝；
- 旧版本的可选字段收紧成必填拒绝；
- 新增字段必须带默认值（`defaults`）；
- `renames` 的旧名必须存在于旧版本、新名必须声明于新版本，类型一致，新名不能与旧字段重合、也不能重复。

## 读回的升降级口径

- `read()` 不传版本：每个事件投影到该类型最新版本，`v` 更新为最新；已在最新版本的事件原样返回。
- `read(version=v)`：低于 `v` 的升级，高于 `v` 的降级；某类型未注册 `v` 时报 `SchemaError`。
- 升级：字段沿版本链逐边搬运，改名按 `renames` 跟随，跨越多版的改名链逐级还原；目标侧缺失且该版本声明了默认值的字段补默认值。
- 降级策略（明说）：新版本独有字段直接丢弃，改名沿链逐级还原成旧名；旧版本当时就缺的可选字段保持缺失，不补默认值。
- 升级只发生在读路径：数据文件始终只追加，`read` 只读打开，读前读后文件字节一致。

`stats()` 在原有的 `events` / `appends` / `reads` 之外新增：`upgraded`（升级过的事件条数）、`downgraded`（降级过的事件条数）、`plans_built`（构建过的相邻版本方案数）。方案按 `(类型, 低版本号)` 缓存，同一对类型版本只构建一次。

## 运行

```bash
python3 demo.py                           # 演进、升降级、恢复、计数演示
python3 -m unittest discover -s tests -v  # 全部行为测试（含对拍/恢复/性能）
```

## 实现说明（十行内）

1. 兼容判定只比相邻版本：注册时与版本号最近的高低邻版各判一次。
2. 改名以新版本 `renames`（旧名->新名）为准，判据与转换共用同一张表。
3. 新增字段必须有默认值；升级沿版本链逐边搬运并补目标侧默认值。
4. 降级只做反向搬运与丢弃新字段，不补默认值，丢失口径见上节。
5. 注册表按 Schema 一行一份 JSON 落盘，重建即恢复版本、改名与判定。
6. 事件文件只追加，read 只读打开，任何读都不改字节。
7. EdgePlan 按 (类型, 低版本) 缓存，同类型同版本边只构建一次。
8. stats 新增 upgraded / downgraded / plans_built 三个计数。
