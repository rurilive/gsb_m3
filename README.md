# centroid

树的重心、子树规模与树上路径问题的求解器，纯标准库，无外部依赖。

## 现状

`centroid/core.py` 提供 `TreeCentroid`：

- `load(n, edges)`：载入一棵树，`n` 是结点个数（编号 0 到 n 减 1），`edges` 是
  `(u, v, w)` 三元组列表，`w` 是正权，根固定为编号 0
- `nodes()`：全部结点编号，按升序，结果确定
- `subtree_size(root)`：以 `root` 为根时，结点到子树规模的映射
- `component_sizes(node)`：删掉 `node` 后各连通块的大小，按升序
- `largest_component(node)`：删掉 `node` 后最大连通块的大小
- `centroid()`：重心，最大连通块最小者，并列取编号最小者
- `centroids()`：全部满足重心条件的结点编号，按升序
- `centroid_property(node)`：最大连通块大小与是否超过半数的布尔值
- `path_stats(u, v)`：两点距离与路径上的最大边权
- `distance(u, v)`、`max_edge_on_path(u, v)`：单取距离或路径最大权
- `count_paths_within(limit)`：距离不超过上界的无序点对条数
- `brute_scale()`、`brute_pair_scale()`：朴素口径的规模估计

现状全部走枚举：子树规模对每个结点各跑一遍遍历；重心对每个结点把它删掉再求最大
连通块；两点距离先枚举点对，再各自上溯到根拼出路径逐条累加；路径计数枚举全部点对
再逐个求距离。口径直白、结果确定，但结点一多就退化到平方甚至立方量级。异常基类是
`CentroidError`，输入不合法抛 `CentroidInputError`，查询未登记结点抛 `UnknownNode`。

## 问题

没有一次后序遍历求出全部子树规模的线性做法，重心只能逐结点删点枚举；两点距离与路径
最大值没有借助最近公共祖先的快速口径；路径计数枚举全部点对，量级随结点数平方增长，
拿不到与线性或对数做法的访问次数对照。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素枚举求解演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
