# kdx

高维空间上的最近邻查询工具包，纯标准库，无外部依赖。

## 现状

`kdx/tree.py` 提供 `PointSet` 与几个辅助入口，能力朴素但正确：

- `PointSet(points)`：维护一批等维度点，按插入顺序保留下标，构造时校验坐标与维度
- `nearest(point)`：对集合里每个点逐一算距离，取最小的那个，平局取较小下标
- `knearest(point, k)`：把所有点算完距离后整体排序，再取前 k
- `range_query_rect(lower, upper)` / `range_query_ball(center, radius)`：枚举所有点逐个判断是否落在闭矩形或闭球内
- `nearest_pair()` / `radius_count(center, radius)`：同样枚举全部点或点对
- `pruning_count`：朴素路径不做子树剪枝，计数恒为零

异常统一挂在 `kdx.tree.KdxError` 之下（也可从包根 `kdx` 导入）：
`InvalidPointsError`、`DimensionMismatchError`、`EmptyPointSetError`、
`InvalidKError`、`InvalidRadiusError`。

## 问题

每次查询都要遍历整个点集：最近邻与 k 近邻是全局线性扫描，范围查询也没有
任何空间裁剪，点数一大单次查询就明显变慢；而且没有可暴露的剪枝统计。

## 目标

见任务描述。约束：

- `tests/test_tree.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
