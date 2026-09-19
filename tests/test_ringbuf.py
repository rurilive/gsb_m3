"""ringbuf 防回归测试：覆盖计数、去重、丢失、顺序四类历史缺陷及并发场景。"""

import threading
import unittest

from ringbuf import Empty, RingBuffer


class TestBasicSemantics(unittest.TestCase):
    def test_count_never_exceeds_capacity_on_overwrite(self):
        rb = RingBuffer(3)
        for i in range(100):
            rb.put(i)
            self.assertLessEqual(rb.count(), 3)
        self.assertEqual(rb.count(), 3)

    def test_overwrite_evicts_oldest(self):
        rb = RingBuffer(3)
        for c in "abcde":
            rb.put(c)
        self.assertEqual(rb.snapshot(), ["c", "d", "e"])
        self.assertEqual([rb.get(), rb.get(), rb.get()], ["c", "d", "e"])

    def test_get_empty_raises(self):
        rb = RingBuffer(2)
        with self.assertRaises(Empty):
            rb.get()
        rb.put("x")
        rb.get()
        with self.assertRaises(Empty):
            rb.get()

    def test_count_returns_to_zero_after_drain(self):
        rb = RingBuffer(4)
        for i in range(10):
            rb.put(i)
        while rb.count():
            rb.get()
        self.assertEqual(rb.count(), 0)

    def test_no_message_lost_when_not_full(self):
        # 交织读写让游标多次回绕，覆盖物理缓冲区每一个槽位
        rb = RingBuffer(5)
        expected = []
        for i in range(200):
            rb.put(i)
            expected.append(i)
            if len(expected) >= 3:
                for want in expected[:2]:
                    self.assertEqual(rb.get(), want)
                expected = expected[2:]
        for want in expected:
            self.assertEqual(rb.get(), want)
        self.assertEqual(rb.count(), 0)


class TestSnapshot(unittest.TestCase):
    def test_snapshot_matches_write_order(self):
        rb = RingBuffer(4)
        for c in "abcdef":
            rb.put(c)
        self.assertEqual(rb.snapshot(), ["c", "d", "e", "f"])

    def test_snapshot_after_partial_drain(self):
        rb = RingBuffer(4)
        for c in "abcdef":
            rb.put(c)
        self.assertEqual(rb.get(), "c")
        rb.put("g")
        self.assertEqual(rb.snapshot(), ["d", "e", "f", "g"])

    def test_snapshot_does_not_mutate(self):
        rb = RingBuffer(3)
        for c in "abc":
            rb.put(c)
        snap = rb.snapshot()
        self.assertEqual(rb.count(), 3)
        self.assertEqual(rb.snapshot(), snap)
        snap.append("x")
        self.assertEqual(rb.snapshot(), ["a", "b", "c"])


class TestConcurrency(unittest.TestCase):
    def test_no_duplicate_and_no_loss_with_large_capacity(self):
        # 容量大于消息总量：每条消息必须恰好被一个消费者取到
        n_producers, n_consumers, per_producer = 4, 4, 2000
        total = n_producers * per_producer
        rb = RingBuffer(total + 1)
        received = []
        received_lock = threading.Lock()
        done_producers = threading.Semaphore(0)

        def producer(pid):
            for i in range(per_producer):
                rb.put((pid, i))
            done_producers.release()

        def consumer():
            got = []
            while True:
                try:
                    got.append(rb.get())
                except Empty:
                    if done_producers.acquire(blocking=False):
                        done_producers.release()
                        if rb.count() == 0:
                            break
            with received_lock:
                received.extend(got)

        producers = [threading.Thread(target=producer, args=(p,)) for p in range(n_producers)]
        consumers = [threading.Thread(target=consumer) for _ in range(n_consumers)]
        for t in producers + consumers:
            t.start()
        for t in producers + consumers:
            t.join()

        self.assertEqual(len(received), total, "消息丢失或数量不符")
        self.assertEqual(len(set(received)), total, "存在重复消费")
        self.assertEqual(rb.count(), 0)

    def test_count_bounded_under_overwrite_stress(self):
        # 小容量高压覆盖：count 始终落在 [0, capacity]，最终可完整排空
        capacity = 8
        rb = RingBuffer(capacity)
        stop = threading.Event()
        violations = []

        def producer(pid):
            i = 0
            while not stop.is_set():
                rb.put((pid, i))
                i += 1

        def consumer():
            while not stop.is_set():
                try:
                    rb.get()
                except Empty:
                    pass
                c = rb.count()
                if not (0 <= c <= capacity):
                    violations.append(c)

        threads = [threading.Thread(target=producer, args=(p,)) for p in range(3)]
        threads += [threading.Thread(target=consumer) for _ in range(3)]
        for t in threads:
            t.start()
        threading.Event().wait(1.0)
        stop.set()
        for t in threads:
            t.join()

        self.assertEqual(violations, [], f"count 越界: {violations[:5]}")
        drained = 0
        try:
            while True:
                rb.get()
                drained += 1
        except Empty:
            pass
        self.assertEqual(drained, rb.count() + drained)  # 排空后不再残留
        self.assertEqual(rb.count(), 0)
        self.assertEqual(rb.snapshot(), [])

    def test_snapshot_consistent_under_concurrent_writes(self):
        rb = RingBuffer(16)
        stop = threading.Event()
        errors = []

        def producer():
            i = 0
            while not stop.is_set():
                rb.put(i)
                i += 1

        def reader():
            while not stop.is_set():
                snap = rb.snapshot()
                if len(snap) != rb.count():
                    errors.append("snapshot 长度与 count 不一致")
                if any(x is None for x in snap):
                    errors.append("snapshot 含空洞")

        threads = [threading.Thread(target=producer) for _ in range(2)]
        threads += [threading.Thread(target=reader) for _ in range(2)]
        for t in threads:
            t.start()
        threading.Event().wait(1.0)
        stop.set()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"snapshot 异常: {errors[:3]}")


if __name__ == "__main__":
    unittest.main()
