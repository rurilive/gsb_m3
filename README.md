# treehash

树同构判定与规范哈希的现有实现，纯标准库，无外部依赖。判定口径是两棵有根树
是否同构、两棵无根树是否同构，以及求一棵树的规范哈希、把一组树按同构关系分
组。

## 现状

- `Tree(n)`：无向简单树，顶点编号 0 到 n-1，`n` 为零表示空树。`add_edge(u,
  v)` 加边，`neighbors`、`degree`、`edges` 读结构，`centroids()` 求全部重心。
- `rooted_isomorphic(tree_a, root_a, tree_b, root_b)`：两棵有根树是否同构。
- `unrooted_isomorphic(tree_a, tree_b)`：两棵无根树是否同构。
- `rooted_canonical_hash(tree, root)`、`canonical_hash(tree)`：有根与无根的规范
  哈希。
- `group_isomorphic(trees)`：把一组树按下标分组，分组按组内最小下标升序。
- `pairwise_comparison_count(trees)`：朴素分组这趟要做的两两递归比较次数。
- 异常：`TreehashError` 为基类，`TreeError` 管树的输入，`QueryError` 管查询
  参数。以上名字都能从 treehash 包直接 import。

这几个能力都建立在同一件事上：把一边的子节点与另一边的子节点两两配对，穷举
配对方式后再递归下去；无根树还要先枚举重心当根，再对每对重心做同样的递归。

## 问题

两两配对是平方甚至更高量级，无根比较在外面又叠了一层重心枚举；同一对子树被
反复比较，算过的形状没有任何复用；也缺少一条与两两递归互相印证的独立做法，
判定对不对只能靠这一路自证。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_baseline.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
