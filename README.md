# metricbox

进程内指标收集的直方图模块，纯标准库，无外部依赖。

## 现状

`metricbox/histogram.py` 提供线程安全 `Histogram`（`threading.Lock` + list）：

- `observe(value)` 记录一个样本
- `count()` 返回样本总数
- `percentiles(*fractions)` 返回 `{分位: 值}`，按 (n-1) 线性插值；无样本抛 `ValueError`

样本永久保留，没有时间窗口。

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

- 窗口判定：样本时间戳 `ts` 满足 `now - ts > window_seconds` 即过期；恰满窗口的样本仍算窗口内。
- 清理策略：惰性清理，`observe`/`count`/`percentiles`/`snapshot` 访问时顺手清；`compact()` 显式清理并返回清理数。
- `observe` 返回本次被挤出的样本数；未配置窗口时恒为 0，行为与旧版一致。
- 分桶规则：`snapshot(edges)` 要求边界严格递增（否则 `ValueError`），返回 `len(edges)+1` 个计数；桶左闭右开，值等于边界归右桶。
- 时钟可注入（默认 `time.monotonic`），全部读写仍由同一把锁保护。
