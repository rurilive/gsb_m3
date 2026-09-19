"""ringbuf 防回归测试：覆盖计数、去重、丢消息、snapshot 顺序及并发场景。"""

import threading
import time
import unittest

from ringbuf import Empty, RingBuffer


class TestCountAndCapacity(unittest.TestCase):
    """现象 1：count 只涨不跌、超过容量。"""

    def test_count_never_exceeds_capacity_when_overwriting(self):
        rb = RingBuffer(3)
        for i in range(100):
            rb.put(i)
            self.assertLessEqual(rb.count(), 3)
        self.assertEqual(rb.count(), 3)

    def test_count_returns_to_zero_after_drain(self):
        rb = RingBuffer(4)
        for i in range(10):
            rb.put(i)
        for _ in range(4):
            rb.get()
        self.assertEqual(rb.count(), 0)
        with self.assertRaises(Empty):
            rb.get()
        self.assertEqual(rb.count(), 0)

    def test_count_tracks_interleaved_put_get(self):
        rb = RingBuffer(5)
        expected = 0
        for i in range(200):
            rb.put(i)
            expected = min(expected + 1, 5)
            self.assertEqual(rb.count(), expected)
            if i % 2 == 0 and expected > 0:
                rb.get()
                expected -= 1
                self.assertEqual(rb.count(), expected)


class TestNoDuplicateConsumption(unittest.TestCase):
    """现象 2：两个消费者拿到同一条消息。"""

    def test_each_item_consumed_exactly_once(self):
        capacity = 1000
        total = 20000
        rb = RingBuffer(capacity)
        received = []
        received_lock = threading.Lock()
        produced = {"n": 0}
        done_producing = threading.Event()

        def producer():
            for i in range(total):
                while rb.count() >= capacity:
                    time.sleep(0)
                rb.put(i)
                produced["n"] += 1
            done_producing.set()

        def consumer():
            while True:
                try:
                    item = rb.get()
                except Empty:
                    if done_producing.is_set() and rb.count() == 0:
                        return
                    time.sleep(0)
                    continue
                with received_lock:
                    received.append(item)

        threads = [threading.Thread(target=producer)]
        threads += [threading.Thread(target=consumer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(received), total)
        self.assertEqual(sorted(received), list(range(total)))


class TestNoMessageLoss(unittest.TestCase):
    """现象 3：缓冲未满时写入的消息丢失。"""

    def test_no_loss_below_capacity(self):
        rb = RingBuffer(10)
        for i in range(7):
            rb.put(i)
        self.assertEqual([rb.get() for _ in range(7)], list(range(7)))

    def test_no_loss_after_wraparound(self):
        rb = RingBuffer(4)
        for i in range(3):
            rb.put(i)
        self.assertEqual([rb.get() for _ in range(3)], [0, 1, 2])
        for i in range(3, 9):
            rb.put(i)
        self.assertEqual(rb.count(), 4)
        self.assertEqual([rb.get() for _ in range(4)], [5, 6, 7, 8])

    def test_overwrite_evicts_oldest_only(self):
        rb = RingBuffer(3)
        for i in range(6):
            rb.put(i)
        self.assertEqual(rb.snapshot(), [3, 4, 5])
        self.assertEqual([rb.get() for _ in range(3)], [3, 4, 5])


class TestSnapshotOrder(unittest.TestCase):
    """现象 4：snapshot 顺序与写入顺序对不上。"""

    def test_snapshot_matches_write_order(self):
        rb = RingBuffer(5)
        for ch in "abcde":
            rb.put(ch)
        self.assertEqual(rb.snapshot(), list("abcde"))

    def test_snapshot_matches_write_order_after_wraparound(self):
        rb = RingBuffer(3)
        for ch in "abcde":
            rb.put(ch)
        self.assertEqual(rb.snapshot(), list("cde"))

    def test_snapshot_matches_write_order_after_gets(self):
        rb = RingBuffer(4)
        for i in range(4):
            rb.put(i)
        self.assertEqual(rb.get(), 0)
        self.assertEqual(rb.get(), 1)
        rb.put(4)
        rb.put(5)
        self.assertEqual(rb.snapshot(), [2, 3, 4, 5])

    def test_snapshot_does_not_mutate(self):
        rb = RingBuffer(3)
        for i in range(5):
            rb.put(i)
        before = rb.snapshot()
        rb.snapshot()
        rb.snapshot()
        self.assertEqual(rb.snapshot(), before)
        self.assertEqual(rb.count(), 3)


class TestConcurrencyStress(unittest.TestCase):
    """并发压测：count 有界、无重复消费、无 None 泄漏。"""

    def test_mpmc_stress(self):
        capacity = 256
        producers = 4
        consumers = 4
        per_producer = 5000
        total = producers * per_producer
        rb = RingBuffer(capacity)
        received = []
        received_lock = threading.Lock()
        produced = {"n": 0}
        produced_lock = threading.Lock()
        violations = []

        def producer(pid):
            for i in range(per_producer):
                rb.put((pid, i))
                with produced_lock:
                    produced["n"] += 1

        def consumer():
            while True:
                try:
                    item = rb.get()
                except Empty:
                    with produced_lock:
                        done = produced["n"] >= total
                    if done and rb.count() == 0:
                        return
                    time.sleep(0)
                    continue
                if item is None:
                    violations.append("got None")
                with received_lock:
                    received.append(item)

        def monitor():
            for _ in range(2000):
                c = rb.count()
                if not 0 <= c <= capacity:
                    violations.append(f"count out of range: {c}")

        threads = [threading.Thread(target=producer, args=(p,)) for p in range(producers)]
        threads += [threading.Thread(target=consumer) for _ in range(consumers)]
        threads.append(threading.Thread(target=monitor))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(violations, [])
        # 缓冲会覆盖，收到的每条都必须唯一且属于已写入集合
        self.assertEqual(len(received), len(set(received)))
        for item in received:
            pid, seq = item
            self.assertTrue(0 <= pid < producers)
            self.assertTrue(0 <= seq < per_producer)
        self.assertEqual(rb.count(), 0)

    def test_count_consistent_after_concurrent_overwrite(self):
        capacity = 64
        rb = RingBuffer(capacity)
        stop = threading.Event()

        def writer():
            n = 0
            while not stop.is_set():
                rb.put(n)
                n += 1

        def reader():
            while not stop.is_set():
                try:
                    rb.get()
                except Empty:
                    pass

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        time.sleep(0.5)
        stop.set()
        for t in threads:
            t.join()

        # 排空后 count 必须精确归零
        drained = 0
        while True:
            try:
                rb.get()
                drained += 1
            except Empty:
                break
        self.assertEqual(rb.count(), 0)
        self.assertLessEqual(drained, capacity)


if __name__ == "__main__":
    unittest.main()
