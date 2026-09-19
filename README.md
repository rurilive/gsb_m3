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

- `metrio/registry.py`：`Registry` 实例持有全部状态（计数器、直方图、注册顺序）；`metrio/meters.py` 的模块函数只是默认实例 `REGISTRY` 的薄壳转发。
- `metrio/snapshot.py`：排序、最近秩分位、sum/avg/min/max 的唯一口径；`Registry.snapshot()` 产出不可变 `Snapshot`，统计可脱离格式化直接单测。
- `metrio/render.py`：三个导出共用同一份 `Snapshot`，只做格式化（快照 → 渲染），字段序差异只存在于这一层，不再各抄一份统计。
- 标签维度从 `Registry` 的键接入（name → (name, labels)），快照加 labels 字段，各渲染器自行决定如何拼输出。
