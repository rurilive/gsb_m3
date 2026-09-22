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

bank = Domain(scale=2, rounding="half_even", overflow="saturate")
bank.parse("1.005")                # 超长小数按银行家舍入落定标
bank.text(bank.fixed(150))         # "1.5"
```

## 现有能力

- `fixedpt/number.py`：`Fixed`，不可变定标小数，`unscaled` 与 `scale` 两个读数口，
  `+` `-` 跨 scale 对齐后精确计算，`*` `/` 与 `rescaled` 落到目标 scale 时按
  指定的舍入模式裁低位（默认朝零截断），比较与 hash 跨 scale 一致
- `fixedpt/domain.py`：`Domain`，账目精度 `scale`、定标整数位宽 `bits`、溢出策略
  `overflow`（`raise` 抛 `DomainOverflow`、`saturate` 饱和到边界、`wrap` 按位宽
  回绕，默认 `raise`）与舍入模式 `rounding`（默认 `truncate`）。`add`、`sub`、
  `mul`、`div` 的结果都过 `fit` 收口；`parse` 与 `text` 负责文本互转，认科学
  计数法与多余的零，超长小数按域的舍入模式落定标，来回倒稳定
- `fixedpt/rounding.py`：`div_round` 按模式舍入的整数除法，五种模式：
  `truncate` 朝零、`away` 远离零、`floor` 向下、`ceil` 向上、`half_even`
  银行家舍入；`div_trunc` 是朝零截断的快捷写法
- `fixedpt/ledger.py`：`total_of` 累加、`apply_rate` 计息、`split` 分账（余数按最小
  单位摊给头几份，各份之和与总额一分不差）、`reconcile` 对账
- `fixedpt/errors.py`：`FixedPointError` 与 `ParseError`、`DomainOverflow`

## 测试

核心只用标准库；`fractions.Fraction` 在 `tests/test_property.py` 里当参考实现，
随机小数配随机运算序列逐一对拍（含负数），边界与极限值单独造，另有百万次
乘除的性能门槛（十五秒内）。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
