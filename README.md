# pctstream

纯标准库的流式分位数统计小工具，无外部依赖。

## 现状

`pctstream/stream.py` 提供一份朴素实现 `NaivePercentileStream`：

- `push(x)`：追加一个数值，非数值抛出 `StreamError`
- `count()`：已推入的个数
- `median()`：中位数，空数据返回 `None`；奇数个取正中间，偶数个取中间两个平均
- `quantile(q)`：分位数，q 取 0 到 100 的整数，空数据返回 `None`，按位置取值
- `sorted_values()`：排序后的副本
- `StreamError`：参数错误的基类，继承 `Exception`

## 问题

每次一有查询，`median`、`quantile` 都把整段数据重新排序一遍再按位置取值，
接收得越多查询越慢；没有在线分位口径，没有滑动窗口，
也没有分桶近似，插入与查询全挤在一处，全量排序无法回答任意时刻的统计量。

## 目标

见任务描述。约束：

- `tests/test_stream.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_online.py`
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
