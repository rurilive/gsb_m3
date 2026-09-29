# joinlab

面向内存行的等值连接工具箱，纯标准库，无外部依赖。

## 现状

`joinlab/join.py` 提供 `NestedLoopJoin`，对左右两表逐对比较连接键：

- `join(left, right, left_key, right_key=None)`：返回所有等值配对，每个元素是 (左行, 右行)
- `count(left, right, left_key, right_key=None)`：返回配对数，等价于 join 结果长度

它用双重循环按相等关系比较，没有哈希表、没有排序归并、没有分块，内存占用随左右
表规模的乘积增长。`tests/test_join.py` 锁住这些行为。

## 目标（见任务描述）

把 `joinlab` 从双重循环扩成多种连接算法，新增哈希连接、排序归并连接、超出内存预算
的分块落盘、多表连接计划、空值与类型口径以及边界与非法条件处理，并与朴素连接对拍。
全部仍在 `joinlab` 包内，纯标准库。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
