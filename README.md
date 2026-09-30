# dsutree

树上子树颜色统计的求解器，纯标准库，无外部依赖。

## 现状

`dsutree/core.py` 提供 `DsuTree`：

- `load(n, edges, colors)`：载入结点数为 `n` 的有根树，根固定为编号 0，
  `edges` 是 `(u, v)` 无序点对列表，`colors` 是长度 `n` 的颜色编号列表
- `node_count()`：结点个数
- `subtree_counts(u)`：以 `u` 为根的子树内，颜色到出现次数的映射
- `dominant_color(u)`：子树内出现最多的颜色，并列取编号最小者
- `all_subtree_counts()`、`all_dominant_colors()`：逐结点的全量结果
- `visit_count()`：逐结点单独统计口径下的访问次数

现状是朴素做法：对每个结点 `u`，从 `u` 出发重新深搜它整棵子树，
用字典累加颜色频次，再挑出主色。每个结点都把子树重走一遍，
子树规模之和一涨，代价就退到平方甚至更高量级。异常基类是 `DsuError`，
输入不合法抛 `DsuInputError`，查询未登记结点抛 `UnknownNodeError`，
边连不成一棵树抛 `DisconnectedError`。

## 问题

没有一次遍历重用小儿子结果的做法，每个结点都从头重走子树，规模一大就慢；
也没有另一条独立口径可以在固定输入上与新做法逐项对照。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素统计演示
python3 -m unittest discover -s tests    # 行为基线测试
```

（实现后补，10 行以内）
