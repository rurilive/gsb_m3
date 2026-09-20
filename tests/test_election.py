"""FileLockElection 行为基线。

这些断言描述的是线上已经在依赖的语义：同一时刻只有一个主、锁文件里记着
持有者、held_since 取自注入的时钟、让位后主位可被接手。重构内部实现时
它们必须原样全绿。
"""
import os
import tempfile
import unittest

from lease import FileLockElection


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class ElectionCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "primary.lock")
        self.clock = FakeClock()

    def make(self, node_id):
        return FileLockElection(self.path, node_id, self.clock)


class TestAcquire(ElectionCase):
    def test_first_acquire_wins(self):
        a = self.make("node-a")
        self.assertFalse(a.is_primary())
        self.assertTrue(a.try_acquire())
        self.assertTrue(a.is_primary())

    def test_second_node_is_refused_while_held(self):
        a = self.make("node-a")
        b = self.make("node-b")
        self.assertTrue(a.try_acquire())
        self.assertFalse(b.try_acquire())
        self.assertFalse(b.is_primary())

    def test_reacquire_by_holder_is_idempotent(self):
        a = self.make("node-a")
        self.assertTrue(a.try_acquire())
        self.clock.t = 1042.0
        self.assertTrue(a.try_acquire())
        self.assertEqual(a.held_since, 1000.0)

    def test_node_id_is_exposed(self):
        self.assertEqual(self.make("node-a").node_id, "node-a")


class TestRelease(ElectionCase):
    def test_release_hands_primary_to_standby(self):
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        a.release()
        self.assertFalse(a.is_primary())
        self.assertIsNone(a.held_since)
        self.assertTrue(b.try_acquire())
        self.assertTrue(b.is_primary())

    def test_release_is_idempotent(self):
        a = self.make("node-a")
        a.release()                        # 从来没有成为过主
        a.try_acquire()
        a.release()
        a.release()
        self.assertFalse(a.is_primary())

    def test_holder_can_take_back_after_release(self):
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        a.release()
        b.try_acquire()
        self.assertFalse(a.try_acquire())  # 现在轮到 b 了

    def test_crashed_holder_frees_the_lock(self):
        """持有者进程崩掉（fd 被关）后，主位必须能被别人接手。"""
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        os.close(a._fd)                    # 模拟进程异常退出
        a._fd = None
        self.assertTrue(b.try_acquire())

    def test_context_manager_releases(self):
        a = self.make("node-a")
        b = self.make("node-b")
        with a:
            a.try_acquire()
            self.assertFalse(b.try_acquire())
        self.assertTrue(b.try_acquire())


class TestHolder(ElectionCase):
    def test_held_since_uses_injected_clock(self):
        self.clock.t = 1234.5
        a = self.make("node-a")
        a.try_acquire()
        self.assertEqual(a.held_since, 1234.5)

    def test_held_since_is_none_before_acquire(self):
        self.assertIsNone(self.make("node-a").held_since)

    def test_current_holder_reads_lock_file(self):
        a = self.make("node-a")
        self.assertIsNone(a.current_holder())
        a.try_acquire()
        self.assertEqual(a.current_holder(), "node-a")

    def test_current_holder_survives_other_instance(self):
        a = self.make("node-a")
        a.try_acquire()
        b = self.make("node-b")
        self.assertEqual(b.current_holder(), "node-a")
        b.try_acquire()
        self.assertEqual(b.current_holder(), "node-a")  # b 没抢到，持有者不变

    def test_held_since_resets_on_reacquire(self):
        a = self.make("node-a")
        a.try_acquire()
        a.release()
        self.clock.t = 2000.0
        a.try_acquire()
        self.assertEqual(a.held_since, 2000.0)


if __name__ == "__main__":
    unittest.main()
