# fixedpt

清算引擎的定点小数库，纯标准库，无外部依赖：小数按 10 的幂缩放成整数存放，
加减与比较跨精度精确，乘除按目标精度定标。

## 用法

```python
from fixedpt import Domain, Fixed, ledger

d = Domain(bits=64, scale=6)       # 账目精度到微，定标整数 64 位
amount = d.fixed(10_500_000)       # 10.50
rate = Fixed(250_000, 6)           # 0.250000
d.mul(amount, rate, out_scale=2)   # 计息，低位朝零截断
ledger.split(d, amount, 3)         # 摊三份，各份之和一分不差
```

## 现有能力

- `fixedpt/number.py`：`Fixed`，不可变定标小数，`unscaled` 与 `scale` 两个读数口，
  `+` `-` 跨 scale 对齐后精确计算，`*` `/` 与 `rescaled` 落到目标 scale 时低位
  朝零截断，比较与 hash 跨 scale 一致
- `fixedpt/domain.py`：`Domain`，账目精度 `scale`、定标整数位宽 `bits`、溢出策略
  `overflow`（现在只认 `raise`）。`add` 与 `sub` 的结果过 `fit` 收口，越界抛
  `DomainOverflow`；`mul` 与 `div` 只是转发到 `Fixed` 的同名方法
- `fixedpt/rounding.py`：`div_trunc`，结果朝零截断的整数除法，乘除降精度都走它
- `fixedpt/ledger.py`：`total_of` 累加、`apply_rate` 计息、`split` 分账（余数按最小
  单位摊给头几份，各份之和与总额一分不差）、`reconcile` 对账
- `fixedpt/errors.py`：`FixedPointError` 与 `ParseError`、`DomainOverflow`

## 现状

- 乘除的定标只有一种裁法，没法按模式舍入
- `mul` 与 `div` 的结果不收口，越界值原样留在结果里，也没有回绕或饱和可选
- 文本互转还没有：解析与格式化都缺

## 目标

见任务描述。约束：现有接口与 `tests/` 的基线行为保持不变，核心只用标准库，
`fractions` 只允许在测试里当参考实现。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
