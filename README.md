# ratelimit

内存固定时间窗限流器，纯标准库，无外部依赖。

## 现状

`ratelimit/core.py` 提供一份朴素限流器 `TimestampLimiter`：

- `TimestampLimiter(window, limit)`：窗口长度与窗口内放行额度，参数非法则抛错
- `allow(now, cost=1, label=DEFAULT_LABEL)`：在时刻 now 记一笔请求并返回是否放行
- `observed(at, label=DEFAULT_LABEL)`：只看时刻 at 的窗口内计数，不改状态
- `total_rejected(label=DEFAULT_LABEL)`：该维度累计被拒绝的笔数
- `history(label=DEFAULT_LABEL)`：每笔判定的时刻、窗口内计数与是否放行的记录
- `labels()`：出现过的维度，升序去重列表
- `naive_scan(stamps, window, at)`：一份独立的线性扫描计数函数
- `RateLimitError`：参数与状态错误的基类，继承 `Exception`

内建单调时钟从 0 起只增不减，窗口口径左闭右开，各维度之间完全隔离。

## 问题

每来一笔请求，限流器都把时间戳追加进该维度的列表，判定时线性扫描
整张列表数出窗口内的个数。结果是对的，但底账只增不减，历史越长扫描
越久，判定代价随记录总数线性膨胀；没有滑动窗口队列，也没有令牌桶，
拿不到均摊常数的放行判定，也没有可核对的底层操作计数。窗口模型只有
固定窗一种，无法与滑动窗口、漏桶、令牌桶在同一组参数下对照通过量。

## 目标

见任务描述。约束：

- `tests/test_core.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_sliding.py`
- 纯标准库，无第三方依赖，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
