"""skiplist 语义测试、随机对拍与性能回归。

只依赖标准库，`python3 tests/test_skiplist.py` 或
`python3 -m unittest tests.test_skiplist` 均可独立重复运行。

约定：
- 名称含 test_red_ 的用例用于钉住源码与 README 不符的缺陷，
  每条红用例上方都有「README 期望 / 实际发生」注释。
- README 未约定的自由行为（如 remove 后 max_height 是否回缩）不钉。
- 随机数据全部使用固定 seed，统计性断言留足余量，不依赖时序碰运气。
"""

import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skiplist.skiplist import SkipList, _MAX_LEVEL, _P


class _ReferenceSortedMap:
    """README 语义的朴素参考实现：插入序 list 承载副本 + 稳定排序扫描。"""

    def __init__(self):
        self._items = []  # [(key, value)]，插入先后即 list 先后

    def insert(self, key, value):
        self._items.append((key, value))

    def remove(self, key):
        for idx, (existing, _value) in enumerate(self._items):
            if existing == key:
                del self._items[idx]
                return True
        return False

    def find(self, key):
        for existing, value in self._items:
            if existing == key:
                return value
        return None

    def contains(self, key):
        return any(existing == key for existing, _ in self._items)

    def __len__(self):
        return len(self._items)

    def scan(self, lo, hi):
        # sorted 稳定：同键元素保持插入先后，即 README 的「先插的在前」
        ordered = sorted(self._items, key=lambda item: item[0])
        if lo is not None:
            ordered = [item for item in ordered if item[0] >= lo]
        if hi is not None:
            ordered = [item for item in ordered if item[0] <= hi]
        return ordered


class TestBasicContract(unittest.TestCase):

    def test_empty_list(self):
        sl = SkipList(seed=0)
        self.assertEqual(len(sl), 0)
        self.assertEqual(sl.max_height, 0)
        self.assertEqual(sl.range_scan(), [])
        self.assertIsNone(sl.find(1))
        self.assertNotIn(1, sl)
        self.assertFalse(sl.remove(1))

    def test_seed_reproduces_structure(self):
        def build(seed):
            sl = SkipList(seed=seed)
            for k in (5, 1, 9, 3, 7, 2, 8):
                sl.insert(k, "v%d" % k)
            return sl

        self.assertEqual(build(42).range_scan(), build(42).range_scan())
        self.assertEqual(build(42).range_scan(),
                         [(1, "v1"), (2, "v2"), (3, "v3"), (5, "v5"),
                          (7, "v7"), (8, "v8"), (9, "v9")])

    def test_red_single_key_lifecycle(self):
        # README 期望（第 1~4 条）：单键 insert -> 命中 -> remove ->
        # 彻底消失，len 归 0。
        # 实际发生：remove 不摘第 0 层链边，删除后 find/in/scan 全部
        # 仍能看到该键（幽灵键），len 却被扣成 0，计数与结构脱节。
        sl = SkipList(seed=1)
        sl.insert(11, "eleven")
        self.assertEqual(len(sl), 1)
        self.assertGreaterEqual(sl.max_height, 1)
        self.assertEqual(sl.find(11), "eleven")
        self.assertIn(11, sl)
        self.assertTrue(sl.remove(11))
        self.assertEqual(len(sl), 0)
        self.assertIsNone(sl.find(11))
        self.assertNotIn(11, sl)
        self.assertEqual(sl.range_scan(), [])
        self.assertFalse(sl.remove(11))

    def test_distinct_keys_stay_sorted(self):
        sl = SkipList(seed=7)
        keys = [88, 72, 95, 60, 81, 1, 50, 100, 42]
        for k in keys:
            sl.insert(k, k * 2)
        self.assertEqual([k for k, _ in sl.range_scan()], sorted(keys))
        self.assertEqual(len(sl), len(keys))


