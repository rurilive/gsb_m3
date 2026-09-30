# triplet

序列组合计数工具包，纯标准库，无外部依赖。

## 现状

`triplet/naive.py` 提供朴素上升三元组统计，只有五项能力：

- `count_increasing_triplets_naive(values)`：数严格上升三元组，即下标递增且取值严格递增的三元组个数
- `count_non_decreasing_triplets_naive(values)`：数非下降三元组，即取值逐项不下降的三元组个数
- `has_increasing_triplet_naive(values)`：判定是否存在上升三元组
- `first_increasing_triplet_naive(values)`：返回按下标序列字典序最小的那个上升三元组
- `count_increasing_subseq_of_length_naive(values, length, strict)`：数指定长度的提升子序列个数

下标从零开始，三元组口径为三个下标严格递增。每项统计都把全部下标三元组枚举
一遍逐个判定，结果正确，但三重循环随长度按立方增长；长度为四或更长的提升子序列
直接把组合取出来判，是指数量级。`TripletAnalysis` 把序列绑定成分析器并给出固定
摘要；非法输入抛 `InvalidInputError`，长度非法抛 `InvalidLengthError`，两者都继承
`TripletError`。

它不提供树状数组或后缀式的独立做法可互相印证，也没有把三重枚举的次数与结构
访问次数摆出来，慢在哪里无从对照。

## 问题

只有一条朴素路径，每问一次就得把全部三元组或组合枚举一遍；序列一长、次数一多，
总代价按立方甚至指数增长；想把计数降到线性对数、或者想让多条独立做法逐项互相
印证，都缺入口。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_naive.py` 基线保持一致（基线一个字不改且必须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
