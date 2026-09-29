"""orderbook 现有订单列表行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from orderbook.engine import Engine, Order


def build():
    e = Engine()
    return e


class TestOrderList(unittest.TestCase):
    def test_place_returns_order_id(self):
        e = build()
        self.assertEqual(e.place("alice", "buy", 100, 5), 1)
        self.assertEqual(e.place("bob", "sell", 101, 3), 2)

    def test_order_id_increases(self):
        e = build()
        a = e.place("alice", "buy", 100, 5)
        b = e.place("alice", "buy", 100, 5)
        c = e.place("bob", "sell", 101, 5)
        self.assertEqual((a, b, c), (1, 2, 3))

    def test_place_rejects_empty_account(self):
        e = build()
        with self.assertRaises(ValueError):
            e.place("", "buy", 100, 5)

    def test_place_rejects_non_str_account(self):
        e = build()
        with self.assertRaises(ValueError):
            e.place(7, "buy", 100, 5)

    def test_place_rejects_bad_side(self):
        e = build()
        with self.assertRaises(ValueError):
            e.place("alice", "hold", 100, 5)

    def test_place_rejects_bad_price(self):
        e = build()
        with self.assertRaises(ValueError):
            e.place("alice", "buy", 0, 5)
        with self.assertRaises(ValueError):
            e.place("alice", "buy", -1, 5)
        with self.assertRaises(ValueError):
            e.place("alice", "buy", 100.0, 5)
        with self.assertRaises(ValueError):
            e.place("alice", "buy", True, 5)

    def test_place_rejects_bad_qty(self):
        e = build()
        with self.assertRaises(ValueError):
            e.place("alice", "buy", 100, 0)
        with self.assertRaises(ValueError):
            e.place("alice", "buy", 100, -3)
        with self.assertRaises(ValueError):
            e.place("alice", "buy", 100, "5")

    def test_open_orders_insertion_order(self):
        e = build()
        e.place("alice", "buy", 100, 5)
        e.place("bob", "sell", 101, 3)
        e.place("carol", "buy", 99, 2)
        ids = [o.order_id for o in e.open_orders()]
        self.assertEqual(ids, [1, 2, 3])

    def test_open_orders_returns_tuple(self):
        e = build()
        e.place("alice", "buy", 100, 5)
        self.assertIsInstance(e.open_orders(), tuple)

    def test_open_orders_fields(self):
        e = build()
        e.place("alice", "buy", 100, 5)
        o = e.open_orders()[0]
        self.assertIsInstance(o, Order)
        self.assertEqual(o.account, "alice")
        self.assertEqual(o.side, "buy")
        self.assertEqual(o.price, 100)
        self.assertEqual(o.qty, 5)

    def test_cancel_removes_order(self):
        e = build()
        oid = e.place("alice", "buy", 100, 5)
        e.place("bob", "sell", 101, 3)
        self.assertTrue(e.cancel(oid))
        self.assertEqual(len(e), 1)
        ids = [o.order_id for o in e.open_orders()]
        self.assertEqual(ids, [2])

    def test_cancel_missing_order(self):
        e = build()
        e.place("alice", "buy", 100, 5)
        with self.assertRaises(KeyError):
            e.cancel(999)

    def test_len_tracks_open_orders(self):
        e = build()
        self.assertEqual(len(e), 0)
        a = e.place("alice", "buy", 100, 5)
        e.place("bob", "sell", 101, 3)
        self.assertEqual(len(e), 2)
        e.cancel(a)
        self.assertEqual(len(e), 1)

    def test_depth_returns_side_in_order(self):
        e = build()
        e.place("alice", "buy", 100, 5)
        e.place("bob", "sell", 101, 3)
        e.place("carol", "buy", 99, 2)
        buys = [o.order_id for o in e.depth("buy")]
        sells = [o.order_id for o in e.depth("sell")]
        self.assertEqual(buys, [1, 3])
        self.assertEqual(sells, [2])

    def test_trades_empty(self):
        e = build()
        e.place("alice", "buy", 101, 5)
        e.place("bob", "sell", 100, 5)
        self.assertEqual(e.trades(), ())


if __name__ == "__main__":
    unittest.main()
