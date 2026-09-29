"""Observable 现有行为的锁定测试：取值、设值通知、订阅与退订。

只覆盖当前已有的朴素可观察值，后面新增的 signal、computed、批处理、
effect 与循环检测另开测试文件。
"""

import unittest

from signalbox import Observable


class TestReadWrite(unittest.TestCase):
    def test_initial_value(self):
        self.assertEqual(Observable(3).get(), 3)

    def test_default_initial_is_none(self):
        self.assertIsNone(Observable().get())

    def test_set_updates_value(self):
        obs = Observable(1)
        obs.set(2)
        self.assertEqual(obs.get(), 2)

    def test_set_returns_none(self):
        obs = Observable(1)
        self.assertIsNone(obs.set(2))

    def test_value_can_be_any_object(self):
        marker = object()
        obs = Observable()
        obs.set(marker)
        self.assertIs(obs.get(), marker)

    def test_version_starts_at_zero(self):
        self.assertEqual(Observable(1).version, 0)

    def test_version_increments_on_set(self):
        obs = Observable(1)
        obs.set(2)
        obs.set(3)
        self.assertEqual(obs.version, 2)


class TestNotification(unittest.TestCase):
    def test_subscriber_called_on_set(self):
        obs = Observable(1)
        seen = []
        obs.subscribe(lambda o, v: seen.append(v))
        obs.set(2)
        self.assertEqual(seen, [2])

    def test_subscriber_receives_observable_and_value(self):
        obs = Observable(1)
        seen = []
        obs.subscribe(lambda o, v: seen.append((o, v)))
        obs.set(9)
        self.assertEqual(seen, [(obs, 9)])

    def test_subscribers_called_in_registration_order(self):
        obs = Observable(0)
        order = []
        obs.subscribe(lambda o, v: order.append("a"))
        obs.subscribe(lambda o, v: order.append("b"))
        obs.set(1)
        self.assertEqual(order, ["a", "b"])

    def test_multiple_subscribers_all_called(self):
        obs = Observable(0)
        seen = []
        obs.subscribe(lambda o, v: seen.append("a"))
        obs.subscribe(lambda o, v: seen.append("b"))
        obs.set(1)
        self.assertEqual(seen, ["a", "b"])

    def test_no_subscribers_is_fine(self):
        obs = Observable(1)
        obs.set(2)
        self.assertEqual(obs.get(), 2)

    def test_subscribe_returns_unsubscribe(self):
        obs = Observable(1)
        seen = []
        unsub = obs.subscribe(lambda o, v: seen.append(v))
        unsub()
        obs.set(2)
        self.assertEqual(seen, [])

    def test_unsubscribe_by_reference(self):
        obs = Observable(1)
        seen = []
        fn = lambda o, v: seen.append(v)
        obs.subscribe(fn)
        self.assertTrue(obs.unsubscribe(fn))
        obs.set(2)
        self.assertEqual(seen, [])

    def test_unsubscribe_unknown_returns_false(self):
        obs = Observable(1)
        self.assertFalse(obs.unsubscribe(lambda o, v: None))

    def test_unsubscribe_is_idempotent(self):
        obs = Observable(1)
        fn = lambda o, v: None
        obs.subscribe(fn)
        self.assertTrue(obs.unsubscribe(fn))
        self.assertFalse(obs.unsubscribe(fn))

    def test_subscribers_snapshot(self):
        obs = Observable(1)
        fn = lambda o, v: None
        obs.subscribe(fn)
        self.assertEqual(obs.subscribers(), [fn])

    def test_subscribe_rejects_non_callable(self):
        obs = Observable(1)
        with self.assertRaises(TypeError):
            obs.subscribe(42)

    def test_set_notifies_after_value_is_visible(self):
        obs = Observable(1)
        seen = []
        obs.subscribe(lambda o, v: seen.append(o.get()))
        obs.set(5)
        self.assertEqual(seen, [5])

    def test_subscriber_exception_propagates(self):
        obs = Observable(1)

        def boom(o, v):
            raise RuntimeError("boom")

        obs.subscribe(boom)
        with self.assertRaises(RuntimeError):
            obs.set(2)
        self.assertEqual(obs.get(), 2)


if __name__ == "__main__":
    unittest.main()