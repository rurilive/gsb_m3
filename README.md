# permparity

排列的逆序数、奇偶性与置换分解的朴素求解器，纯标准库，无外部依赖。

## 现状

permparity/perm.py 提供以下函数，全部是直白做法：

- validate_perm(perm)：校验从零开始的排列，返回列表
- inversion_count(perm)：两两比较全部数对求逆序数，返回逆序数与比较次数
- parity(perm)：先算逆序数再看奇偶，返回 even 或 odd
- is_even(perm)：该排列是否偶排列
- cycle_decomposition(perm)：对每个元素反复标记求循环分解
- min_swaps(perm)：最少交换次数，元素个数减循环个数
- cycle_type(perm)：各循环长度的多重集合
- parity_by_cycles(perm)：用循环分解的符号判奇偶
- compose(left, right)：置换复合
- compose_parity(left, right)：复合后的奇偶性
- can_swap(a, b)：两个排列能否通过交换互化
- min_swaps_between(a, b)：把甲变成乙的最少交换次数，靠反复查找

逆序数与奇偶性都靠两两比较，平方量级，元素一多就不可用。

## 问题

现在只有平方量级的逆序数一条路，奇偶性与循环分解也都挂在它上面；
最少交换次数、循环长度、置换复合各写各的，互相之间没有逐项印证的对照；
朴素比较次数与更省的做法之间没有规模对照，省了多少也拿不出数字；
空排列、单元素、单位排列、完全逆序、含重复、自环、非法排列这些边界
只能靠肉眼去猜，异常口径也散在各处。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_perm.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
