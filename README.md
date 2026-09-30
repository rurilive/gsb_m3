# fftconv

多项式乘法与求值的朴素工具，纯标准库，无外部依赖。

## 现状

`fftconv/conv.py` 把多项式乘法交给双重循环：

- `Poly`：低位在前的系数表表示，构造时去掉高次零项，零多项式用空列表
- `Poly.mul_naive`：逐对系数相乘再按幂次累加，平方级复杂度
- `Poly.add`、`Poly.sub`：逐项对齐加减
- `Poly.evaluate`：霍纳方式逐项求值；`evaluate_many` 逐点算
- `convolve_naive`：两条系数序列的朴素卷积
- `from_roots`：由根逐个相乘构造多项式
- `check_coeffs`、`trim`、`result_length`、`check_pointwise`：校验与辅助
- `is_prime`、`check_modulus`、`is_power_of_two`、`check_transform_length`：模数与长度校验
- 异常统一挂在 `Erro` 下：`IllegalArgument`、`IllegalLength`、`IllegalModulus`、`PointMismatch`

## 问题

每乘两个多项式，都要把两边的系数逐一配对相乘再按幂次累加，
代价是两边长度的乘积，规模一大就上到平方量级，而结果只是一个系数表，
中间过程用完即弃。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_baseline.py` 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
