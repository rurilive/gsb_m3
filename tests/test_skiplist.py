"""skiplist 语义测试。

以 README.md「语义约定」为唯一行为定义，逐条锁定。
红用例上方注释写明「README 期望 / 实际发生」。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v
或直接：
    python3 tests/test_skiplist.py
"""

import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skiplist.skiplist import SkipList  # noqa: E402


class _Reference:
    """朴素参考实现：插入有序的 (key, value) 列表。

    - insert 恒追加一个副本；
    - remove 摘除插入最早的同键副本；
    - scan 按 key 非降序输出（sorted 稳定排序，同键保持插入先后）。
    """

    def __init__(self):
        self._items = []

    def insert(self, key, value):
        self._items.append((key, value))

    def remove(self, key):
        for idx, (k, _) in enumerate(self._items):
            if k == key:
                del self._items[idx]
                return True
        return False

    def find(self, key):
        for k, v in self._items:
            if k == key:
                return v
        return None

    def scan(self, lo=None, hi=None):
        ordered = sorted(self._items, key=lambda kv: kv[0])
        return [
            (k, v)
            for k, v in ordered
            if (lo is None or k >= lo) and (hi is None or k <= hi)
        ]

    def __len__(self):
        return len(self._items)


class TestInsertAndFind(unittest.TestCase):
    """README 第 1、3 条：insert / find / in。"""

    def test_find_returns_inserted_value(self):
        sl = SkipList(seed=7)
        sl.insert(10, "x")
        sl.insert(3, "y")
        self.assertEqual(sl.find(10), "x")
        self.assertEqual(sl.find(3), "y")

    def test_find_missing_returns_none(self):
        sl = SkipList(seed=7)
        sl.insert(10, "x")
        self.assertIsNone(sl.find(999))

    def test_contains_hit_and_miss(self):
        sl = SkipList(seed=7)
        sl.insert(10, "x")
        self.assertIn(10, sl)
        self.assertNotIn(999, sl)

    def test_find_returns_oldest_copy_value(self):
        # README 第 3 条：find 返回最旧副本的 value。
        sl = SkipList(seed=7)
        sl.insert(5, "first")
        sl.insert(5, "second")
        self.assertEqual(sl.find(5), "first")

    def test_contains_with_none_value(self):
        # README 期望：第 3 条「存在任一副本即命中」，value 任意（含 None），
        #             因此 insert(7, None) 后 `7 in sl` 必须为 True。
        # 实际发生：__contains__ 用 `find(key) is not None` 判断，
        #           存入 None 值的键被误判为不存在，返回 False。
        sl = SkipList(seed=7)
        sl.insert(7, None)
        self.assertIn(7, sl)


class TestDuplicateKeys(unittest.TestCase):
    """README 第 1 条：同键副本共存，先插的在前。"""

    def test_duplicate_copies_coexist_in_insertion_order(self):
        # README 期望：第 1 条，同键副本按插入先后共存于链上，
        #             range_scan 应输出 [(5, "a"), (5, "b"), (5, "c")]。
        # 实际发生：_splice 中 `pred.key == node.key: continue` 跳过了底层链接，
        #           同键副本根本没进链，range_scan 只输出 [(5, "a")]。
        sl = SkipList(seed=7)
        sl.insert(5, "a")
        sl.insert(5, "b")
        sl.insert(5, "c")
        self.assertEqual(sl.range_scan(), [(5, "a"), (5, "b"), (5, "c")])

    def test_len_counts_each_copy_once(self):
        # README 期望：第 4 条，len 等于副本总数；插 3 个同键副本 len 应为 3。
        # 实际发生：insert 命中重复键分支时多算一次（分支内 +=1 且末尾再 +=1），
        #           len 变成 4，且与 range_scan 条数（1 条）不一致。
        sl = SkipList(seed=7)
        for _ in range(3):
            sl.insert(5, "v")
        self.assertEqual(len(sl), 3)
        self.assertEqual(len(sl), len(sl.range_scan()))


