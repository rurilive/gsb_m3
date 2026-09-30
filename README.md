# spanlab

序列左右边界的朴素工具箱，纯标准库，无外部依赖。

## 现状

spanlab/stacks.py 提供一组最直白的实现，全部用双向扫描或双重循环：

- first_greater_left / first_greater_right / first_smaller_left / first_smaller_right：
  对某个位置，从它出发向左或向右一格一格地看，谁先满足严格更大或严格更小就返回谁，
  一直没有就返回约定值 -1
- bounds_greater / bounds_smaller：把每个位置左右两侧的下标各拼成一个列表返回
- largest_rectangle：柱状图最大矩形面积，逐位置把它当作最矮的那一根再向两侧扩
- sum_of_subarray_mins / sum_of_subarray_maxs：所有子数组的最小值之和与最大值之和
- count_subarrays_as_min：每个元素作为最小值出现的子数组个数
- count_brute_scans：统计做一轮左右边界查询总共比较多少次
- SpanError / InvalidInputError：自己抛出的异常统一派生自 SpanError
- 非整数、bool、越界下标一律在入口抛 InvalidInputError

## 问题

每个位置都靠向左向右各扫一遍定边界，序列一长就退到平方量级：一次全量查询要做的
比较次数随长度近似平方增长。既没有单调栈，也没有一次遍历；更复杂的问题如柱状图
最大矩形、子数组最小与最大之和、作为最小值出现的子数组计数，全是双重循环在内层
重算，一段长序列上反复白扫。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_stacks.py 基线一致（基线一个字不改，且必须全绿）
- 新行为另开 tests/test_hybrid.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