class TestInsertDuplicates(unittest.TestCase):

    def test_green_distinct_insert_appends(self):
        sl = SkipList(seed=2)
        sl.insert(3, "a")
        sl.insert(5, "b")
        self.assertEqual(sl.range_scan(), [(3, "a"), (5, "b")])

    def test_red_duplicate_insert_creates_coexisting_copies(self):
        # README 期望（第 1 条）：insert 恒新增副本，同键副本按插入先后
        # 共存于链上，先插的在前；scan 应为 [(10,'a'), (10,'b')]，
        # len 为 2（第 4 条：len 等于副本总数）。
        # 实际发生：insert 命中同键段后先走链到段尾，_splice 在每一层
        # 都因 `pred.key == node.key` 而 continue，新节点一条边都没接上，
        # 成为链外孤儿（scan/find 永远看不到它）；与此同时 _size 在分支
        # 内外各 += 1 一次，len 变成 3——副本没进去，计数反而多加。
        sl = SkipList(seed=1)
        sl.insert(10, "a")
        sl.insert(10, "b")
        self.assertEqual(sl.range_scan(), [(10, "a"), (10, "b")])
        self.assertEqual(len(sl), 2)

    def test_red_three_copies_ordered_oldest_first(self):
        # README 期望（第 1/3/4 条）：三个同键副本按插入序输出 x1,x2,x3，
        # find 返回最旧的 x1，len 为 3。
        # 实际发生：第 2、3 个副本全部是挂不上链的孤儿，链上只剩 x1；
        # len 却累加成 5（首个 +1，后两个各 +2）。
        sl = SkipList(seed=1)
        sl.insert(10, "x1")
        sl.insert(10, "x2")
        sl.insert(10, "x3")
        self.assertEqual(sl.range_scan(),
                         [(10, "x1"), (10, "x2"), (10, "x3")])
        self.assertEqual(sl.find(10), "x1")
        self.assertEqual(len(sl), 3)


class TestFindAndContains(unittest.TestCase):

    def test_green_find_missing_returns_none(self):
        sl = SkipList(seed=3)
        sl.insert(1, "one")
        self.assertIsNone(sl.find(2))
        self.assertNotIn(2, sl)

    def test_green_find_returns_inserted_value(self):
        sl = SkipList(seed=3)
        sl.insert(4, "four")
        sl.insert(2, "two")
        self.assertEqual(sl.find(4), "four")
        self.assertEqual(sl.find(2), "two")

    def test_red_contains_treats_none_value_as_missing(self):
        # README 期望（第 3 条 + 开篇「value 任意」）：存在任一副本即
        # 命中；存入 value=None 后 `key in sl` 必须为 True。
        # 实际发生：__contains__ 写成 `return self.find(key) is not None`，
        # 用 value 的真值判定键命中，value=None 的现存键被误判不存在。
        sl = SkipList(seed=1)
        sl.insert(7, None)
        self.assertIn(7, sl)

    def test_red_find_sees_second_copy_and_returns_oldest(self):
        # README 期望（第 1/3 条）：两个副本共存于链上，find 返回最旧
        # 副本 "old"。
        # 实际发生：新副本是链外孤儿，scan/find 的键集合从插入起就缺了
        # 它（与 test_red_duplicate_insert_creates_coexisting_copies
        # 同根）；同时钉住 find 必须落最旧副本，防止修复插入时误接到
        # 同键段尾部而返回 "new"。
        sl = SkipList(seed=1)
        sl.insert(9, "old")
        sl.insert(9, "new")
        self.assertEqual(sl.range_scan(9, 9), [(9, "old"), (9, "new")])
        self.assertEqual(sl.find(9), "old")


