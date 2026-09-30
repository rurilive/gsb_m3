# matchx

一个只用 Python 标准库的二分图匹配小工具，纯内存，无外部依赖。

## 现状

`matchx/bipartite.py` 提供 `BipartiteMatcher`，维护一张二分图：左侧一组点、
右侧一组点，边用 `(左点, 右点)` 集合表示，重复边只算一次，自环与空点当场
拒掉。当前所有结果都由枚举驱动：

- `add_edge(left, right)`：加一条边，重复边不重复计，返回自身
- `left_nodes` / `right_nodes` / `edges()` / `edge_count()` / `node_count()`：
  读图，边按端点排序后稳定给出
- `neighbors(left)`：某个左侧点连到的右侧点集合
- `max_matching_size()`：回溯枚举全部匹配，取条数最多的那条
- `is_maximum(matching)`：枚举全部匹配，拿给定匹配的大小与真正最大值比
- `perfect_matching_exists()`：最大匹配是否覆盖全部左侧点
- `max_matching()` / `matched_to(left)`：给出一个最大匹配方案并回查配对
- `min_vertex_cover()`：枚举两侧点的全部子集，挑能盖住每条边的最小点集
- `max_independent_set()`：枚举全部子集，挑内部没有任何边的最大点集

## 问题

枚举的量随点数指数增长：求最大匹配要回溯走遍每个左侧点配或不配的全部组合，
判断一个匹配是否最大要把这些组合再走一遍，最小点覆盖与最大独立集更是把两侧
点的子集挨个试。点数一多就迅速撑不住，而且当前既没有增广的观念，也没有任何
计数能说明一条更聪明的做法省了多少。

## 目标

在当前基础上，以增广路为核心把 `BipartiteMatcher` 扩成二分图组合工具集，
见任务描述。约束：

- 现有行为与 `tests/test_bipartite.py` 基线保持一致（基线一个字不改）
- 纯标准库，不得引入任何外部依赖
- 枚举那套朴素路径保留，新老两条路对同一批数据给出的事实必须一致

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