class TestRemove(unittest.TestCase):
    """README 第 2 条：remove 恰移除最旧副本。"""

    def test_remove_missing_returns_false_and_changes_nothing(self):
        sl = SkipList(seed=7)
        for i in range(10):
            sl.insert(i, str(i))
        before = sl.range_scan()
        self.assertFalse(sl.remove(999))
        self.assertEqual(len(sl), 10)
        self.assertEqual(sl.range_scan(), before)

    def test_remove_unlinks_key(self):
        # README 期望：第 2 条，remove 返回 True 后该键（已无副本）__contains__
        #             必须为 False，range_scan 不再输出它，len 减一。
        # 实际发生：remove 只尝试摘除 1 层及以上的链接，从不摘除第 0 层，
        #           节点仍挂在底链上：remove(3) 返回 True、len 减一，
        #           但 3 仍在 range_scan 与 find 中「冒出来」。
        sl = SkipList(seed=7)
        for i in range(10):
            sl.insert(i, str(i))
        self.assertTrue(sl.remove(3))
        self.assertNotIn(3, sl)
        self.assertEqual(len(sl), 9)
        self.assertEqual([k for k, _ in sl.range_scan()],
                         [0, 1, 2, 4, 5, 6, 7, 8, 9])

    def test_remove_only_oldest_copy(self):
        # README 期望：第 2 条，同键有多个副本时 remove 恰移除最旧的一个，
        #             剩余副本仍在链上且顺序不变。
        # 实际发生：副本未入链（见 test_duplicate_copies_coexist_in_insertion_order），
        #           且 remove 不摘第 0 层，remove 后最旧副本依然可见。
        sl = SkipList(seed=7)
        sl.insert(5, "a")
        sl.insert(5, "b")
        self.assertTrue(sl.remove(5))
        self.assertEqual(sl.range_scan(), [(5, "b")])
        self.assertEqual(len(sl), 1)


class TestLenAndScan(unittest.TestCase):
    """README 第 4、5 条：len 与 range_scan。"""

    def test_len_matches_scan_count_for_distinct_keys(self):
        sl = SkipList(seed=7)
        keys = list(range(200))
        random.Random(42).shuffle(keys)
        for k in keys:
            sl.insert(k, k)
        self.assertEqual(len(sl), 200)
        self.assertEqual(len(sl), len(sl.range_scan()))

    def test_scan_is_sorted_and_complete(self):
        sl = SkipList(seed=7)
        keys = list(range(500))
        random.Random(1).shuffle(keys)
        for k in keys:
            sl.insert(k, k * 10)
        scanned = sl.range_scan()
        self.assertEqual([k for k, _ in scanned], list(range(500)))
        self.assertEqual(scanned, [(k, k * 10) for k in range(500)])

    def test_scan_closed_interval(self):
        # README 第 5 条：闭区间 [lo, hi]，两端都含。
        sl = SkipList(seed=7)
        for k in (60, 72, 81, 88, 95):
            sl.insert(k, str(k))
        self.assertEqual(sl.range_scan(72, 88),
                         [(72, "72"), (81, "81"), (88, "88")])

    def test_scan_unbounded_sides(self):
        sl = SkipList(seed=7)
        for k in (60, 72, 81, 88, 95):
            sl.insert(k, str(k))
        self.assertEqual([k for k, _ in sl.range_scan()], [60, 72, 81, 88, 95])
        self.assertEqual([k for k, _ in sl.range_scan(lo=81)], [81, 88, 95])
        self.assertEqual([k for k, _ in sl.range_scan(hi=81)], [60, 72, 81])

    def test_scan_lo_greater_than_hi_is_empty(self):
        sl = SkipList(seed=7)
        for k in (60, 72, 81):
            sl.insert(k, k)
        self.assertEqual(sl.range_scan(90, 70), [])

    def test_scan_bounds_need_not_be_existing_keys(self):
        sl = SkipList(seed=7)
        for k in (60, 72, 81, 88, 95):
            sl.insert(k, str(k))
        self.assertEqual([k for k, _ in sl.range_scan(70, 90)], [72, 81, 88])


class TestHeightDistribution(unittest.TestCase):
    """README 第 6 条：层级分布与 max_height。"""

    def test_max_height_empty_is_zero(self):
        self.assertEqual(SkipList(seed=7).max_height, 0)

    def test_max_height_at_thousand_scale(self):
        # README 期望：第 6 条，P(height >= k) = (1/4)^(k-1)，上限 16 层；
        #             千级元素规模下 max_height 通常不低于 4 层
        #             （4096 个节点全不超过 3 层的概率约 (1-1/64)^4096 ≈ e^-64，
        #             断言留足余量，取 >= 4）。
        # 实际发生：_random_height 的循环条件写成 `h > _MAX_LEVEL`（应为 <），
        #           循环体永不执行，所有节点恒为 1 层，max_height 恒为 1，
        #           查找/插入退化为 O(n)（README 第 7 条随之不成立）。
        sl = SkipList(seed=20260920)
        for i in range(4096):
            sl.insert(i, i)
        self.assertGreaterEqual(sl.max_height, 4)
        self.assertLessEqual(sl.max_height, 16)

    def test_seed_reproducibility(self):
        # 构造时传相同 seed，随机层级序列可复现（max_height 可观测）。
        a = SkipList(seed=123)
        b = SkipList(seed=123)
        for i in range(500):
            a.insert(i, i)
            b.insert(i, i)
        self.assertEqual(a.max_height, b.max_height)


