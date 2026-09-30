# wgraph

带非负权图上的最短路，纯标准库，无外部依赖。

## 现状

wgraph/shortest.py 提供最朴素的 WeightedGraph：

- add_node / add_edge：邻接表存图，默认有向，权值须为非负整数，否则抛 EdgeError
- neighbors / nodes / has_node / node_count / edge_count：图结构查询，未知点抛 UnknownNode
- shortest_distances(source)：每轮线性扫描未访问点里距离最小的一个，再松弛其邻居，
  结果对，但每轮线性找最小使代价随点数平方级上涨，没有优先队列
- shortest_predecessors(source)：同样扫描法求前驱
- shortest_path(source, target)：由前驱还原一条最短路径，不可达返回空列表

## 问题

只能求单源、只能靠线性扫描，点数一多就慢得没法用；没有堆优化、没有堆操作计数，
也没有另一条独立口径去交叉核对结果，前驱路径与权值和的一致性无从验证，多源与
负权输入更没有快速失败。

## 目标

在现有实现上补出堆优化主路径、独立朴素口径交叉核对、多源、前驱路径还原与负权
快速失败，见任务描述。约束：

- 现有行为与 tests/test_shortest.py 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
