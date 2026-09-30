# centdecomp

树上路径统计的现有实现，纯标准库，无外部依赖。统计口径是距离恰好等于某值
的路径条数、距离不超过某值的路径条数，以及最远路径的长度与端点。

## 现状

- `Tree(n)`：无向带权树，顶点编号 0 到 n-1，边权为非负整数。`add_edge(u, v,
  weight=1)` 加边，`neighbors`、`edges`、`degree` 读结构，`path_distance(src, dst)`
  沿唯一路径累加边长（同点得 0），`all_pairs_distances()` 枚举全部无序点对及其
  距离，`pair_count()` 给点对总数。
- `count_exact(tree, d)`：距离恰好等于 d 的点对数。
- `count_at_most(tree, d)`：距离不超过 d 的点对数。
- `diameter(tree)`：返回 `(长度, 端点甲, 端点乙)`，并列时端点编号字典序最小。
- `enumerate_pair_visits(tree)`：朴素做法要枚举的点对数。
- 异常：`CentdecompError` 为基类，`TreeError` 管树的输入，`QueryError` 管查询
  参数。以上名字都能从 centdecomp 包直接 import。

这几个能力都建立在同一件事上：把所有无序点对枚举出来，逐对求路径距离再判定。

## 问题

点对枚举是平方量级，每对还要单独走一次路径搜索，顶点稍微一多就慢到不可用；
逐对求距离时同一段路被反复重走，算过的结果没有任何复用；也缺少一条与点对
枚举互相印证的独立做法，统计对不对只能靠这一路自证。

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
