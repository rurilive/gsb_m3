"""ledgerbook 现状演示。

第一段：收支流水的记录、合计与余额，看一遍金额校验与错误。
第二段：预留的借贷平衡交易与试算平衡演示位子（见文末注释）。
"""

from ledgerbook import InvalidAmount, Ledger


def main():
    print("=== 收支流水账 ===")
    ledger = Ledger()
    ledger.record_in(100_00, note="销售收款")
    ledger.record_out(30_00, note="采购付款")
    ledger.record_in(5_50, note="退款")
    print("  流水条数:", len(ledger.flows()))
    print("  收入合计（分）:", ledger.total_in())
    print("  支出合计（分）:", ledger.total_out())
    print("  余额（分）:", ledger.balance())
    print("  余额元:", "%.2f" % (ledger.balance() / 100))
    try:
        ledger.record_in(0)
    except InvalidAmount as exc:
        print("  金额为零被拒:", exc)
    try:
        ledger.record_out(1.5)
    except InvalidAmount as exc:
        print("  金额为浮点被拒:", exc)
    ledger.reset()
    print("  重置后流水条数:", len(ledger.flows()))

    # TODO(借贷平衡与试算平衡): 复式记账分录、科目表、多级汇总、期间结账、
    # 试算平衡、对账与冲销都补齐后，在这里加一段演示：
    # 用一张科目表提交一笔借贷平衡的交易，打印各分录与按科目汇总的余额；
    # 提交一笔借贷不平衡的交易，打印被拒绝的提示；
    # 打印 trial_balance 的两个合计，确认借贷相等.


if __name__ == "__main__":
    main()