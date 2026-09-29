# rangetree

闭区间的相交查询，纯标准库，无外部依赖。

## 现状

`rangetree/set.py` 提供一份朴素区间集 `RangeSet`：

- `Interval(left, right)`：闭区间 [left, right]，构造时校验左不大于右
- `insert(left, right)`：追加一段区间，返回落库后的副本
- `scan_point(point)`：线性扫描，返回包含该点的全部区间，保持加入顺序
- `scan_interval(left, right)`：线性扫描，返回与查询区间相交的全部区间，保持加入顺序
- `count()` / `__len__` / `intervals()`：区间个数与全部区间的副本列表（加入顺序）
- `access_count` / `reset_access_count()`：查询逐个走过的区间数，可归零

## 问题

只有一层朴素过滤：任何查询都要把全部区间走一遍，访问计数等于区间总数。
建树、增删、重叠合并、覆盖统计这些能力一个都没有入口，区间一多查询就全是全量扫描，
查询到底剪没剪枝无从证明。

## 目标

在当前基础上补出以左端点建的可高效相交查询、可增删、可合并的区间树，
并给出覆盖统计与有序结果，见任务描述。约束：

- 现有行为与 `tests/test_scan.py` 基线保持一致（基线一个字不改）
- 纯标准库，Python 3.10+
- 不许把相交查询做成换皮的全量扫描，必须能给出剪枝的证据

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）