# evschema

审计事件存储，纯标准库，无外部依赖。

## 能力

- `evschema/schema.py`：`Schema` 声明字段（名到类型映射）、必填、默认值表与改名表；`validate(data)` 返回问题列表，`type_ok(value, name)` 是类型判据
- `evschema/evolve.py`：`check_compatibility(old, new)` 返回 `(ok, reasons)`；`StepPlan` 是相邻版本间可升可降的单步方案
- `evschema/registry.py`：`SchemaRegistry(path=None)` 按类型和版本保管 Schema，注册新版本先与当前最高版本做兼容判定；给 `path` 时每次注册原子落盘，同路径重建实例即恢复
- `evschema/store.py`：`append(etype, data, version=None)` 校验后追加落盘；`read(version=None)` 默认升级到该类型最新版本（`v` 更新），给定版本则投影（升级或降级）；`stats()` 另含 `upgraded` 与 `plans_built`

数据文件一行一个事件：`{"seq": 1, "type": "order", "v": 1, "data": {...}}`。

兼容判据：删字段、改类型（含改名字段类型变化）、旧可选收紧成必填（保留或改名后）都拒绝；旧必填放开为可选允许；新增字段必须带默认值；改名在新版的 `renames` 里声明 `{旧名: 新名}`，判定与迁移都认可，可跨版本成链。

## 实现说明

- 兼容：拒删字段、改类型、旧可选收紧成必填；新增字段必须在 `defaults` 给默认值；`renames` 的旧名须在旧版消失、新名须为新版新增且类型不变。
- 升级口径：只在读路径沿相邻版本链做「改名搬值 + 新字段补默认值」，旧版本来就缺失的可选字段不回填；事件 `v` 更新为目标版本。
- 降级口径：反向改名搬回旧名；只丢高于目标版本「真正新增」的字段，改名目标随反向改名搬回，低版本仍缺失的可选字段保持缺失。
- 注册表落盘为独立 JSON 文件，原子替换写；同路径重建后版本与兼容判定一致。
- 文件只追加，任何 `read` 都不回写，读前读后字节一致。
- 缓存：相邻版本单步方案按 `(类型, 低版本号)` 只构建一次，`stats()["plans_built"]` 为其数量，`stats()["upgraded"]` 为实际升级的事件条数；降级沿用同一份方案、不另计数。

## 运行

```bash
python3 demo.py                           # 追加、校验、读回现状演示
python3 -m unittest discover -s tests -v  # 全部行为测试（基线 + 演进）
```
