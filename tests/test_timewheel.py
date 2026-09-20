"""timewheel 语义测试。

以 README 的「语义约定」为唯一基准：逐条锁语义用例 + 时序性质对拍。
- GREEN_* 类：README 语义在当前源码上成立的行为。
- RED_* 类：当前源码与 README 不符的行为（允许红），每个用例上方注释写清
  「README 期望什么 / 实际发生什么」。
- Property* 类：时序性质（单调推进不早不晚不重复、小步/大步序列一致）与
  朴素参考实现（NaiveWheel）的随机对拍。

时序全部由注入的 ManualClock 定死节奏；可直接：
    python3 -m unittest tests.test_timewheel -v
    python3 tests/test_timewheel.py          # 等价
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timewheel import TimeWheel  # noqa: E402
from timewheel.clock import ManualClock  # noqa: E402
from timewheel.wheel import TaskHandle  # noqa: E402


def make_wheel(slots=8, tick=1.0, start=0.0):
    clock = ManualClock(start)
    return clock, TimeWheel(slots=slots, tick=tick, clock=clock)


def plant(wheel, task, deadline, slot):
    """绕过 add 直接把任务挂进指定槽（仅用于隔离 advance/drain 语义）。"""
    handle = TaskHandle(task, deadline, slot, wheel)
    wheel._buckets[slot].append(handle)
    return handle


# ---------------------------------------------------------------------------
# 朴素参考实现：按到期时刻排序的列表，每次推进扫描到期项（README 语义）。
# tick 对齐延迟下，同一到期时刻任务的加入顺序即就绪队列追加顺序，因此排序
# 键取 (deadline, seq) 与 README 第 2/3 条要求的追加/取出顺序完全一致。
# ---------------------------------------------------------------------------
class NaiveWheel:
    def __init__(self, slots, tick):
        self.slots = slots
        self.tick = tick
        self.now = 0.0
        self.pending = []
        self.ready = []
        self.counter = 0

    def add(self, delay, task):
        if delay <= 0:
            raise ValueError("delay must be positive")
        if delay > self.slots * self.tick:
            raise ValueError("delay beyond one revolution")
        self.counter += 1
        handle = [task, self.now + delay, self.counter, "pending"]
        self.pending.append(handle)
        return handle

    def advance(self, now):
        if now < self.now:
            raise ValueError("cannot move backwards")
        steps = int((now - self.now) // self.tick)
        if steps <= 0:
            return
        cutoff = self.now + steps * self.tick
        due = [h for h in self.pending if h[1] <= cutoff]
        due.sort(key=lambda h: (h[1], h[2]))
        self.pending = [h for h in self.pending if h[1] > cutoff]
        for h in due:
            h[3] = "ready"
            self.ready.append(h)
        self.now = cutoff

    def due(self):
        out = [h[0] for h in self.ready]
        for h in self.ready:
            h[3] = "taken"
        self.ready = []
        return out

    def cancel(self, handle):
        if handle[3] == "pending":
            self.pending.remove(handle)
        elif handle[3] == "ready":
            self.ready.remove(handle)
        else:
            return False
        handle[3] = "cancelled"
        return True

    def remaining(self):
        return {h[0] for h in self.pending} | {h[0] for h in self.ready}


def wheel_remaining(wheel, handles, delivered):
    out = set()
    for h in handles:
        if h.cancelled or h.task in delivered:
            continue
        if h in wheel._buckets[h.slot] or h in wheel._ready.values():
            out.add(h.task)
    return out


def run_scenario(seed, slots=8, n=250, safe=False):
    """固定 seed 的 add/cancel/advance 交错序列，返回 None 或首个分歧描述。

    safe=True 时把序列约束在当前实现已知无缺陷的子空间内（落点不经过最后
    一个槽、不跨回绕、相对延迟唯一、只取消未到期任务），用于验证参考模型
    本身的正确性与无缺陷区域的性质；safe=False 覆盖全域以钉出缺陷。
    返回元组 (阶段, ...)，触发顺序/次数/最终剩余任务任一不一致即非 None。
    """
    rng = random.Random(seed)
    ref = NaiveWheel(slots, 1.0)
    wheel = TimeWheel(slots=slots, tick=1.0, clock=ManualClock(0.0))
    handles = []
    ref_map = {}
    delivered = set()
    t = 0.0
    for i in range(n):
        r = rng.random()
        if r < 0.5:
            cursor = int(wheel._cursor)
            if safe:
                used = {h.deadline - wheel.now for h in handles
                        if not h.cancelled and h in wheel._buckets[h.slot]}
                steps_opts = [s for s in range(1, slots - 1 - cursor)
                              if float(s) not in used
                              and cursor + s <= slots - 2]
                if not steps_opts:
                    continue
                delay = float(rng.choice(steps_opts))
            else:
                delay = float(rng.randrange(1, slots + 1))
            task = "t%d" % i
            wh = wheel.add(delay, task)
            rh = ref.add(delay, task)
            handles.append(wh)
            ref_map[task] = rh
        elif r < 0.65 and handles:
            if safe:
                pending = [h for h in handles
                           if not h.cancelled and h in wheel._buckets[h.slot]]
                if not pending:
                    continue
                wh = rng.choice(pending)
            else:
                wh = rng.choice(handles)
            rh = ref_map[wh.task]
            actual = wh.cancel()
            expected = ref.cancel(rh)
            if actual != expected:
                return ("cancel", i, wh.task, actual, expected)
        elif safe and int(wheel._cursor) >= slots - 2:
            continue
        else:
            if safe:
                k = rng.randrange(1, slots - 1)
                if int(wheel._cursor) + k > slots - 2:
                    k = (slots - 2) - int(wheel._cursor)
            else:
                k = rng.randrange(1, slots + 3)
            t += k
            wheel.advance(t)
            ref.advance(t)
            actual = wheel.due()
            expected = ref.due()
            delivered |= set(actual)
            if actual != expected:
                return ("due", i, t, actual, expected)
    actual_remaining = wheel_remaining(wheel, handles, delivered)
    expected_remaining = ref.remaining()
    if actual_remaining != expected_remaining:
        return ("remaining", actual_remaining, expected_remaining)
    return None


class GREEN_TimeModelAndSlots(unittest.TestCase):
    """README 第 1 条：时间模型、回绕、最后槽参与（当前成立的部分）。"""

    def test_now_from_injected_clock(self):
        clock, wheel = make_wheel(start=1000.0)
        self.assertEqual(wheel.now, 1000.0)
        clock.advance(5.0)
        # 注入时钟只在构造时读一次；之后 now 只随 advance 变化
        self.assertEqual(wheel.now, 1000.0)

    def test_now_advances_by_whole_ticks_only(self):
        _, wheel = make_wheel()
        wheel.advance(2.0)
        self.assertEqual(wheel.now, 2.0)
        wheel.advance(2.9)
        self.assertEqual(wheel.now, 2.0)
        wheel.advance(3.0)
        self.assertEqual(wheel.now, 3.0)

    def test_non_integer_tick_quantizes(self):
        _, wheel = make_wheel(tick=0.5)
        wheel.advance(0.7)
        self.assertEqual(wheel.now, 0.5)
        wheel.advance(1.0)
        self.assertEqual(wheel.now, 1.0)

    def test_delay_must_be_positive(self):
        _, wheel = make_wheel()
        for bad in (0, -1.0):
            with self.assertRaises(ValueError):
                wheel.add(bad, "x")

    def test_delay_beyond_one_revolution_rejected(self):
        _, wheel = make_wheel(slots=8, tick=1.0)
        with self.assertRaises(ValueError):
            wheel.add(8.0001, "x")
        # 边界：恰好一整圈 slots*tick 必须接受
        h = wheel.add(8.0, "edge")
        self.assertEqual(h.deadline, 8.0)

    def test_deadline_is_now_plus_delay(self):
        _, wheel = make_wheel()
        h = wheel.add(2.5, "x")
        self.assertEqual(h.deadline, 2.5)
        wheel.advance(1.0)
        h2 = wheel.add(2.0, "y")
        self.assertEqual(h2.deadline, 3.0)

    def test_fractional_delay_uses_ceil_for_slot(self):
        # ceil(0.2/1) = 1：不足一个 tick 的延时也落在下一槽
        _, wheel = make_wheel(slots=8)
        h = wheel.add(0.2, "x")
        self.assertEqual(h.slot, 1)

    def test_slots_modulo_indexing_within_arc(self):
        # cursor=2, steps=3 -> 槽 5（不跨最后槽时取模与 README 一致）
        _, wheel = make_wheel(slots=8)
        wheel.advance(2.0)
        h = wheel.add(3.0, "x")
        self.assertEqual(h.slot, 5)

    def test_last_slot_participates_without_wrap(self):
        # 最后一个槽（下标 slots-1）不回绕时照常参与
        _, wheel = make_wheel(slots=8)
        plant(wheel, "last", 7.0, 7)
        wheel.advance(7.0)
        self.assertEqual(wheel.due(), ["last"])

    def test_constructor_rejects_bad_params(self):
        with self.assertRaises(ValueError):
            TimeWheel(slots=1, tick=1.0, clock=ManualClock(0.0))
        with self.assertRaises(ValueError):
            TimeWheel(slots=8, tick=0.0, clock=ManualClock(0.0))
        with self.assertRaises(ValueError):
            TimeWheel(slots=8, tick=-1.0, clock=ManualClock(0.0))


class GREEN_AdvanceAndDue(unittest.TestCase):
    """README 第 2/3 条：推进、迟到 tick、due 顺序（当前成立的部分）。"""

    def test_backwards_rejected(self):
        _, wheel = make_wheel()
        wheel.advance(3.0)
        with self.assertRaises(ValueError):
            wheel.advance(2.0)

    def test_sub_tick_advance_is_noop(self):
        _, wheel = make_wheel()
        plant(wheel, "x", 1.0, 1)
        wheel.advance(0.999)
        self.assertEqual(wheel.now, 0.0)
        self.assertEqual(wheel.due(), [])

    def test_drain_one_slot_per_tick_in_add_order(self):
        _, wheel = make_wheel(slots=8)
        # 同槽同一次 drain：deadline 递增，追加序与到期序一致
        plant(wheel, "a", 1.0, 1)
        plant(wheel, "b", 1.4, 1)
        wheel.advance(1.0)
        self.assertEqual(wheel.due(), ["a", "b"])

    def test_multi_slot_advance_drains_each_once_in_order(self):
        _, wheel = make_wheel(slots=8)
        plant(wheel, "s2", 2.0, 2)
        plant(wheel, "s5a", 5.0, 5)
        plant(wheel, "s5b", 5.2, 5)
        wheel.advance(6.0)
        self.assertEqual(wheel.due(), ["s2", "s5a", "s5b"])

    def test_due_clears_queue_and_is_repeatable(self):
        _, wheel = make_wheel(slots=8)
        plant(wheel, "x", 1.0, 1)
        wheel.advance(1.0)
        self.assertEqual(wheel.due(), ["x"])
        self.assertEqual(wheel.due(), [])

    def test_late_deadline_still_fires(self):
        # 迟到不豁免：任务 deadline=1，直接推进到 6 也必须触发
        _, wheel = make_wheel(slots=8)
        plant(wheel, "late", 1.0, 1)
        wheel.advance(6.0)
        self.assertEqual(wheel.due(), ["late"])

    def test_advance_does_not_change_pending_deadline(self):
        _, wheel = make_wheel(slots=8)
        h = plant(wheel, "x", 2.0, 2)
        before = h.deadline
        wheel.advance(1.0)
        wheel.advance(2.0)
        self.assertEqual(h.deadline, before)
        self.assertEqual(wheel.due(), ["x"])

    def test_exact_fire_time_within_first_arc(self):
        # 性质：单调推进时任务恰好在其到期 tick 触发一次，不早不晚不重复
        _, wheel = make_wheel(slots=8)
        wheel.add(2.0, "a")
        wheel.add(5.0, "b")
        fired = []
        for t in range(1, 6):
            wheel.advance(float(t))
            fired.extend((t, task) for task in wheel.due())
        self.assertEqual(fired, [(2, "a"), (5, "b")])

    def test_small_steps_equal_big_step_within_first_arc(self):
        # 性质：不跨回绕、不经过最后槽时，小步推进与大步推进序列一致
        def run(big):
            _, wheel = make_wheel(slots=16)
            wheel.add(1.0, "a")
            wheel.add(3.0, "b")
            wheel.add(4.0, "c")
            if big:
                wheel.advance(6.0)
                return wheel.due()
            seq = []
            for t in range(1, 7):
                wheel.advance(float(t))
                seq.extend(wheel.due())
            return seq

        self.assertEqual(run(big=True), run(big=False))


class GREEN_Cancel(unittest.TestCase):
    """README 第 5 条：取消语义（当前成立的部分）。"""

    def test_cancel_pending_task_never_fires(self):
        _, wheel = make_wheel(slots=8)
        h = wheel.add(2.0, "x")
        self.assertTrue(h.cancel())
        wheel.advance(5.0)
        self.assertEqual(wheel.due(), [])

    def test_cancel_is_idempotent_returns_false_afterward(self):
        _, wheel = make_wheel(slots=8)
        h = wheel.add(2.0, "x")
        self.assertTrue(h.cancel())
        self.assertFalse(h.cancel())

    def test_cancel_after_taken_by_due_returns_false(self):
        _, wheel = make_wheel(slots=8)
        h = wheel.add(1.0, "x")
        wheel.advance(1.0)
        wheel.due()
        self.assertFalse(h.cancel())

    def test_cancel_pending_keeps_other_tasks_intact(self):
        _, wheel = make_wheel(slots=8)
        keep = wheel.add(1.0, "keep")
        gone = wheel.add(1.0, "gone")
        self.assertTrue(gone.cancel())
        wheel.advance(1.0)
        self.assertEqual(wheel.due(), ["keep"])
        self.assertFalse(keep.cancel())


class RED_AddSlotModulo(unittest.TestCase):
    """README 第 1 条钉红：槽下标必须 mod slots，最后一个槽照常参与回绕。"""

    # README 期望：槽位 = (cursor + ceil(delay/tick)) mod slots；
    # 实际发生：源码写成 mod (slots-1)，下标体系整体错位，最后槽永不被 add 命中。
    def test_full_revolution_delay_lands_on_last_then_wrap_to_zero(self):
        _, wheel = make_wheel(slots=8)
        h = wheel.add(8.0, "rev")
        self.assertEqual(h.slot, 0)

    # README 期望：delay=7、slots=8 时 ceil=7，任务落入最后槽 7；
    # 实际发生：(0+7) % 7 == 0，任务落进槽 0。
    def test_last_slot_index(self):
        _, wheel = make_wheel(slots=8)
        h = wheel.add(7.0, "last")
        self.assertEqual(h.slot, 7)

    # README 期望：delay=7 的任务 deadline=7，推进到 t=7 恰好触发一次；
    # 实际发生：任务被错放进槽 0，t=7 不触发，被推迟到下一圈（槽 0 在小步
    # 推进下永远不被 drain），触发时刻既错且重复语义也无法保证。
    def test_misplaced_task_fires_at_deadline(self):
        _, wheel = make_wheel(slots=8)
        wheel.add(7.0, "x")
        fired = []
        for t in range(1, 8):
            wheel.advance(float(t))
            fired.extend(wheel.due())
        self.assertEqual(fired, ["x"])


class RED_AdvanceWrap(unittest.TestCase):
    """README 第 2 条钉红：跨回绕点时被跨过的每个槽（含落点槽）恰好一次。"""

    # README 期望：cursor=6 一次 advance 到 10（跨过 7、0、1、2 四个槽），
    # 落点槽 2 中 deadline=10 的任务在 t=10 恰好进入就绪队列，迟到不豁免；
    # 实际发生：回绕分支的第二段 range(0, new_cursor) 漏掉落点槽 new_cursor，
    # 任务在 t=10 不触发，被遗留在槽 2，要再等一整圈到 t=18 才可能被收走。
    def test_wrap_advance_drains_landing_slot(self):
        _, wheel = make_wheel(slots=8, start=6.0)
        wheel._cursor = 6
        plant(wheel, "land", 10.0, 2)
        wheel.advance(10.0)
        self.assertEqual(wheel.due(), ["land"])
        self.assertEqual(
            [h.task for bucket in wheel._buckets for h in bucket], [])

    # README 期望：整圈任务在槽 0，advance 一整圈（跨过 1..7 和回绕点 0）
    # 后必须在 t=8 触发一次；实际发生：落点槽 0 同样被漏掉，任务滞留槽 0。
    def test_full_revolution_advance_drains_slot_zero(self):
        _, wheel = make_wheel(slots=8)
        plant(wheel, "rev", 8.0, 0)
        wheel.advance(8.0)
        self.assertEqual(wheel.due(), ["rev"])


class RED_DedupAndOrder(unittest.TestCase):
    """README 第 3/4 条钉红：同 deadline 不合并；due 按追加顺序。"""

    # README 期望：相同 delay 的两次 add 是两个独立任务，到期都必须出现；
    # 实际发生：就绪队列是 _ready={deadline: handle} 字典，后一个按相同
    # deadline 键覆盖前一个，第一个任务被静默吞掉。
    def test_same_deadline_tasks_both_appear(self):
        _, wheel = make_wheel(slots=32)
        wheel.add(1.0, "first")
        wheel.add(1.0, "second")
        wheel.advance(1.0)
        self.assertEqual(wheel.due(), ["first", "second"])

    # README 期望：同一槽被同一次 drain 收走的任务按加入顺序追加，due 也按
    # 加入顺序返回（README 明确「顺序与追加顺序一致」）；
    # 实际发生：due 用 sorted(_ready) 按 deadline 数值重排，而槽内允许
    # ceil 后同槽、deadline 不同的任务，加入顺序被破坏。
    def test_due_preserves_append_order_within_slot(self):
        _, wheel = make_wheel(slots=32)
        wheel.add(2.0, "added-first")
        wheel.add(1.5, "added-second")
        wheel.advance(2.0)
        self.assertEqual(wheel.due(), ["added-first", "added-second"])


class RED_CancelReady(unittest.TestCase):
    """README 第 5 条钉红：已进就绪队列但尚未 due 取走的任务也能取消。"""

    # README 期望：任务已 drain 进就绪队列后 cancel 仍返回 True 且任务被移除，
    # 随后 due() 不得再返回它；实际发生：cancel 只在槽 bucket 里找句柄，
    # 找不到就返回 False，就绪队列里的任务无法取消、仍会被 due 取出执行。
    def test_cancel_task_already_in_ready_queue(self):
        _, wheel = make_wheel(slots=8)
        h = wheel.add(1.0, "x")
        wheel.advance(1.0)
        self.assertTrue(h.cancel())
        self.assertEqual(wheel.due(), [])


class PropertySmallVsBigAcrossWrap(unittest.TestCase):
    """性质钉红：多次小步推进与一次大步推进到同一时刻，触发序列完全一致。"""

    # README 期望：advance 只按最终时刻收集到期任务，推进路径无关，两种推进
    # 方式触发序列完全一致，且任务都在其到期时刻 t=7 触发；
    # 实际发生：delay=7 的任务被错放进槽 0（add 取模缺陷），而槽 0 只在
    # 大步跨回绕时被 drain、逐 tick 小步推进永不经过槽 0——小步序列为空，
    # 大步序列在 t=9 才触发，序列与触发时刻双双不一致。
    def test_small_steps_match_single_big_step_across_wrap(self):
        def run(big):
            _, wheel = make_wheel(slots=8)
            wheel.add(7.0, "x")
            if big:
                wheel.advance(9.0)
                return wheel.due()
            seq = []
            for t in range(1, 10):
                wheel.advance(float(t))
                seq.extend(wheel.due())
            return seq

        self.assertEqual(run(big=False), run(big=True))
        # 同时钉死「恰好在到期时刻 t=7」
        _, wheel = make_wheel(slots=8)
        wheel.add(7.0, "x")
        fired_at = []
        for t in range(1, 10):
            wheel.advance(float(t))
            for _ in wheel.due():
                fired_at.append(t)
        self.assertEqual(fired_at, [7])


class PropertyDifferentialSafe(unittest.TestCase):
    """性质（绿）：无缺陷子空间内，时间轮与朴素参考模型完全等价。

    固定 seed 随机交错 add/cancel/advance，覆盖不回绕的多槽大步推进；
    触发顺序、触发次数、cancel 返回值、最终剩余任务逐操作对齐。
    """

    SEEDS = (0, 1, 2, 3, 4, 7, 13, 42, 99, 1234)

    def test_matches_naive_reference_in_safe_subspace(self):
        for seed in self.SEEDS:
            self.assertIsNone(
                run_scenario(seed, safe=True),
                msg="safe subspace diverged at seed=%d" % seed)


class PropertyDifferentialFull(unittest.TestCase):
    """性质（红）：全域随机交错序列与朴素参考模型对拍。

    README 期望：全域（含整圈 delay、同 deadline、就绪队列取消、大步跨多槽
    跨回绕）下，时间轮触发顺序、次数与最终剩余任务都与朴素参考一致；
    实际发生：固定 seed 的序列在 add 取模、回绕漏槽、同 deadline 覆盖、
    就绪队列不可取消等处与参考模型分歧，首个分歧随断言信息一并钉出。
    """

    SEED = 20260920

    def test_matches_naive_reference_over_full_domain(self):
        divergence = run_scenario(self.SEED, slots=8, n=300, safe=False)
        self.assertIsNone(divergence)


if __name__ == "__main__":
    unittest.main(verbosity=2)
