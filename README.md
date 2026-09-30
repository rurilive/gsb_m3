# dncopt

分段最优划分工具包，纯标准库，无外部依赖。

## 现状

dncopt/core.py 提供 Optimizer：

- Optimizer(costs)：一条非负整数代价序列
- Optimizer.costs：按登记顺序给出的代价元组
- Optimizer.size：元素的个数
- seg_sum(i, j)：第 i 到第 j 个元素这一段的和，逐项累加
- seg_cost(i, j)：该段的总代价，记为该段和的平方
- segmented_dp(groups)：按组逐层给出前若干元素分成若干组的最小总代价
- decision_points(groups)：与代价表并行的最优切割点表，并列取下标最小
- min_cost(groups)：整条序列分成指定组数的最小总代价
- naive_op_visits：最近一次调用里枚举切割点的次数
- 异常基类 DncoptErro，下分 InputErro

## 问题

对每一组、每个前缀枚举全部上一刀位置，取总代价最小者，切割点数量随
长度与组数一起涨，规模一大就是平方乃至更高量级，纯粹靠机器硬扛；
最优切割点把同样的枚举重来一遍；计数只是为了暴露朴素枚举的次数，
没有一条更聪明的路径能把每层的枚举量压下来。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_core.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
