# topocount

有向无环图的拓扑序计数工具，纯标准库，无外部依赖。

## 现状

topocount/dag.py 提供 DAGCounter 与 brute_permutations：

- DAGCounter(n, edges)：以点数与按输入先后给出的边表建图，点编号取零到 n-1，
  允许自环与平行边，构造时校验结构
- topological_orders()：全部拓扑序，按字典序升序给出
- has_topological_order()：是否存在拓扑序
- count_topological_orders()：拓扑序的个数
- min_topological_order()：字典序最小的拓扑序
- max_weight_order(weight)：权值和最大的拓扑序与最大权值和
- position_ranges()：每个点在各拓扑序里出现位置的最小值与最大值
- topological_orders 之外还提供 successor_map、predecessor_map、in_degrees
- reset_counters / counters：上一次枚举留下的排列访问数与边检查次数
- brute_permutations(n, edges)：独立的计数函数，返回排列访问数与边检查次数

内部把全部顶点排列逐个校验每条边的方向，排列数按阶乘增长，很慢，但结果正确。

## 问题

现在只有全排列枚举一条路，判是否存在拓扑序、数拓扑序个数、挑字典序最小的
拓扑序、取权值和最大的拓扑序、算顶点出现位置区间，全部靠把排列过一遍，
阶乘量级，点数一上去就不可用；所有查询共用一本计数账，分不清各条路各花了
多少；排列枚举次数与任何更省的做法之间没有对照，省了多少也拿不出数字；
空图、单点、无边、链、星形、完全有向无环图、有环、自环、平行边这些边界
只能靠肉眼去猜，异常与非法输入的口径也散在各处。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_dag.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
