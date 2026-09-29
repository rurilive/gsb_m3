# graphinc

可增量更新的有向加权图，纯标准库，无外部依赖。

## 现状

`graphinc/graph.py` 提供 `DirectedWeightedGraph`，构造时一次建成邻接表，
建成之后图不再变动：

- `add_node(node)` / `nodes()` / `has_node(node)`：节点登记与查询
- `add_edge` 仅在构造期可用，`edges()` / `has_edge(u, v)` / `weight(u, v)`：边查询
- `neighbors(u)`：直接后继 `(v, weight)`，按 v 升序
- `distances(src)`：Dijkstra 单源最短距离，不可达记 `math.inf`，结果按源点缓存
- `shortest_path(src, dst)`：`(距离, 路径列表)`，不可达为 `(inf, [])`
- `reachable(src)`：有向可达集合，含源点自身
- `topo_order()`：Kahn 拓扑排序，同层按字典序出队，有环抛 `CycleError`

权重在加边处校验：负权、非数值、布尔值一律抛 `ValueError`。

## 问题

图只能一次建成，建完就冻结：边既不能加也不能删；最短路结果按源点缓存，
在静态图下才成立；`topo_order` 只抛一个不带诊断的 `CycleError`，
环上有哪些节点无从得知。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_graph.py` 基线保持一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
