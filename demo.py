"""fixedpt 现状演示。

第一段：定标值怎么存、怎么算，跨 scale 的加减与比较是精确的。
第二段：清算例行，计息与分账，分账保证一分不差。
第三段：域宽和溢出策略现在的样子，以及留给舍入与文本互转的位子。
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
    print("mul 现在不收口:", small.mul(Fixed(100, 0), Fixed(40, 0)))

    # TODO(舍入与文本): 舍入模式、乘除定标收口、Domain.parse 与 Domain.text
    # 落地后，在这里补一段带模式的乘除和一张文本互转的表。


if __name__ == "__main__":
    main()
