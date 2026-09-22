"""fixedpt 现状演示。

第一段：定标值怎么存、怎么算，跨 scale 的加减与比较是精确的。
第二段：清算例行，计息与分账，分账保证一分不差。
第三段：五种舍入模式下的乘除，以及显式可配的越界策略。
第四段：文本互转，普通小数、科学计数法与多余零都认。
"""

from fixedpt import (
    CEIL,
    FLOOR,
    HALF_EVEN,
    TRUNC,
    UP,
    Domain,
    DomainOverflow,
    Fixed,
    ledger,
)


def main():
    d = Domain(bits=64, scale=6)

    print("=== 定标值 ===")
    amount = d.fixed(120_500_000)      # 120.50
    rate = Fixed(33_333, 6)            # 0.033333
    print("amount =", amount, " rate =", rate)
    print("加一笔 1.50:", d.add(amount, d.fixed(1_500_000)))
    print("计息落定标:", d.mul(amount, rate, 6))
    print("跨 scale 比较:", Fixed(12, 1) == Fixed(120, 2), amount > d.fixed(1))

    print("=== 计息与分账 ===")
    interest = ledger.apply_rate(d, amount, rate, out_scale=6)
    print("interest =", interest)
    parts = ledger.split(d, d.fixed(10_000_000), 3)   # 10.00 摊三份
    print("分账:", [p.unscaled for p in parts],
          " 合计等于总额:", ledger.total_of(d, parts) == d.fixed(10_000_000))
    print("对账差:",
          ledger.reconcile(d, [d.fixed(1_200_000), interest], d.fixed(1_204_000)))

    print("=== 域宽与溢出 ===")
    small = Domain(bits=8, scale=0)
    print("bits=8 的范围:", small.min_unscaled, "到", small.max_unscaled)
    try:
        small.add(Fixed(100, 0), Fixed(40, 0))
    except DomainOverflow as exc:
        print("add 越界:", exc)
    print("mul 默认安全档也收口，越界同样抛:", end=" ")
    try:
        small.mul(Fixed(100, 0), Fixed(40, 0))
    except DomainOverflow as exc:
        print(type(exc).__name__)

    print("=== 舍入模式 ===")
    bank = Domain(bits=64, scale=2, rounding=HALF_EVEN)
    # 12.345 / 10 = 1.2345，落到分位正好在半上
    for mode in (TRUNC, HALF_EVEN, UP, FLOOR, CEIL):
        got = bank.div(Fixed(12345, 3), Fixed(10, 0), rounding=mode)
        neg = bank.div(Fixed(-12345, 3), Fixed(10, 0), rounding=mode)
        print("模式 %-9s 正:" % mode, bank.text(got), " 负:", bank.text(neg))
    print("银行家舍入看奇偶:", bank.text(bank.parse("1.235")),
          bank.text(bank.parse("1.245")))

    print("=== 越界策略 ===")
    sat = Domain(bits=8, scale=0, overflow="saturate")
    wrap = Domain(bits=8, scale=0, overflow="wrap")
    print("saturate 100*40:", sat.mul(Fixed(100, 0), Fixed(40, 0)),
          " -100*40:", sat.mul(Fixed(-100, 0), Fixed(40, 0)))
    print("wrap 100*40:", wrap.mul(Fixed(100, 0), Fixed(40, 0)),
          " 300 回绕:", wrap.fit(300), " -300 回绕:", wrap.fit(-300))

    print("=== 文本互转 ===")
    d6 = Domain(bits=64, scale=6, rounding=HALF_EVEN)
    for text in ("1.500", "001.5", "1.5e3", "1E-6", "-.0000025", "1200"):
        value = d6.parse(text)
        print("%-12s -> unscaled=%-12d -> text=%s"
              % (text, value.unscaled, d6.text(value)))
    value = d6.fixed(10_500_000)
    print("来回倒:", d6.text(value), "->", d6.parse(d6.text(value)))


if __name__ == "__main__":
    main()
