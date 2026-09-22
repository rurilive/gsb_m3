import unittest

from qsketch import EmptySetError, ShardSet, SketchError


class AddTest(unittest.TestCase):
    def test_add_returns_shard_count(self):
        shards = ShardSet()
        self.assertEqual(shards.add("a", 1), 1)
        self.assertEqual(shards.add("a", 2), 2)
        self.assertEqual(shards.add("b", 3), 1)

    def test_shard_name_must_be_str(self):
        shards = ShardSet()
        for bad in (1, None, ("a",)):
            with self.assertRaises(SketchError):
                shards.add(bad, 1)
        self.assertEqual(shards.names(), [])

    def test_names_sorted(self):
        shards = ShardSet()
        for name in ("c", "a", "b"):
            shards.add(name, 1)
        self.assertEqual(shards.names(), ["a", "b", "c"])


class ReadTest(unittest.TestCase):
    def test_count_total_and_per_shard(self):
        shards = ShardSet()
        shards.add("a", 1)
        shards.add("a", 2)
        shards.add("b", 3)
        self.assertEqual(shards.count(), 3)
        self.assertEqual(shards.count("a"), 2)
        self.assertEqual(shards.count("b"), 1)

    def test_count_unknown_shard(self):
        with self.assertRaises(SketchError):
            ShardSet().count("nope")

    def test_values_concatenate_in_name_order(self):
        shards = ShardSet()
        shards.add("b", 3)
        shards.add("a", 1)
        shards.add("a", 2)
        self.assertEqual(shards.values(), [1.0, 2.0, 3.0])
        self.assertEqual(shards.values("a"), [1.0, 2.0])

    def test_values_unknown_shard(self):
        with self.assertRaises(SketchError):
            ShardSet().values("nope")

    def test_quantile_matches_full_sort(self):
        shards = ShardSet()
        for name, values in (("a", [7, 1]), ("b", [5, 3]), ("c", [9])):
            for value in values:
                shards.add(name, value)
        ordered = sorted([7, 1, 5, 3, 9])
        for q in (0.0, 0.25, 0.5, 0.75, 1.0):
            position = q * (len(ordered) - 1)
            lo = int(position)
            hi = min(lo + 1, len(ordered) - 1)
            frac = position - lo
            expected = ordered[lo] * (1 - frac) + ordered[hi] * frac
            self.assertAlmostEqual(shards.quantile(q), expected)

    def test_quantile_empty_raises(self):
        with self.assertRaises(EmptySetError):
            ShardSet().quantile(0.5)


class MergeTest(unittest.TestCase):
    def test_merge_matches_full(self):
        a = ShardSet()
        a.add("x", 1)
        a.add("y", 2)
        b = ShardSet()
        b.add("x", 3)
        b.add("z", 4)
        full = ShardSet()
        for name, value in (("x", 1), ("y", 2), ("x", 3), ("z", 4)):
            full.add(name, value)
        merged = a.merge(b)
        self.assertEqual(merged.names(), ["x", "y", "z"])
        self.assertEqual(merged.count("x"), 2)
        self.assertEqual(merged.count(), 4)
        for q in (0.0, 0.5, 0.9, 1.0):
            self.assertEqual(merged.quantile(q), full.quantile(q))

    def test_merge_leaves_inputs_alone(self):
        a = ShardSet()
        a.add("x", 1)
        b = ShardSet()
        b.add("x", 2)
        merged = a.merge(b)
        self.assertEqual(a.values(), [1.0])
        self.assertEqual(b.values(), [2.0])
        self.assertEqual(merged.values(), [1.0, 2.0])

    def test_merge_type_checked(self):
        with self.assertRaises(SketchError):
            ShardSet().merge({})


if __name__ == "__main__":
    unittest.main()
