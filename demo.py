"""coinlib 现状演示。

第一段：浮点钱包的加减与余额，看一遍基线行为与浮点误差。
第二段：预留的定点货币演示位子（见文末注释）。
"""

from coinlib import Wallet


def main():
    print("=== 浮点钱包 ===")
    wallet = Wallet(100.0)
    print("  初始余额:", wallet.balance())
    wallet.deposit(20.0)
    wallet.withdraw(5.5)
    print("  存取后余额:", wallet.balance())
    print("  余额元:", "%.2f" % wallet.balance())

    drift = Wallet()
    drift.deposit(0.1)
    drift.deposit(0.2)
    print("  0.1 加 0.2 的余额:", repr(drift.balance()))
    print("  是否等于 0.3:", drift.balance() == 0.3)

    # TODO(精确货币改造): 定点货币、货币代码与舍入模式、配比分摊、汇率换算、
    # 格式化与解析都补齐后，在这里加一段演示：
    # 用最小单位整数构造一笔金额并往返读取，打印无损结果；
    # 对一笔金额按权重分摊给多方，打印各方份额与它们的合计，确认合计精确等于原额；
    # 对两个不同货币的金额做一次相加，打印被拒绝的提示.


if __name__ == "__main__":
    main()
