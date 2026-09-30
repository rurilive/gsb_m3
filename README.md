# treeknapsack

树形依赖选择（树上背包）工具，纯标准库，无外部依赖。

## 现状

treeknapsack/knapsack.py 提供 TreeKnapsack：

- TreeKnapsack(n, parent, weight, value, cap)：以物品数、父指针、重量表、价值表与
  容量为底座，n 为非负整数且不超过物品数上限，父指针长度为 n、取值是 -1 或
  合法编号且不成环，重量与价值为非负整数序列，容量为非负整数
- brute_best(capacity=None)：根节点最优价值与选中物品集合，并列取编号字典序最小
- brute_exact(cap)：恰好装满容量 cap 的最优价值与集合，装不满返回 None 与空表
- brute_subtree(root, cap)：子树 root 在容量 cap 下的最优价值与集合（子树根独立看待）
- brute_all_subtrees(cap)：每个节点当子树根各算一次，按编号升序返回
- brute_visits：上一次计算的朴素枚举次数
- forest_count / is_forest：根节点个数与是否为空树或森林

内部逐个考虑物品的选与不选，依赖闭合时沿父指针走到根检查祖先，每个子树再对
子树内节点单独枚举取数组合，规模一大就指数爆炸，但结果正确。

## 问题

逐个考虑选与不选是指数量级，依赖闭合判定自己走一遍路径；每个子树再单独枚举一遍
节点的取数组合，没有任何把子树背包结果按容量卷积合并进父节点的手段，也拿不出
计数说明省了多少。没有独立的第二条路径与朴素路径逐项对账，空树、单节点、链状树、
星形树、全部重量为零、某物品重量大于容量、父节点不选子节点不可选、容量为零、
多个根节点这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_knapsack.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