class TestRemove(unittest.TestCase):

    def test_green_remove_missing_returns_false_and_changes_nothing(self):
        sl = SkipList(seed=5)
        sl.insert(1, "a")
        sl.insert(2, "b")
        snapshot = sl.range_scan()
        size = len(sl)
        self.assertFalse(sl.remove(99))
        self.assertEqual(sl.range_scan(), snapshot)
        self.assertEqual(len(sl), size)

    def test_red_remove_unlinks_node_from_level_zero(self):
        # README 期望（第 2 条）：存在副本时摘除该副本；该键无副本后
        # __contains__ 为 False，find 为 None，range_scan 不再输出它。
        # 实际发生：remove 的前驱收集循环条件写成 `while i > 0`，只覆盖
        # 第 1 层及以上，第 0 层 backbone 从不摘除节点；remove 返回 True
        # 且 _size 减 1，但节点对所有查询依旧可见——“删掉的键又冒出来”。
        sl = SkipList(seed=1)
        sl.insert(5, "x")
        self.assertTrue(sl.remove(5))
        self.assertNotIn(5, sl)
        self.assertIsNone(sl.find(5))
        self.assertEqual(sl.range_scan(), [])

    def test_red_remove_after_real_removal_returns_false(self):
        # README 期望（第 2 条）：唯一副本删除后再次 remove 返回 False，
        # 不改动结构，len 保持 0（第 4 条）。
        # 实际发生：节点仍挂在第 0 层，remove 反复返回 True 并持续递减
        # _size；再调一次 len() 直接抛
        # ValueError: __len__() should return >= 0。
        sl = SkipList(seed=1)
        sl.insert(5, "x")
        self.assertTrue(sl.remove(5))
        self.assertFalse(sl.remove(5))
        self.assertEqual(len(sl), 0)
        self.assertEqual(sl.range_scan(), [])

    def test_red_remove_one_of_duplicates_drops_oldest_only(self):
        # README 期望（第 2/3/4 条）：两个同键副本时 remove 一次只摘最旧
        # 副本，find/scan 仍可见剩余的新副本，len 为 1；再 remove 才清空，
        # 第三次返回 False。
        # 实际发生：新副本插入起就是链外孤儿；第一次 remove 只动高层边
        # （这些边根本没指向孤儿），链上旧副本依旧可见，计数却 -1；之后
        # 无论 remove 多少次都清不掉第 0 层的旧副本。
        sl = SkipList(seed=1)
        sl.insert(8, "old")
        sl.insert(8, "new")
        self.assertTrue(sl.remove(8))
        self.assertEqual(sl.range_scan(8, 8), [(8, "new")])
        self.assertEqual(sl.find(8), "new")
        self.assertEqual(len(sl), 1)
        self.assertTrue(sl.remove(8))
        self.assertFalse(sl.remove(8))
        self.assertEqual(len(sl), 0)

    def test_red_remove_keeps_other_keys_intact(self):
        # README 期望（第 2 条）：删掉键 2 的最旧副本后，其余键与键 2
        # 的剩余副本都还在，序列为 [1,2,3]，len 为 3。
        # 实际发生：键 2 的第二个副本插入时已是链外孤儿，remove 又不摘
        # 第 0 层，删除后序列变成 [1,2,2,3]、len 为 3，键 2 的旧副本
        # 幽灵残留而新副本从未入链。
        sl = SkipList(seed=9)
        for k, v in ((1, "a"), (2, "b"), (3, "c"), (2, "b2")):
            sl.insert(k, v)
        sl.remove(2)
        self.assertEqual([k for k, _ in sl.range_scan()], [1, 2, 3])
        self.assertEqual(len(sl), 3)


class TestLenAndScanConsistency(unittest.TestCase):

    def test_green_len_matches_scan_without_duplicates(self):
        sl = SkipList(seed=11)
        for k in (4, 1, 7, 2, 6):
            sl.insert(k, k)
        self.assertEqual(len(sl), len(sl.range_scan()))

    def test_red_len_matches_scan_under_duplicate_inserts(self):
        # README 期望（第 4 条）：len 等于副本总数，与 range_scan() 输出
        # 条数一致，此处两者都应为 3。
        # 实际发生：同键插入多做一次 _size += 1 而副本未入链，最终
        # len()==4 而 scan 只有 2 条。
        sl = SkipList(seed=1)
        sl.insert(10, "a")
        sl.insert(10, "b")
        sl.insert(20, "c")
        self.assertEqual(len(sl), len(sl.range_scan()))

    def test_red_len_nonnegative_after_repeated_remove(self):
        # README 期望（第 2/4 条）：无副本时 remove 不改结构也不改计数，
        # len 恒为非负。
        # 实际发生：幽灵节点让 remove 反复“成功”，_size 被扣成负数，
        # len() 抛 ValueError: __len__() should return >= 0。
        sl = SkipList(seed=1)
        sl.insert(6, "z")
        sl.remove(6)
        sl.remove(6)  # README 语义下应返回 False 且计数不变
        try:
            size = len(sl)
        except ValueError as exc:
            self.fail("_size 被扣成负数，len() 抛 %r" % exc)
        self.assertGreaterEqual(size, 0)


