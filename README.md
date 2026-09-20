# metricbox

进程内指标收集的直方图模块，纯标准库，无外部依赖。

## 现状

`metricbox/histogram.py` 提供线程安全 `Histogram`（`threading.Lock` + list）：

- `observe(value)` 记录一个样本，返回本次被挤出窗口的样本数
- `count()` 返回窗口内样本总数
- `percentiles(*fractions)` 返回 `{分位: 值}`，按 (n-1) 线性插值；无样本抛 `ValueError`
- `compact()` 显式清理过期样本，返回清理数
- `snapshot(bucket_edges)` 按严格递增边界导出窗口内分桶计数

构造参数 `window_seconds=None` 时样本永久保留，行为与初版一致；配置后启用
滑动窗口，`clock` 可注入（默认 `time.monotonic`）。

## 问题

直方图的数据是全生命周期的。流量模式一变（刚扩容、刚切流），旧样本把分位数拖住，监控看到的 P99 迟迟反映不了现状，告警跟着失真。

## 目标

见任务描述。约束：

- `tests/test_histogram.py` 是行为基线，一个字不改
- 不配置窗口时行为与现状完全一致
- 纯标准库

## 运行

```bash
python3 demo.py                          # 直方图演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 窗口判定：样本 `(时间戳, 值)` 按时间戳有序存放，`now - ts < window_seconds` 算窗口内，恰满窗口的样本保留。
- 时钟：构造时注入无参可调用对象，默认 `time.monotonic`；不配置窗口时不读取时钟。
- 统计：`count`/`percentiles`/`snapshot` 用二分定位窗口起点，只读窗口后缀，不触发清理。
- 清理策略：过期样本惰性删除，仅 `observe` 顺带物理挤出；`compact()` 可显式清理并返回删除条数。
- 分桶规则：桶为 `(edges[i-1], edges[i]]`，共 `len(edges)+1` 个；值等于边界归右桶（`bisect_right`），边界须严格递增。
