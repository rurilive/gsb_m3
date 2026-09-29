"""SnowflakeGenerator 现有行为的锁定测试。"""

import unittest

from idkit.snowflake import (
    EPOCH_MS,
    MAX_NODE,
    MAX_SEQUENCE,
    NODE_BITS,
    SEQUENCE_BITS,
    ClockBackwards,
    SequenceExhausted,
    SnowflakeGenerator,
)


class FixedClock:
    """可手动推进的时钟。"""

    def __init__(self, start):
        self.value = start

    def __call__(self):
        return self.value

    def set(self, value):
        self.value = value


class TestConstruction(unittest.TestCase):
    def test_default_node_is_zero(self):
        self.assertEqual(SnowflakeGenerator().node_id, 0)

    def test_node_id_stored(self):
        self.assertEqual(SnowflakeGenerator(node_id=5).node_id, 5)

    def test_node_id_out_of_range(self):
        with self.assertRaises(ValueError):
            SnowflakeGenerator(node_id=-1)
        with self.assertRaises(ValueError):
            SnowflakeGenerator(node_id=MAX_NODE + 1)

    def test_node_id_type(self):
        with self.assertRaises(TypeError):
            SnowflakeGenerator(node_id="1")

    def test_last_timestamp_before_generation(self):
        self.assertEqual(SnowflakeGenerator().last_timestamp, -1)


class TestNextId(unittest.TestCase):
    def test_sequence_increments_within_same_ms(self):
        g = SnowflakeGenerator(node_id=3)
        first = g.next_id(EPOCH_MS + 1000)
        second = g.next_id(EPOCH_MS + 1000)
        self.assertEqual(second - first, 1)
        self.assertEqual(g.parse(second)[2], 1)

    def test_sequence_resets_when_time_advances(self):
        g = SnowflakeGenerator(node_id=3)
        g.next_id(EPOCH_MS + 1000)
        g.next_id(EPOCH_MS + 1000)
        moved = g.next_id(EPOCH_MS + 1001)
        self.assertEqual(g.parse(moved)[2], 0)
        self.assertEqual(g.parse(moved)[0], EPOCH_MS + 1001)

    def test_ids_are_monotonic(self):
        g = SnowflakeGenerator(node_id=7)
        ids = [g.next_id(EPOCH_MS + 2000) for _ in range(50)]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(set(ids)), len(ids))

    def test_sequence_exhaustion_raises(self):
        g = SnowflakeGenerator(node_id=0)
        g.next_id(EPOCH_MS + 3000)
        for _ in range(MAX_SEQUENCE):
            g.next_id(EPOCH_MS + 3000)
        with self.assertRaises(SequenceExhausted):
            g.next_id(EPOCH_MS + 3000)

    def test_backwards_clock_raises(self):
        g = SnowflakeGenerator(node_id=0)
        g.next_id(EPOCH_MS + 5000)
        with self.assertRaises(ClockBackwards):
            g.next_id(EPOCH_MS + 4999)

    def test_clock_injected(self):
        clk = FixedClock(EPOCH_MS + 8000)
        g = SnowflakeGenerator(node_id=1, clock=clk)
        ts, node, _ = g.parse(g.next_id())
        self.assertEqual(ts, EPOCH_MS + 8000)
        self.assertEqual(node, 1)
        clk.set(EPOCH_MS + 8001)
        self.assertEqual(g.parse(g.next_id())[0], EPOCH_MS + 8001)

    def test_now_ms_type(self):
        g = SnowflakeGenerator(node_id=0)
        with self.assertRaises(TypeError):
            g.next_id("100")


class TestParse(unittest.TestCase):
    def test_roundtrip(self):
        g = SnowflakeGenerator(node_id=9)
        value = g.next_id(EPOCH_MS + 4000)
        ts, node, seq = g.parse(value)
        self.assertEqual(ts, EPOCH_MS + 4000)
        self.assertEqual(node, 9)
        self.assertEqual(seq, 0)

    def test_parse_rejects_negative(self):
        with self.assertRaises(ValueError):
            SnowflakeGenerator().parse(-1)

    def test_parse_rejects_non_int(self):
        with self.assertRaises(TypeError):
            SnowflakeGenerator().parse("42")

    def test_parse_reads_back_node_field(self):
        g = SnowflakeGenerator(node_id=4)
        value = g.next_id(EPOCH_MS + 6000)
        self.assertEqual(g.parse(value)[1], 4)

    def test_bit_widths(self):
        self.assertEqual(SEQUENCE_BITS, 12)
        self.assertEqual(NODE_BITS, 10)
        self.assertEqual(MAX_SEQUENCE, (1 << SEQUENCE_BITS) - 1)
        self.assertEqual(MAX_NODE, (1 << NODE_BITS) - 1)


if __name__ == "__main__":
    unittest.main()