class TestRangeScan(unittest.TestCase):

    def setUp(self):
        self.sl = SkipList(seed=4)
        for k in (1, 2, 3, 4, 5):
            self.sl.insert(k, "v%d" % k)

    def test_green_full_scan_sorted(self):
        self.assertEqual([k for k, _ in self.sl.range_scan()],
                         [1, 2, 3, 4, 5])

    def test_green_closed_interval_inclusive_bounds(self):
        self.assertEqual([k for k, _ in self.sl.range_scan(2, 4)],
                         [2, 3, 4])

    def test_green_one_sided_bounds(self):
        self.assertEqual([k for k, _ in self.sl.range_scan(4)], [4, 5])
        self.assertEqual([k for k, _ in self.sl.range_scan(None, 2)],
                         [1, 2])

    def test_green_lo_greater_than_hi_returns_empty(self):
        self.assertEqual(self.sl.range_scan(5, 1), [])

    def test_green_intervals_outside_domain_are_empty(self):
        self.assertEqual(self.sl.range_scan(100, 200), [])
        self.assertEqual(self.sl.range_scan(-10, -1), [])

    def test_green_boundary_single_key_interval(self):
        self.assertEqual(self.sl.range_scan(3, 3), [(3, "v3")])


class TestLevelDistribution(unittest.TestCase):
    """README 第 6 条：P(height >= k) = (1/4)^(k-1)，上限 16。"""

    def _heights(self, sl, draws):
        return [sl._random_height() for _ in range(draws)]

    def test_green_height_never_below_one_or_above_cap(self):
        sl = SkipList(seed=0)
        heights = self._heights(sl, 5000)
        self.assertGreaterEqual(min(heights), 1)
        self.assertLessEqual(max(heights), _MAX_LEVEL)

    def test_red_geometric_tail_probabilities(self):
        # README 期望（第 6 条）：每层以 1/4 概率再升一层，
        # P(height >= k) = (1/4)^(k-1)。30000 次抽样、0.4x~2.5x 的宽松
        # 区间只抓“分布完全不对”，不卡正常随机波动。
        # 实际发生：_random_height 的循环条件写成 `while h > _MAX_LEVEL`，
        # h 从 1 起恒为假，高度永远是 1，P(h>=2) 实际为 0（期望 0.25）。
        draws = 30000
        sl = SkipList(seed=20240920)
        heights = self._heights(sl, draws)
        for k in (2, 3):
            expected = _P ** (k - 1)
            observed = sum(1 for h in heights if h >= k) / draws
            self.assertGreater(observed, expected * 0.4,
                               "P(h>=%d)=%.4f 远低于期望 %.4f"
                               % (k, observed, expected))
            self.assertLess(observed, expected * 2.5,
                            "P(h>=%d)=%.4f 远高于期望 %.4f"
                            % (k, observed, expected))

    def test_red_cap_can_actually_be_reached(self):
        # README 期望（第 6 条）：上限 16 层意味着分布允许抽到 16。
        # 200000 次抽样中 P(h=16)=(1/4)^15≈9.3e-10，期望命中约
        # 0.00019 次——单次都够不到属于正常波动，所以这里不直接要求
        # 出现 16；改为要求 200000 次抽样里至少出现高度 8（期望约
        # 19 次，余量极宽）。实际发生：高度恒为 1，8 一次都不出现。
        sl = SkipList(seed=77)
        heights = self._heights(sl, 200000)
        self.assertGreaterEqual(max(heights), 8)

    def test_red_max_height_grows_beyond_one_at_thousand_scale(self):
        # README 期望（第 6 条）：千级元素规模下 max_height 通常不低于
        # 4 层。取 3 个固定 seed，断言至少 2 个 >=4，阈值放到 3
        # （理论均值 1 + log_4(1000) ≈ 6），只钉“完全不高层化”。
        # 实际发生：所有节点高度恒为 1，max_height 永远是 1。
        reached = []
        for seed in (101, 202, 303):
            sl = SkipList(seed=seed)
            for k in range(1000):
                sl.insert(k, k)
            reached.append(sl.max_height)
        self.assertGreaterEqual(sum(1 for h in reached if h >= 4), 2,
                                "千级规模 max_height=%r" % reached)

    def test_green_max_height_is_zero_on_empty_and_positive_nonempty(self):
        sl = SkipList(seed=0)
        self.assertEqual(sl.max_height, 0)
        sl.insert(1, 1)
        self.assertGreaterEqual(sl.max_height, 1)


