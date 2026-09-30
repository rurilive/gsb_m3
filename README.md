# modarith

模运算工具集，纯标准库，无外部依赖。

## 现状

`modarith/modarith.py` 提供一组朴素但正确的模运算函数：

- `mod_pow(base, exp, mod)`：把底数连乘指数次，每步取模
- `mod_inverse(a, m)`：从一到模数减一逐个试乘，找模逆元
- `solve_linear_congruence(a, b, m)`：枚举零到模数减一的全部候选解
- `comb_mod(n, k, mod)`：先算阶乘再直接相除后取模
- `crt(residues, moduli)`：逐个区间合并一组两两互素的同余式

异常统一挂在 `modarith.modarith.ModarithError` 之下（也可从包根 `modarith` 导入）：
`InvalidModulusError`、`NegativeExponentError`、`InverseNotExistsError`、
`NoSolutionError`、`NotCoprimeError`、`InvalidCombinationError`。

## 问题

求幂是线性于指数的连乘，指数一大就慢；求逆元是逐个试乘，模数一大就慢；
解同余方程靠枚举全部候选解；组合数先算阶乘再相除，模数一大就溢出。

## 目标

见任务描述。约束：

- `tests/test_modarith.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
