# stampkit

报表服务内部用的时间戳工具库：秒/毫秒换算、按固定间隔的桶对齐、
时间跨度计算与归档打包。只依赖 Python 标准库。

## 快速上手

```python
from stampkit import to_millis, floor_bucket, align_many, duration_between

to_millis(1_700_000_000, unit="s")            # 1700000000000
floor_bucket(1_700_000_030_000, 60_000)       # 1699999980000
align_many([1_700_000_000_000, 1_700_000_060_000], 60_000, unit="ms")
duration_between(1_700_000_000_000, 1_700_000_090_000, unit="s")   # 90
```

## 接口与契约

内部的规范表示是整数毫秒。时间戳入参可以是 int，也可以是 float
（JSON 里常见的 1234567890.5 这类十进制字面量）；单位取 `"s"` 或 `"ms"`。

### 单位判定

- 入参显式给了 `unit` 就按 `unit` 解释，任何情况下都不再走启发式。
- 没给 `unit` 时按量级判定：`abs(value) >= 10**11` 判为毫秒，否则判为秒。
  十位的秒级时间戳判为秒，十三位的毫秒时间戳判为毫秒。

### units

- `guess_unit(value) -> "s" | "ms"`
- `to_millis(value, unit=None) -> int`：换算成整数毫秒，向下取整（向负无穷）。
  浮点入参按十进制字面值精确换算，不做二进制浮点近似。
- `to_seconds(value, unit=None) -> Decimal`：换算成秒，返回十进制精确值。

### align

- `floor_bucket(ts_ms, interval_ms) -> int`：不超过 `ts_ms` 的最大 `interval_ms` 整数倍。
- `ceil_bucket(ts_ms, interval_ms) -> int`：不小于 `ts_ms` 的最小 `interval_ms` 整数倍，
  `ts_ms` 已经在桶上时返回自身。
- `bucket_index(ts_ms, interval_ms) -> int`：`ts_ms` 所在桶的序号，
  等于 `floor_bucket(ts_ms, interval_ms) // interval_ms`。
- `bucket_span(start_ms, end_ms, interval_ms) -> int`：半开区间 `[start_ms, end_ms)`
  覆盖到的桶个数，`start_ms == end_ms` 时为 0，起点不在桶上时照样按覆盖数计。
- `align_many(values, interval_ms, unit=None) -> list[int]`：批量向下对齐，
  语义等价于对每个元素逐条调用 `floor_bucket(to_millis(...))`。这是报表导出的
  热路径，十万条量级要在亚秒内跑完。

取整方向与符号无关：`floor` 一律向负无穷，`ceil` 一律向正无穷，1970 年之前
的负时间戳同样适用。`interval_ms` 是任意正整数毫秒，允许小于一秒。

### span

- `duration_between(start_ms, end_ms, unit="ms") -> int`：两个毫秒时间点的间隔，
  按 `unit`（`"ms"`、`"s"`、`"min"`、`"h"`、`"d"`）输出整数个单位，向下取整（向负无穷）。
- `format_duration(ms) -> str`：可读格式，如 `"1d 2h 3m 4.500s"`。
- `pack_duration(ms) -> bytes` / `unpack_duration(blob) -> int`：归档索引用的
  定长编码，小端有符号 64 位整数，单位是毫秒，两者互为逆运算。

## 运行

```bash
python3 -m unittest discover -s tests    # 行为基线
python3 demo.py                          # 端到端演示
```
