"""Ledger 现有行为的锁定测试：收支流水、余额与金额校验。

只覆盖当前实现已经具备的能力。科目表、借贷平衡、多级汇总、期间结账、
试算平衡、对账与冲销都还没有，新增行为另建测试文件，不改动本文件。
"""

import unittest

from ledgerbook import InvalidAmount, Ledger


class TestRecording(unittest.TestCase):
    def test_record_in_returns_flow(self):
        ledger = Ledger()
        flow = ledger.record_in(100)
        self.assertEqual(flow.kind, "in")
        self.assertEqual(flow.amount, 100)
        self.assertEqual(flow.note, "")

    def test_record_out_returns_flow(self):
        ledger = Ledger()
        flow = ledger.record_out(250, note="采购")
        self.assertEqual(flow.kind, "out")
        self.assertEqual(flow.amount, 250)
        self.assertEqual(flow.note, "采购")

    def test_flows_keep_insertion_order(self):
        ledger = Ledger()
        ledger.record_in(100)
        ledger.record_out(30)
        ledger.record_in(5)
        self.assertEqual([f.kind for f in ledger.flows()], ["in", "out", "in"])

    def test_flows_returns_a_copy(self):
        ledger = Ledger()
        ledger.record_in(100)
        snapshot = ledger.flows()
        snapshot.clear()
        self.assertEqual(len(ledger.flows()), 1)

    def test_empty_ledger_has_no_flows(self):
        self.assertEqual(Ledger().flows(), [])


class TestTotals(unittest.TestCase):
    def test_total_in_sums_only_income(self):
        ledger = Ledger()
        ledger.record_in(100)
        ledger.record_in(50)
        ledger.record_out(999)
        self.assertEqual(ledger.total_in(), 150)

    def test_total_out_sums_only_expense(self):
        ledger = Ledger()
        ledger.record_in(100)
        ledger.record_out(30)
        ledger.record_out(20)
        self.assertEqual(ledger.total_out(), 50)

    def test_balance_is_income_minus_expense(self):
        ledger = Ledger()
        ledger.record_in(100)
        ledger.record_out(30)
        self.assertEqual(ledger.balance(), 70)

    def test_balance_can_be_negative(self):
        ledger = Ledger()
        ledger.record_out(30)
        self.assertEqual(ledger.balance(), -30)

    def test_empty_ledger_balances_to_zero(self):
        self.assertEqual(Ledger().balance(), 0)


class TestReset(unittest.TestCase):
    def test_reset_clears_flows(self):
        ledger = Ledger()
        ledger.record_in(100)
        ledger.reset()
        self.assertEqual(ledger.flows(), [])
        self.assertEqual(ledger.balance(), 0)


class TestAmountValidation(unittest.TestCase):
    def test_zero_in_rejected(self):
        with self.assertRaises(InvalidAmount):
            Ledger().record_in(0)

    def test_zero_out_rejected(self):
        with self.assertRaises(InvalidAmount):
            Ledger().record_out(0)

    def test_negative_amount_rejected(self):
        with self.assertRaises(InvalidAmount):
            Ledger().record_in(-1)

    def test_float_amount_rejected(self):
        with self.assertRaises(InvalidAmount):
            Ledger().record_in(1.5)

    def test_bool_amount_rejected(self):
        with self.assertRaises(InvalidAmount):
            Ledger().record_out(True)

    def test_string_amount_rejected(self):
        with self.assertRaises(InvalidAmount):
            Ledger().record_in("100")

    def test_rejected_flow_is_not_recorded(self):
        ledger = Ledger()
        try:
            ledger.record_in(0)
        except InvalidAmount:
            pass
        self.assertEqual(ledger.flows(), [])


if __name__ == "__main__":
    unittest.main()
