# lcdecomp

树上按深度统计的求解器，纯标准库，无外部依赖。

## 现状

`lcdecomp/core.py` 提供 `LongChainTree`：

- `load(n, edges, weights)`：载入结点数为 `n` 的有根树，根固定为编号 0，
  `edges` 是 `(u, v)` 无序点对列表，`weights` 是长度 `n` 的结点权重列表
- `node_count()`：结点个数
- `heuristic_child(u)`：按子树节点数口径给出 `u` 的重儿子，无儿子返回 `None`
- `depth_counts(u)`：以 `u` 为根的子树内每个深度的节点个数列表，下标为相对深度
- `deepest_depth(u)`：以 `u` 为根的子树内最深节点的相对深度
- `depth_distribution()`：全树内每个绝对深度的节点个数列表
- `merge_cost()`：朴素归并深度数组时的元素拷贝总次数估计

现状是朴素做法：重儿子按子树节点数划分；计算深度分布时，对每棵子树先
深搜求出相对深度数组，再把各儿子的数组整份取出、逐个元素拷贝进一张新
数组相加。每个结点都要新建一份长度等于其深度的完整数组，深度一深、
结点一多，拷贝总量迅速膨胀，退到平方甚至更高量级。异常基类是 `Erro`，
输入不合法抛 `InputErro`，查询未登记结点抛 `UnknownNodeErro`，
边连不成一棵树抛 `DisconnectedErro`。

## 问题

没有按深度最大的儿子划分长链的做法，每个结点都新建整份深度数组逐个拷贝，
规模一大就慢；也没有另一条独立口径可以在固定输入上与新做法逐项对照。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素深度统计演示
python3 -m unittest discover -s tests    # 行为基线测试
```

（实现后补，10 行以内）
