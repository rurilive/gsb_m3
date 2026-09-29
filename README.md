# graphiq

有向图分析库，纯标准库，无外部依赖。

## 现状

graphiq/graph.py 提供 Graph，邻接表存图，边可带一个非负权重
（默认 1.0，同向重复加边按覆盖处理，自环允许）。目前能用的分析
只有可达性一类：

- add_node(node) / add_edge(u, v, weight=1.0)：建图，端点懒登记
- nodes() / edges() / has_node / has_edge / weight / neighbors(u)：结构查询
- reachable(src)：从单个源点做一次深度优先搜索，给出可达集合，含 src 自身
- reachable_all()：对每个节点各做一次搜索，得到全对可达

权重在加边处校验：负权、非数值、布尔值一律抛 ValueError。
tests/test_reach.py 锁住这些行为。

## 问题

分析能力只有全对可达：整张图能说的只有谁到得了谁，哪怕对一张静态图
也要对每个节点从头搜一遍。图上真正关心的结构一概拿不到，分不出哪些
节点互相可达、分不出谁必须排在谁前面、找不出无向意义下的桥与割点、
也算不出带权或不带权的最短路径。有环的时候更是无话可说，既给不出
拓扑序，也说不清环上到底有哪几个节点。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_reach.py 基线一致（基线一个字不改）
- 新行为另开 tests/test_analysis.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）