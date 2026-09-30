# eulerx

一笔画工具的朴素基线，纯标准库，无外部依赖。

## 现状

`eulerx/graph.py` 里是一张朴素多重图，无向边与有向边分别用列表逐条累积，
允许自环与平行边。所有一笔画问题都只靠枚举全部边顺序的排列、再逐条检查首尾
是否相接且每条边恰好走一次，阶乘的量级：

- `make_undirected()` / `make_directed()`：建空图
- `add_vertex(v)` / `add_edge(u, v)` / `add_arc(u, v)`：加点、加无向边、加有向边
- `vertices()` / `undirected_edges()` / `directed_edges()`：列顶点、列边
- `degree(v)` / `odd_degree_vertices()` / `in_out_degree()`：度、奇度点、入度出度
- `has_euler_path_undirected(g)` / `has_euler_circuit_undirected(g)`：可行性判断
- `naive_euler_path_undirected(g)` / `naive_euler_circuit_undirected(g)`：一条具体路径
- `naive_euler_path_directed(g)` / `has_euler_path_directed(g)`：有向图这两项
- `naive_edge_order_check_count(g)`：朴素路径枚举要检查的边序总数，即边数的阶乘
- `chain_count(texts)`：字符串接龙的可行排列个数，按回溯数出来

## 问题

只有枚举与回溯这一条路。求一条欧拉路径要数遍边数的阶乘个边序再逐个检查，
五条边就是一百二十次，八条边已是四万次，十条边起就完全跑不动；判断有无
欧拉路径也靠尝试排列，没有把连通性与奇度点的充要条件单独写成一路。三条结论
各算各的，路径对不对、可行性判断与路径给得是否自洽，没有第二把尺子来印证。
有向图的入度出度条件没有与路径求解互相核对，字符串接龙也没有与图上的路径
求解对上口径。空图、单点、无边的多点、单边、自环、平行边、多于两个奇度点、
不连通图这些边界，眼下既没有逐条锁死的口径，也没有统一错误类型。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_euler.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
