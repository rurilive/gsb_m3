# samx

一段固定文本上的子串结构工具，纯标准库，无外部依赖。

## 现状

`samx/substrings.py` 提供 `NaiveSubstrings`，把文本的全部子串枚举进集合
去重后计数，判断模式是否子串用逐个起始位置的朴素匹配，出现次数用线性
扫描计数，子串按长度聚合也建立在集合之上：

- `all_substrings()`：枚举全部子串（含重复），按起点、终点升序
- `distinct_substrings()` / `count_distinct_substrings()`：集合去重与计数
- `is_substring(pattern)`：朴素匹配判定模式是否出现
- `count_occurrences(pattern)`：线性扫描统计出现次数
- `count_substrings_by_length()` / `distinct_substring_lengths()`：聚合

## 问题

枚举全部子串先吃下一大块内存，子串一多就平方级时间加大量内存；判定与
计数都要对文本反复线性扫描，没有可复用的结构；不同子串个数只能靠集合
大小兜底，文本稍长就同时扛不住时间与内存。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_substrings.py` 基线保持一致（基线一个字不改）
- 纯标准库，异常继承 `Erro` 基类

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