class TestRandomDifferential(unittest.TestCase):
    """固定 seed 随机操作流与朴素参考实现逐步对拍。

    每个操作后检查四条有序映射不变量：
    1. 中序遍历（range_scan 全量）与参考副本集合逐元素一致（含顺序）；
    2. 遍历序列严格非降且同键保持插入先后（参考侧 sorted 稳定性）；
    3. 删除过且无剩余副本的键不再出现；
    4. len 与实际副本数一致。
    """

    KEYSPACE = 10
    NOPS = 300
    SEEDS = (0, 1, 2, 3, 4, 7, 11, 42)

    def _run_stream(self, seed):
        sl = SkipList(seed=seed)
        ref = _ReferenceSortedMap()
        rng = random.Random(1000 + seed)
        step = 0
        try:
            for step in range(self.NOPS):
                roll = rng.random()
                key = rng.randrange(self.KEYSPACE)

                if roll < 0.45:  # 插入（含大量重复键）
                    value = "s%d-%d" % (seed, step)
                    sl.insert(key, value)
                    ref.insert(key, value)
                elif roll < 0.75:  # 删除（重复删 / 删不存在的键）
                    got = sl.remove(key)
                    want = ref.remove(key)
                    self.assertEqual(
                        got, want,
                        "seed=%d step=%d remove(%r) 返回 %r，参考 %r"
                        % (seed, step, key, got, want))
                elif roll < 0.9:  # 点查
                    self.assertEqual(
                        sl.find(key), ref.find(key),
                        "seed=%d step=%d find(%r) 不一致"
                        % (seed, step, key))
                    self.assertEqual(
                        key in sl, ref.contains(key),
                        "seed=%d step=%d contains(%r) 不一致"
                        % (seed, step, key))
                else:  # 区间遍历（含 None 边界与 lo>hi）
                    lo = None if rng.random() < 0.25 else rng.randrange(
                        self.KEYSPACE)
                    hi = None if rng.random() < 0.25 else rng.randrange(
                        self.KEYSPACE)
                    self.assertEqual(
                        sl.range_scan(lo, hi), ref.scan(lo, hi),
                        "seed=%d step=%d range_scan(%r,%r) 不一致"
                        % (seed, step, lo, hi))

                # 不变量 1/2：全量中序遍历与参考完全一致（含同键先后）
                full = sl.range_scan()
                expected = ref.scan(None, None)
                self.assertEqual(
                    full, expected,
                    "seed=%d step=%d 全量遍历不一致" % (seed, step))
                keys_only = [k for k, _ in full]
                self.assertEqual(
                    keys_only, sorted(keys_only),
                    "seed=%d step=%d 中序遍历非有序" % (seed, step))
                # 不变量 3：对参考侧已清空的键，跳表不得再输出
                for absent in range(self.KEYSPACE):
                    if not ref.contains(absent):
                        self.assertNotIn(
                            absent, keys_only,
                            "seed=%d step=%d 已删除键 %r 再次出现"
                            % (seed, step, absent))
                # 不变量 4：len 与实际副本数一致
                self.assertEqual(
                    len(sl), len(expected),
                    "seed=%d step=%d len=%d 与实际副本数 %d 不符"
                    % (seed, step, len(sl), len(expected)))
        except AssertionError:
            raise
        except Exception as exc:  # 源码缺陷可能直接抛异常（如 len<0）
            self.fail("seed=%d step=%d 操作流引发异常: %r"
                      % (seed, step, exc))

    def test_green_distinct_key_insertion_stream_matches_reference(self):
        # 对拍框架的无缺陷基线：固定 seed 的互异键插入流（不触发重复
        # 副本与删除路径），每步全量遍历与 len 都必须与参考一致，
        # 用于证明对拍逻辑本身不会误报。
        sl = SkipList(seed=101)
        ref = _ReferenceSortedMap()
        order = list(range(120))
        random.Random(2024).shuffle(order)
        for step, key in enumerate(order):
            sl.insert(key, step)
            ref.insert(key, step)
            self.assertEqual(sl.range_scan(), ref.scan(None, None))
            self.assertEqual(len(sl), len(ref))

    def test_red_mixed_operation_streams_match_reference(self):
        # README 期望（第 1~5 条整体）：插入/删除/查询/区间遍历混排后，
        # 结果、顺序、长度每一步都与朴素参考实现一致。
        # 实际发生：固定 seed=0 的流在第 14 步首次删除键时即分叉——
        # remove 不摘第 0 层，已删键在随后全量遍历中幽灵重现；继续跑还
        # 会叠加副本孤儿（len 虚高）与重复 remove 把 len 扣成负数
        # （ValueError）。逐条语义用例已分别钉根因，本用例钉
        # “任意操作序列后不变量必须成立”。
        for seed in self.SEEDS:
            self._run_stream(seed)


