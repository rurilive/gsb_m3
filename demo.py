"""fixedpt 现状演示。

第一段：定标值怎么存、怎么算，跨 scale 的加减与比较是精确的。
第二段：清算例行，计息与分账，分账保证一分不差。
第三段：域宽与三种溢出策略。
第四段：五种舍入模式下的乘除。
第五段：文本互转，科学计数法与超长小数都走得通。
"""

from fixedpt import Domain, DomainOverflow, Fixed, ledger


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
    try:
        small.mul(Fixed(100, 0), Fixed(40, 0))
    except DomainOverflow as exc:
        print("mul 越界(raise):", exc)
    sat = Domain(bits=8, scale=0, overflow="saturate")
    print("mul 饱和:", sat.mul(Fixed(100, 0), Fixed(40, 0)))
    wrap = Domain(bits=8, scale=0, overflow="wrap")
    print("mul 回绕:", wrap.mul(Fixed(100, 0), Fixed(40, 0)))

    print("=== 舍入模式 ===")
    for mode in ("truncate", "away", "floor", "ceil", "half_even"):
        dm = Domain(bits=64, scale=0, rounding=mode)
        pos = dm.mul(Fixed(25, 1), Fixed(1, 0), out_scale=0)   # 2.5
        neg = dm.mul(Fixed(-25, 1), Fixed(1, 0), out_scale=0)  # -2.5
        print("%-9s 2.5 -> %s  -2.5 -> %s" % (mode, pos.unscaled, neg.unscaled))

    print("=== 文本互转 ===")
    d2 = Domain(bits=64, scale=2, rounding="half_even")
    for raw in ("12.3400", "1.2e3", "-.5", "1.005", "3.14159265"):
        value = d2.parse(raw)
        print("%-12s -> %-18s -> %s" % (raw, value, d2.text(value)))


if __name__ == "__main__":
    main()
