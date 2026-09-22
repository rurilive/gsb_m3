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

from fixedpt import HALF_EVEN
bank = Domain(bits=64, scale=2, rounding=HALF_EVEN)
bank.div(bank.parse("2.505"), Fixed(1, 0), out_scale=2)  # 2.50，半靠偶数
Domain(bits=64, scale=6, overflow="saturate")            # 越界夹到端点
Domain(bits=64, scale=6, overflow="wrap")                 # 二补码回绕
d.text(d.parse("1.500e3"))                                # "1500"
```

## 现有能力

- `fixedpt/number.py`：`Fixed`，不可变定标小数，`unscaled` 与 `scale` 两个读数口，
  `+` `-` 跨 scale 对齐后精确计算，`*` `/` 与 `rescaled` 落到目标 scale 时低位
  朝零截断，比较与 hash 跨 scale 一致
- `fixedpt/domain.py`：`Domain`，账目精度 `scale`、定标整数位宽 `bits`、溢出策略
  `overflow`（`raise`/`wrap`/`saturate`，默认安全档 `raise`）与舍入模式
  `rounding`（`trunc`/`half_even`/`up`/`floor`/`ceil`，默认 `trunc`）。
  `add`/`sub` 与乘除结果都过 `fit` 收口；`mul`/`div` 先按模式定标再收口，
  模式可逐次调用覆盖。`parse` 认普通小数与科学计数法、多余零，超长小数按
  模式舍入；`text` 出去掉多余零的规范文本，来回稳定
- `fixedpt/rounding.py`：五种模式的整数除法 `div_round`、降精度 `rescale`，
  以及朝零截断的 `div_trunc`，乘除定标都走它
- `fixedpt/ledger.py`：`total_of` 累加、`apply_rate` 计息、`split` 分账（余数按最小
  单位摊给头几份，各份之和与总额一分不差）、`reconcile` 对账
- `fixedpt/errors.py`：`FixedPointError` 与 `ParseError`、`DomainOverflow`

## 约束

核心只用标准库，`fractions` 只允许在测试里当参考实现；`tests/` 下
`test_number.py`、`test_domain.py`、`test_ledger.py` 为基线，一字不改。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
