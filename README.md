# unionx

内存里的连通判定小库，纯标准库，无外部依赖。

## 现状

unionx/graph.py 提供 NaiveUnionFind：

- add_node(node) / has_node(node) / nodes()：登记节点，按登记顺序枚举
- add_edge(a, b)：加一条无向边，重复边去重，按加入顺序留痕
- connected(a, b)：每次现场从一端做一遍广度优先遍历，走到另一端即连通
- component_of(node) / component_count() / component_sizes()：组件成员按登记顺序，孤立节点各算一个
- UnknownNode：访问未登记节点时抛出，携带该节点

## 问题

只有邻接表加广度优先遍历这一条路径。连通性、组件成员、组件数、组件大小
全是查询时现算的，边一多每次都要把整片重新走一遍，反复查询同一对点也不
留缓存，节点规模上去之后开销随查询次数线性叠加。想按大小或插入顺序枚举
组件成员可以，但没有任何增量维护可言。更关键的是没有撤销：加错一条边只
能整片重建；也没有带权概念，两点间的相对关系无从表达；批量操作只能一条
一条边加边查，拿不到与声明顺序绑定的一次性结果。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_connect.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
