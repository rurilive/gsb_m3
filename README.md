# crtkit

同余方程组工具集，纯标准库，无外部依赖。

## 现状

`crtkit/crtkit.py` 提供一组朴素但正确的函数：

- `search_first_solution(residues, moduli)`：从零开始逐个候选整数往上试，返回第一个同时满足全部方程的解
- `has_solution(residues, moduli)`：用同一个试值过程判定方程组是否有解
- `solve(residues, moduli)`：给出一个解，找不到就抛无解异常
- `smallest_non_negative(residues, moduli)`：试出来的第一个解即当作最小非负解
- `solutions_in_range(residues, moduli, low, high)`：区间内逐个候选整数试出全部解
- `count_in_range(residues, moduli, low, high)`：区间内的解个数
- `count_search_steps(residues, moduli)`：数一下本组方程要试探多少个候选整数才找到解

不互质的模数不约分、不含逆元，靠更大范围硬试；余数为负或大于模数时先按模数规约。

异常统一挂在 `crtkit.crtkit.CrtkitError` 之下（也可从包根 `crtkit` 导入）：
`EmptySystemError`、`InvalidModulusError`、`NoSolutionError`、`InvalidRangeError`、
`InvalidBoundsError`。

## 问题

解同余方程组是逐个候选整数往上试，全部模数的最小公倍数一大，试值次数就线性膨胀；
不互质的情形不约分，试的范围更大更慢；有无解判定、区间枚举、解个数都重复同一套试值，
规模上来后慢得离谱。

## 目标

见任务描述。约束：

- `tests/test_crtkit.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
