# topoflow

有向图上的增量拓扑排序，纯标准库，无外部依赖。数据来自构建系统的任务依赖：
导入工具批量灌入依赖对，运行期再陆续增删边，调度器随时要当前拓扑序。

## 接口

`topoflow/engine.py` 提供 `IncrementalTopo`：

- `add_node(node)` / `add_edge(u, v)` / `remove_edge(u, v)`：单条增删，删一条不存在的边返回 False
- `add_edges(pairs)` / `remove_edges(pairs)`：批量入口，导入工具与日志回放走这两个
- `order()`：当前拓扑序，有环抛 `CycleError`
- `is_acyclic()`：当前图有没有环
- `in_degree(node)`：节点当前入度
- `rank(node)`：节点在当前序里的位置，下游按它做增量缓存
- `nodes()`：节点加入顺序
- `snapshot()`：复制一份底层 `DiGraph`，拿去做对拍

引擎内部只做局部修补：加边、删边先记账，查询时把积压的操作结算到序上。

## 判定基准

`topoflow/reference.py` 是每次从头重算的参考实现。约定：同一时刻有多个节点
可以出队时，先出加入序号小的那个。按这条规则，每张图只对应一份拓扑序，
引擎导出的序要跟它一致。

- `reference_order(graph)` / `reference_is_acyclic(graph)`：全量口径的答案
- `order_problems(graph, order)`：核对一份拓扑序，列出缺节点、次序反转之类的问题
- `topoflow/graph.py` 的 `DiGraph` 是底层存储，节点与边的登记顺序稳定

## 运行

```bash
python3 demo.py                          # 导入、回放、大图删边的现状演示
python3 -m unittest discover -s tests    # 行为基线
```
