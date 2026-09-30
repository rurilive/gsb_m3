# leftistheap

优先队列合并工具的现有实现，纯标准库，无外部依赖。能力是建堆、插入、取最小、
弹出最小、合并两个堆、堆排序，以及给出合并这趟的规模量化出口。

## 现状

- `Heap(items=None)`：优先队列，底层是一条升序列表。`size`、`is_empty` 读规模，
  `peek_min` 取最小，`pop_min` 弹出最小，`insert` 插入，`to_sorted_list` 取
  升序快照，`drain` 反复弹出把堆清空。
- `build_heap(items)`：用一批元素建堆。
- `merge_heaps(first, second)`：合并两个堆，返回新堆，输入堆不改动。
- `merge_many(heaps)`：把一批堆顺次两两合并。
- `heap_sort(items)`：建堆后反复弹出最小，得到升序序列。
- `naive_merge_insert_count(first, second)`：朴素合并这趟逐个插入的累计次数。
- 构造工具在 `leftistheap.builders`：`from_values`、`empty_heap`、`single_heap`、
  `ascending`、`descending`、`constant`、`with_negative`、`two_heaps`。
- 异常：`LeftistHeapError` 为基类，`HeapError` 管构造与输入，`OperationError`
  管操作前置条件。以上名字都能从 leftistheap 包直接 import。

这几个能力都建立在同一件事上：堆就是一条升序列表，插入时从头线性扫描找位置
再后移插入，合并两个堆时把一边的元素逐个插入另一边。

## 问题

逐个插入在列表里线性找位置是平方量级，合并两个各含 n 个元素的堆要 n 次插入、
每次扫过一截，N 次合并叠起来就是平方以上；缺少一条与逐个插入互相印证的独立
做法，合并对不对只能靠这一路自证。

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