class TestPerformanceScaling(unittest.TestCase):
    """README 第 7 条：查找/插入随规模保持 O(log n)，无明显超线性拐点。

    固定 seed、固定数据构造（互异、确定的键序列），只测墙钟时间比值，
    阈值按本机多 seed 实测放宽（好实现比值远低于阈值，坏实现远超），
    不依赖绝对时序。坏实现因每次检查点都会超阈，测试在 2 万键处即
    提前失败，整套用例红路运行时间仍在十几秒量级。
    """

    SEED = 20240920
    N_FULL = 100000
    CHECKPOINTS = (10000, 20000, 40000, 100000)
    FIND_BATCH = 2000
    # 规模翻倍时：好实现点查均摊仅增 ~1.1~1.25 倍（log n 之差），
    # 坏实现严格翻倍（~2.0）。阈值 1.7 留足 CI 抖动余量。
    FIND_DOUBLING_LIMIT = 1.7
    # 累计插入耗时翻倍：好实现 ~2.0~2.6（n log n 次线性），坏实现
    # ~4.5+（O(n^2)）。阈值 3.2 卡在两者之间。
    INSERT_DOUBLING_LIMIT = 3.2

    @staticmethod
    def _find_per_op(sl, bound, rng):
        queries = [rng.randrange(bound) for _ in range(
            TestPerformanceScaling.FIND_BATCH)]

        def once():
            start = time.perf_counter()
            for key in queries:
                sl.find(key)
            return time.perf_counter() - start

        return min(once() for _ in range(3)) / TestPerformanceScaling.FIND_BATCH

    def test_red_no_superlinear_kink_from_10k_to_100k(self):
        # README 期望（第 7 条，依赖第 6 条分布成立）：键数从一万增到
        # 十万，查找与插入不出现明显超线性拐点。
        # 实际发生：_random_height 恒返回 1，跳表退化为单链表，查找/
        # 插入均为 O(n)：点查均摊随规模线性翻倍（2 万/1 万 ≈ 2.0），
        # 累计插入耗时随翻倍放大约 4.5 倍（n^2 特征），查询越跑越慢。
        sl = SkipList(seed=self.SEED)
        rng = random.Random(self.SEED ^ 0x55AA)
        find_per_op = {}
        insert_cum = {}
        start_build = time.perf_counter()
        previous_checkpoint = None
        for count in range(1, self.N_FULL + 1):
            sl.insert(count * 7 + 3, count)  # 互异键，固定构造
            if count in self.CHECKPOINTS:
                insert_cum[count] = time.perf_counter() - start_build
                find_per_op[count] = self._find_per_op(
                    sl, count * 7 + 3, rng)
                if previous_checkpoint is not None:
                    find_ratio = (find_per_op[count]
                                  / find_per_op[previous_checkpoint])
                    insert_ratio = (insert_cum[count]
                                    / insert_cum[previous_checkpoint])
                    self.assertLess(
                        find_ratio, self.FIND_DOUBLING_LIMIT,
                        "%d->%d 键点查均摊增长 x%.2f（超 %.1f，"
                        "呈线性而非 O(log n)）"
                        % (previous_checkpoint, count, find_ratio,
                           self.FIND_DOUBLING_LIMIT))
                    self.assertLess(
                        insert_ratio, self.INSERT_DOUBLING_LIMIT,
                        "%d->%d 键累计插入耗时增长 x%.2f（超 %.1f，"
                        "疑似 O(n^2)）"
                        % (previous_checkpoint, count, insert_ratio,
                           self.INSERT_DOUBLING_LIMIT))
                previous_checkpoint = count

        # 终态再确认：10 万键规模下点查均摊相对 1 万键不应超过 3 倍
        # （好实现实测 ~2.3，含 log_4(10)≈1.66 的理论增量）。
        overall = find_per_op[100000] / find_per_op[10000]
        self.assertLess(overall, 3.0,
                        "1万->10万键点查均摊增长 x%.2f" % overall)


if __name__ == "__main__":
    unittest.main(verbosity=2)
