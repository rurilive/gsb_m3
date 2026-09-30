# detmod

一个只用 Python 标准库的模运算矩阵工具包，无外部依赖。做实验的脚本、批处理的
报表、教学演示里的模矩阵演算，都会碰到在模素数或模一般数下求行列式、做矩阵
乘法、求逆、解方程组、看秩这样的情形，detmod 就是干这件事的那一层。包内
matrix.py 提供 MatrixKit 类与一组朴素函数，秩与线性相关判定也在其中。

## 现状

- `detmod/matrix.py`：行列式有两条朴素路径，det_definitional 按定义对第一行
  展开、递归累加带符号余子式，perm_det 枚举全排列、按逆序数奇偶取符号累加，
  都是阶乘量级。
- `mat_mul` 三重循环逐项累加，`mat_pow` 把同一矩阵连乘指数那么多遍，指数多大
  就做多少次矩阵乘法。
- `inverse_adjugate` 靠伴随矩阵除以行列式，逐个代数余子式拼伴随阵。
- `solve_cramer` 用克拉默法则，每个未知量各算一次行列式。
- `det_terms` 与 `elimination_ops` 给出全排列项数与高斯消元操作次数，供规模
  对照。
- `mat_rank` 按最大非零子式阶数枚举行子集与列子集，`rows_dependent` 据此判线性
  相关。
- `mod_inverse` 先试扩展欧几里得，无逆元时如实抛 InverseErro。
- `detmod/matrix.py` 的 DetErro 是所有可诊断错误的基类，派生 MatrixErro、
  ModErro、InverseErro。

## 问题

行列式停在按定义递归展开与全排列枚举的阶乘量级，阶数一高就跑不动；矩阵幂是
指数多大就做多少次立方量级的乘法；求逆靠伴随矩阵，每个元素都要算一次余子式
行列式；解方程组逐个分量各算一次行列式，几件事各走各的路，互相印不上。实现
没有把规模压下来的手段，也缺少把全排列项数与消元操作次数摆在一起对照的口径。

## 目标

见任务描述。

## 运行

    python3 demo.py
    python3 -m unittest discover -s tests

（实现后补，10 行以内）
