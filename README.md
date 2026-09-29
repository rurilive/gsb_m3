# rmqlib

区间最值工具，纯标准库，无外部依赖。

## 现状

`rmqlib/rmq.py` 提供 `NaiveRMQ`：

- `query_min(l, r)`：半开区间 [l, r) 上的最小值，空区间返回 None
- `query_max(l, r)`：半开区间 [l, r) 上的最大值，空区间返回 None
- `query_argmin(l, r)`：最小值首次出现的下标，空区间返回 None
- `query_many(ranges)`：对一批区间逐个求最小值
- `value_at(i)` / `as_list()` / `__len__`：读取序列

内部只留一个整数列表。每问一次区间，就把区间从头整个扫一遍，
既没有预处理，也没有下标缓存或二维结构；区间一多，重复白扫很多。
区间非法（左端大于右端、端点越界、端点为 None）时抛 `ValueError`。

## 问题

逐项扫描使得单次查询是线性代价，查询数量一大就白扫；没有稀疏表、
没有二维子矩阵查询、没有分块预处理、也没有能共享预处理的批量处理。

## 目标

见任务描述。约束：

- `tests/test_rmq.py` 是行为基线，一个字不许改，必须原样全绿
- 新行为另开 `tests/test_sparse.py`，用固定序列与逐字断言
- 纯标准库

## 运行

```bash
python3 demo.py                           # 区间最值现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```

（实现后补，10 行以内）
