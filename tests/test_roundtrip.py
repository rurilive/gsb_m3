"""随机对象树：编解码再编码字节不变，解码值与原树相等。

同一份数据在哪台机器上编出的字节都必须一样，这里用固定种子的随机
树覆盖各类型组合，再编码字节不变即规范形稳定；字段表还单独验证
编码结果与插入顺序无关。
"""

import math
import random
import struct
import unittest

from packwire import decode, encode


def random_tree(rng, depth=0):
    kinds = ["int", "float", "str", "bytes"]
    if depth < 5:
        kinds += ["list", "dict"]
    kind = rng.choice(kinds)
    if kind == "int":
        return rng.choice([
            0, 1, 23, 24, 255, 256, 65535, 65536,
            (1 << 32) - 1, 1 << 32, (1 << 64) - 1,
            -1, -24, -25, -256, -(1 << 64),
            rng.getrandbits(64), -1 - rng.getrandbits(64),
            rng.randint(-1000, 1000),
        ])
    if kind == "float":
        bits = rng.getrandbits(64)
        return rng.choice([
            0.0, -0.0, 0.5, 1.5, 65504.0, 100000.0, 1e300, 0.1,
            float("inf"), float("-inf"),
            struct.unpack(">d", bits.to_bytes(8, "big"))[0],
        ])
    if kind == "str":
        return "".join(rng.choice("abzé加速卡\u2022~") for _ in range(rng.randint(0, 30)))
    if kind == "bytes":
        return bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 40)))
    if kind == "list":
        return [random_tree(rng, depth + 1) for _ in range(rng.randint(0, 5))]
    keys = set()
    while len(keys) < rng.randint(0, 5):
        keys.add("k%d" % rng.randint(0, 999))
    return {key: random_tree(rng, depth + 1) for key in keys}


def trees_equal(left, right):
    if isinstance(left, float) and isinstance(right, float):
        if math.isnan(left) and math.isnan(right):
            return True
        return left == right and math.copysign(1.0, left) == math.copysign(1.0, right)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            trees_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return (left.keys() == right.keys()
                and all(trees_equal(left[k], right[k]) for k in left))
    return type(left) is type(right) and left == right


class RandomTreeTests(unittest.TestCase):
    def test_random_trees_round_trip_byte_stable(self):
        rng = random.Random(20260921)
        for i in range(300):
            tree = random_tree(rng)
            blob = encode(tree)
            with self.subTest(tree=i):
                got = decode(blob)
                self.assertTrue(trees_equal(got, tree))
                self.assertEqual(encode(got), blob)

    def test_encode_is_deterministic_across_calls(self):
        rng = random.Random(7)
        for i in range(50):
            tree = random_tree(rng)
            with self.subTest(tree=i):
                self.assertEqual(encode(tree), encode(tree))


class MapDeterminismTests(unittest.TestCase):
    def test_map_encoding_independent_of_insertion_order(self):
        keys = ["alpha", "b", "cc", "z", "payload", "id", "x" * 30]
        base = {key: index for index, key in enumerate(keys)}
        reference = encode(base)
        rng = random.Random(11)
        for _ in range(30):
            shuffled = keys[:]
            rng.shuffle(shuffled)
            with self.subTest(order=shuffled):
                self.assertEqual(encode({k: base[k] for k in shuffled}), reference)

    def test_nested_mixed_tree_matches_reference_hex(self):
        value = {"id": "gpu-01", "tags": ["a", "b"], "load": 0.5, "up": True}
        self.assertEqual(
            encode(value).hex(),
            "a4626964666770752d303162757001646c6f6164d9380064746167738261616162")


if __name__ == "__main__":
    unittest.main()
