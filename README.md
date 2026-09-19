# metrio

进程内指标收集包：计数器 + 直方图，三种文本格式导出。2019 年上线，纯标准库，无外部依赖。

## 对外 API（不可变更）

- `inc(name, n=1) -> int`：计数器加 n（n 可为负），返回加完的值
- `counter_value(name, default=0)`：读计数器，未注册返回 default
- `histogram(name)`：注册一个空直方图
- `observe(name, value)`：记样本，未注册会顺手注册
- `render_text() -> str`：人读格式；空注册表返回空串
- `export_json() -> str`：JSON，histogram 字段序 name,count,sum,avg,min,max,p50,p95,p999
- `export_prom() -> str`：prom 风格，quantile 行在前、_count/_sum 在后；空直方图无 quantile 行
- `reset()`：清空全部指标

导出格式（含字段顺序）是稳定契约，下游按字段序解析。分位数口径（最近秩法）与各边界行为以 `tests/test_meters.py` 为准。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 管线分三层：`registry.py`（实例状态）→ `snapshot.py`（统计口径：排序/求和/最近秩分位唯一一份）→ `renderers.py`（三个渲染器只吃快照，差异只剩字段序与数字格式）。
- `meters.py` 是默认 `Registry` 实例上的薄壳转发，模块级 `REGISTRY` 名字保留可导入。
- 三种导出不再各抄统计逻辑：`Snapshot` 只算一次，字段序契约（JSON 的 count 在前、prom 的 quantile 在前）固化在各自渲染函数里。
- 快照不可变且不含格式化，统计口径可脱离注册表/输出格式单独测试。
- 标签接入点：在 `Registry` 的计数器/直方图 key 上组合「名称 + 标签」，快照增加标签字段，各渲染器按格式补 `{k="v"}` 即可，管线与既有无标签输出不变。
