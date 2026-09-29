# skiplib

纯标准库的有序集合工具，无外部依赖。

## 现状

skiplib/sorted.py 提供 FlatSorted，内部只有一个保持升序的 list：

- add(x)：线性找到位置再插入，集合语义，重复插入幂等，新元素返回 True
- contains(x)：线性查找
- discard(x)：删除一个，不存在返回 False
- rank(x)：返回严格小于 x 的元素个数
- kth(i)：返回第 i 小元素（零基），越界抛 ValueError
- range_query(lo, hi)：线性扫描返回闭区间 [lo, hi] 内的元素列表
- len(s)：元素个数

## 问题

查找、定位、排名都要线性扫描，插入还要把后半段整体搬移，三处开销都是 O(n)。
结构里没有多层索引，插入顺序不参与结构，谈不上可复现的层高，也没有当前层数、
各层节点数这类自洽的统计，更没有能反映访问成本的计数。元素规模化之后这套
朴素有序 list 就成了瓶颈。

## 目标

把 FlatSorted 扩成以跳表为核心的集合工具，支持多层索引、前驱后继、排名定位、
区间枚举、层高可读统计与操作计数，见任务描述。约束：

- 现有行为与 tests/test_sorted.py 基线保持一致（基线一个字不改）
- 新行为另开 tests/test_skiplist.py
- 纯标准库
- 线性有序 list 路径不许删，两条路对同一批数据事实必须对得上

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
