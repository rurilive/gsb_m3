# statlib

纯标准库的流式统计小工具，无外部依赖。

## 现状

`statlib/running.py` 提供一份朴素实现 `NaiveStats`：

- `push(x)`：追加一个数值，非数值抛出 `StatError`
- `mean()`：算术平均，空数据返回 `None`
- `median()`：中位数，空数据返回 `None`；奇数个取正中间，偶数个取中间两个的平均
- `min()` / `max()`：最值，空数据返回 `None`；均为排序后取端
- `count()`：已推入的个数
- `sorted_values()`：排序后的副本
- `StatError`：参数错误的基类，继承 `Exception`

## 问题

每次一有查询，`median`、`min`、`max` 都把整段数据重新排序一遍，
数据一多就白排一遍，也无法在插入过程中在线回答统计量；
没有分位数、没有滑动窗口，插入与查询都是全量口径。

## 目标

见任务描述。约束：

- `tests/test_running.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_median.py`
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