class TestDifferentialAgainstReference(unittest.TestCase):
    """不变量对拍：任意操作序列后，与朴素参考实现的结果、顺序、长度一致。"""

    def test_random_op_stream_matches_reference(self):
        # README 期望：第 1~5 条组合不变量 —— 任意 insert/remove/find/range_scan
        #             混排（含重复键与不存在键）后，中序遍历严格有序且与
        #             插入集合一致、删除过的键不再出现、len 与实际键数一致。
        # 实际发生：remove 不摘第 0 层（已删键仍在扫描中）、同键副本未入链、
        #           重复插入 len 重复计数，操作流开始不久即与参考实现分叉。
        seed = 20260920
        rng = random.Random(seed)
        sl = SkipList(seed=seed)
        ref = _Reference()
        key_pool = list(range(40))  # 小键池，保证大量重复键与已删键

        for step in range(3000):
            op = rng.random()
            key = rng.choice(key_pool)
            if op < 0.45:
                value = rng.randrange(1000)
                sl.insert(key, value)
                ref.insert(key, value)
            elif op < 0.70:
                self.assertEqual(sl.remove(key), ref.remove(key),
                                 "remove(%r) 返回值分叉 @ step %d" % (key, step))
            elif op < 0.85:
                self.assertEqual(sl.find(key), ref.find(key),
                                 "find(%r) 分叉 @ step %d" % (key, step))
            else:
                lo = rng.choice(key_pool + [None])
                hi = rng.choice(key_pool + [None])
                self.assertEqual(sl.range_scan(lo, hi), ref.scan(lo, hi),
                                 "range_scan(%r, %r) 分叉 @ step %d"
                                 % (lo, hi, step))
            self.assertEqual(len(sl), len(ref),
                             "len 分叉 @ step %d" % step)
            # 全量扫描对拍：顺序与内容必须完全一致。
            self.assertEqual(sl.range_scan(), ref.scan(),
                             "全量扫描分叉 @ step %d" % step)


class TestPerformance(unittest.TestCase):
    """README 第 7 条：键数 1 万 -> 10 万，查找与插入不出现明显超线性拐点。"""

    def _build(self, n, seed):
        # 降序插入构造基表：即便实现退化为单链表，构造也是 O(1) 每节点，
        # 保证本用例在红状态下也能在有限时间内跑完。
        sl = SkipList(seed=seed)
        for k in range(n, 0, -1):
            sl.insert(k, k)
        return sl

    def _mixed_ops_time(self, sl, n, op_count, seed):
        rng = random.Random(seed)
        start = time.perf_counter()
        for i in range(op_count):
            key = rng.randrange(1, n + 1)
            if i % 2 == 0:
                sl.find(key)
            else:
                sl.insert(key, key)
        return time.perf_counter() - start

    def test_no_superlinear_scaling(self):
        # README 期望：第 7 条，查找/插入为 O(log n)，规模 10x 时每操作耗时
        #             只应增长约 log(1e5)/log(1e4) ≈ 1.25 倍，阈值放宽到 4 倍
        #             保证 CI 稳定（正确实现实测远低于 2）。
        # 实际发生：所有节点恒为 1 层（见 test_max_height_at_thousand_scale），
        #           查找/插入退化为 O(n)，规模 10x 时每操作耗时约 10x，超阈值。
        n_small, n_large = 10_000, 100_000
        op_count = 3000

        sl_small = self._build(n_small, seed=11)
        sl_large = self._build(n_large, seed=11)

        t_small = self._mixed_ops_time(sl_small, n_small, op_count, seed=99)
        t_large = self._mixed_ops_time(sl_large, n_large, op_count, seed=99)

        ratio = t_large / max(t_small, 1e-9)
        self.assertLess(
            ratio, 4.0,
            "每操作耗时比 %.2f（1e5 vs 1e4），疑似超线性拐点" % ratio)


if __name__ == "__main__":
    unittest.main()
