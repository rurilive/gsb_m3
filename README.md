# treediam

树统计工具的朴素基线，纯标准库，无外部依赖。

## 现状

treediam/tree.py 里是 Tree，一棵有根的带权树，节点用整数编号，根在构造时给定，
边权可以为负，weights 取 edge 或 vertex 决定路径权按边权还是点权累加：

- add_edge(parent, child, weight=1)：逐条累积邻接表
- nodes / children / pairs：列节点、列孩子、列全部点对
- path(a, b) 与 path_weight(a, b)：朴素地在两点之间走一遍求路径与路径权
- traverse(start)：从一个点出发走遍全树，返回访问序列

同一模块 treediam/tree.py 里还有几个朴素统计，都靠枚举与反复遍历：

- diameter(tree) 与 diameter_path(tree)：枚举所有点对，逐个算路径权取最大
- farthest_from / farthest_distance：对每个点各算一次到起点的距离取最大
- all_distances / distance_sum / all_distance_sums：逐点算距离再累加
- max_distance_sum_point：对每个点各求一次距离之和再取最大
- pair_distance_sum：枚举所有点对，逐个算路径权再累加
- center / centroid：逐个候选点摘掉后重跑连通分量
- in_same_root / reachable_from / is_tree / components：连通性朴素判定

## 问题

只有这一层朴素实现，规模一大就崩。求直径要枚举所有点对，每对再走一遍路径，
点数一多就是平方乃至立方的量级；求距离之和、求离得最远的点、求重心也都是
对每个点重来一次完整遍历，重复算的中间结果全都丢了；点权口径与边权口径各写
一套，互相对不上时也没有第二把尺子来印证；单节点、两节点、链、星、菊花、
零权边、负权边、并列直径、并列重心、成林这些边界，眼下既没有明确口径也没有
统一错误类型。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_tree_stats.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
