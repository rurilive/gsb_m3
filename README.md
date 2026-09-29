# graphex

图论工具包，纯标准库，无外部依赖。

## 现状

`graphex/matrix.py` 提供 `ReachMatrix`，是一张无权的邻接矩阵：

- `add_node(name)`：登记节点，重复登记不改动已有结构
- `add_edge(a, b)`：加一条无向边，矩阵双向置位
- `has_edge(a, b)`：判断两点之间是否有边
- `reached_from(start)`：从起点出发按单位代价广度遍历，返回可达节点名（字典序）
- `connected(a, b)`：两点是否连通

每条边的遍历代价视为相同的单位代价，只回答可达与否，不记录边长，也不产出最短距离或路径。未知节点抛 `UnknownNode`，其余业务错误继承 `GraphError`。

## 目标

见任务描述。约束：

- `tests/test_matrix.py` 行为基线保持不变（基线一个字不改且必须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 无权连通演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
