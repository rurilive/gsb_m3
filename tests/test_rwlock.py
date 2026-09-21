"""RWLock 行为的锁定测试。"""

import threading
import time
import unittest

from bucketmap.rwlock import RWLock

PAUSE = 0.05


def in_thread(target):
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def probe(mode, flag):
    """返回一个进锁后置位 flag 的线程函数。"""
    def target():
        with mode():
            flag.set()
    return target


def blocked(mode, flag):
    """在当前持锁状态下起线程，验证它进不去，返回该线程。"""
    thread = in_thread(probe(mode, flag))
    if flag.wait(PAUSE):
        raise AssertionError("线程没有在等锁")
    return thread


class TestExclusion(unittest.TestCase):
    def test_two_readers_hold_at_once(self):
        lock = RWLock()
        entered = threading.Barrier(3)
        errors = []

        def reader():
            try:
                with lock.read():
                    entered.wait(2)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [in_thread(reader) for _ in range(2)]
        try:
            entered.wait(2)
        except threading.BrokenBarrierError:  # pragma: no cover
            pass
        for thread in threads:
            thread.join(2)
        self.assertEqual(errors, [])
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(lock.reader_count(), 0)

    def test_writer_and_reader_mutually_wait(self):
        lock = RWLock()
        inside = threading.Event()
        with lock.read():
            writer = blocked(lock.write, inside)
        self.assertTrue(inside.wait(2))
        writer.join(2)
        inside.clear()
        with lock.write():
            reader = blocked(lock.read, inside)
        self.assertTrue(inside.wait(2))
        reader.join(2)

    def test_writer_preference_queues_new_readers(self):
        lock = RWLock()
        queued = threading.Event()
        writer_in = threading.Event()
        reader_in = threading.Event()

        def writer():
            queued.set()
            with lock.write():
                writer_in.set()

        with lock.read():
            in_thread(writer)
            self.assertTrue(queued.wait(2))
            time.sleep(PAUSE)          # 等写者排上队
            reader = in_thread(probe(lock.read, reader_in))
            self.assertFalse(reader_in.wait(PAUSE))
        self.assertTrue(writer_in.wait(2))   # 先轮到写者
        self.assertTrue(reader_in.wait(2))
        reader.join(2)

    def test_exception_releases_lock(self):
        lock = RWLock()
        with self.assertRaises(RuntimeError):
            with lock.write():
                raise RuntimeError("boom")
        with lock.write():
            pass
        with self.assertRaises(RuntimeError):
            with lock.read():
                raise RuntimeError("boom")
        with lock.read():
            pass
        self.assertEqual(lock.reader_count(), 0)


if __name__ == "__main__":
    unittest.main()
