"""InMemoryNetwork 的行为基线。"""

import random
import unittest

from membersim.clock import SimClock
from membersim.network import InMemoryNetwork


class ScriptRng:
    """按剧本发延迟的随机源，把乱序写死在测试里。"""

    def __init__(self, delays):
        self.delays = list(delays)

    def random(self):
        return 1.0

    def randint(self, low, high):
        return self.delays.pop(0)


class TestBasicDelivery(unittest.TestCase):
    def setUp(self):
        self.clock = SimClock()
        self.net = InMemoryNetwork(self.clock)

    def test_message_arrives_after_delay(self):
        self.assertTrue(self.net.send("a", "b", "hi"))
        self.assertEqual(self.net.deliver_due(), [])
        self.clock.advance(1)
        msgs = self.net.deliver_due()
        self.assertEqual(len(msgs), 1)
        self.assertEqual((msgs[0].src, msgs[0].dst, msgs[0].payload), ("a", "b", "hi"))

    def test_message_delivered_once(self):
        self.net.send("a", "b", "hi")
        self.clock.advance(2)
        self.assertEqual(len(self.net.deliver_due()), 1)
        self.assertEqual(self.net.deliver_due(), [])

    def test_inflight_and_sent_by(self):
        self.net.send("a", "b", 1)
        self.assertEqual(self.net.inflight(), 1)
        self.assertEqual(self.net.sent_by("a"), 1)
        self.assertEqual(self.net.sent_by("b"), 0)
        self.clock.advance(1)
        self.net.deliver_due()
        self.assertEqual(self.net.inflight(), 0)
        self.assertEqual(self.net.stats["delivered"], 1)

    def test_no_loss_by_default(self):
        for _ in range(20):
            self.assertTrue(self.net.send("a", "b", "x"))
        self.assertEqual(self.net.stats["dropped"], 0)


class TestDelayAndOrder(unittest.TestCase):
    def test_a_slow_message_can_arrive_after_a_later_one(self):
        clock = SimClock()
        net = InMemoryNetwork(clock, rng=ScriptRng([3, 1]))
        net.send("a", "b", "old")
        clock.advance(1)
        net.send("a", "b", "new")
        clock.advance(1)
        self.assertEqual([m.payload for m in net.deliver_due()], ["new"])
        clock.advance(1)
        self.assertEqual([m.payload for m in net.deliver_due()], ["old"])

    def test_loss_is_deterministic_per_seed(self):
        def dropped(seed):
            clock = SimClock()
            net = InMemoryNetwork(clock, rng=random.Random(seed), loss=0.5)
            for i in range(10):
                net.send("a", "b", i)
            return net.stats["dropped"]

        self.assertEqual(dropped(7), dropped(7))

    def test_bad_parameters_rejected(self):
        clock = SimClock()
        with self.assertRaises(ValueError):
            InMemoryNetwork(clock, max_delay=0)
        with self.assertRaises(ValueError):
            InMemoryNetwork(clock, min_delay=2, max_delay=1)
        with self.assertRaises(ValueError):
            InMemoryNetwork(clock, loss=1.0)


class TestPartition(unittest.TestCase):
    def setUp(self):
        self.clock = SimClock()
        self.net = InMemoryNetwork(self.clock)

    def test_cross_group_send_is_dropped(self):
        self.net.partition(["a"], ["b", "c"])
        self.assertFalse(self.net.send("a", "b", "x"))
        self.assertEqual(self.net.stats["dropped"], 1)

    def test_same_group_still_works(self):
        self.net.partition(["a"], ["b", "c"])
        self.assertTrue(self.net.send("b", "c", "x"))

    def test_unknown_node_can_still_reach_both_sides(self):
        self.net.partition(["a"], ["b"])
        self.assertTrue(self.net.send("a", "z", "x"))
        self.assertTrue(self.net.send("z", "b", "x"))

    def test_message_due_during_partition_is_dropped(self):
        self.net.send("a", "b", "x")
        self.net.partition(["a"], ["b"])
        self.clock.advance(1)
        self.assertEqual(self.net.deliver_due(), [])
        self.assertEqual(self.net.stats["dropped"], 1)

    def test_heal_restores_delivery(self):
        self.net.partition(["a"], ["b"])
        self.net.heal()
        self.assertTrue(self.net.send("a", "b", "x"))
        self.clock.advance(1)
        self.assertEqual(len(self.net.deliver_due()), 1)


if __name__ == "__main__":
    unittest.main()
