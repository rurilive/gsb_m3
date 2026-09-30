# combperm

纯标准库的组合与排列枚举小工具，无外部依赖。

## 现状

`combperm/enumerate.py` 提供一份朴素实现 `NaiveEnumerator`：

- `NaiveEnumerator(size)`：以集合规模为核心参数，集合恒为 0 到 size 减一
- `size()`：规模
- `combinations_count(k)`：取 k 个的组合数，k 越界抛出 `CombPermError`
- `permutations_count(k)`：取 k 个的排列数，k 越界抛出 `CombPermError`
- `all_combinations(k)`：全部组合，按字典序
- `all_permutations(k)`：全部 k 元排列，按字典序
- `nth(k, index, mode)`：按字典序取第 index 个，序号从零开始
- `rank(seq, mode)`：给出序列的名次，名次从零开始
- `CombPermError`：参数错误的基类，继承 `Exception`

## 问题

`combinations_count`、`permutations_count`、`nth`、`rank` 都要现场把全部结果
展开一遍再取值或数位次，每一位都在尚未使用的元素列表里做线性查找，
规模一大代价就随阶乘级上涨；名次与序号之间没有解析互逆公式，
带重复元素的去重组合与去重排列、以及固定字典序取第几个的大整数解法都还没有。

## 目标

见任务描述。约束：

- `tests/test_enumerate.py` 是基线，一字不许改且必须全绿
- 新行为另开 `tests/test_advanced.py`
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
