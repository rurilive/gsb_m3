# diffcons

差分约束系统的可行解求解器，纯标准库，无外部依赖。

## 现状

`diffcons/system.py` 提供 `DifferenceSystem`：

- `add_le(lhs, rhs, bound)`：登记 x[lhs] 减 x[rhs] 不超过 bound 的约束
- `add_eq(lhs, rhs, bound)`：登记 x[lhs] 减 x[rhs] 恰好等于 bound 的约束
- `constraints()` / `variables()` / `len()`：登记内容的查询
- `solve()`：对全部约束反复扫描、逐轮松弛每个变量，直到某轮不再变化，返回一组可行赋值
- `has_solution()`：按同一套反复松弛判断有没有可行解
- `diff_max(a, b)`：照同一套松弛求 x[a] 减 x[b] 的最大值，无上界返回 None
- `check_assignment(value)`：逐一核对赋值，返回第一条被违反的约束，全满足返回 None

变量名非空字符串校验、上界整数校验与赋值合法性校验失败抛 `ConstraintError`，
反复松弛不收敛即判负环抛 `Infeasible`，它们都继承 `DiffError`。

## 问题

朴素做法每轮都要把每条约束都看一遍，轮数又随变量数增长，变量或约束一多就明显变慢；
而没有把约束建成图，也拿不到两点最短路的先进口径。能力上也还缺：把不等式与等式混合后
成体系地求解、证明某条最大差值确实同时满足全部约束、以及明确标出赋值违反的是哪一条。

## 目标

见任务描述。约束：

- `tests/test_system.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 差分约束求解与无解判定演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
