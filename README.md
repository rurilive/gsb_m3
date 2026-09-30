# tspx

完全图上最短闭合回路的朴素工具，纯标准库，无外部依赖。

## 现状

tspx/tour.py 提供 TspSolver 与两个工具函数：

- distance(a, b)：两点之间的欧氏距离
- tour_length(points, order)：按给定次序把点依次相连再回到起点的闭合回路长度
- TspSolver(points)：坐标列表，逐点转成浮点，允许重复与空表
- count()：点数
- enumerate_best()：枚举全部排列挑最短回路，返回长度与次序；点数不超过 1 时返回零长度平凡次序
- enumerate_count()：枚举口径下需要考察的排列数
- nearest_neighbor(start)：从 start 出发每次挑最近的未访问点，返回次序与长度
- nearest_neighbor_over_starts()：对每个起点各做一次，返回其中最短的长度、次序与起点

内部就是全排列走一遍再整段重算回路长度，或对每个起点从头做一遍最近邻，
规模一大就明显变慢，但结果正确。

## 问题

只有全排列枚举这一条精确路子，阶乘级，点多几个就跑不动；近似只有朴素最近邻，
对每个起点重来一遍也没有插入、交换或退火之类的改进，回路质量与代价的差距看不出；
精确解到底比近似好多少、与枚举暴力口径是否逐项一致，没有对照；
状态数与排列数的差距、规模上限之外的口径也都没有暴露。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_tour.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
