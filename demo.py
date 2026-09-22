"""revcache 现状演示：读写撞在一起时的几个现场。

场景不靠 sleep 赌时序：数据源的读延迟走注入的 sleep 桩，把慢读按在
回源里停住，再让写或删插进来，然后打印两边各自看到的结果。带“期望”
的行是修好之后该有的样子，跑在现在的代码上多半对不上。

运行：python3 demo.py
"""

import threading
import time

from revcache import Backend, CacheError, CachedStore, TransientError, ValueCache


class GateSleep:
    """注入给 Backend 的 sleep 桩。

    被调用（也就是有人正卡在回源里）时记录下来并停住，等外部放行才
    返回，这样演示就能把并发时序摆准，不用猜。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.inside = 0
        self.release = threading.Event()

    def __call__(self, seconds):
        with self._lock:
            self.inside += 1
        self.release.wait(5.0)

    def wait_inside(self, count, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.inside >= count:
                    return True
            time.sleep(0.005)
        return False

    def open(self):
        self.release.set()


def demo_slow_read_writes_back_stale():
    print("=== 1. 慢读把改前的老值回填进缓存 ===")
    gate = GateSleep()
    backend = Backend(sleep=gate)
    store = CachedStore(backend, ValueCache())
    store.write("price:1001", 19.9)
    backend.inject_latency(0.05, key="price:1001")

    reader = threading.Thread(target=store.read, args=("price:1001",))
    reader.start()
    gate.wait_inside(1)                # 读线程已经拿着老值卡在回源里
    store.write("price:1001", 24.5)    # 写者更新数据源并清掉缓存
    gate.open()
    reader.join()

    print("  数据源现在的值:", backend.get("price:1001"))
    print("  再读一次        :", store.read("price:1001"), "（期望 24.5）")


def demo_cold_key_load_amplification():
    print()
    print("=== 2. 缓存刚清空，读线程各回各的源 ===")
    gate = GateSleep()
    backend = Backend(sleep=gate)
    store = CachedStore(backend, ValueCache())
    store.write("price:1002", 7.0)
    store.cache.invalidate("price:1002")
    backend.inject_latency(0.05, key="price:1002")

    readers = [threading.Thread(target=store.read, args=("price:1002",))
               for _ in range(8)]
    for thread in readers:
        thread.start()
    gate.wait_inside(1)   # 第一个读已在回源里，其余几个还没回源或已排在它后面
    time.sleep(0.02)
    gate.open()
    for thread in readers:
        thread.join()

    print("  8 个并发读，数据源被读次数:", backend.stats()["reads"],
          "（期望 1）")


def demo_failed_load_is_cached():
    print()
    print("=== 3. 回源失败被当成结果缓存下来 ===")
    backend = Backend()
    store = CachedStore(backend, ValueCache())
    store.write("price:1003", 5.0)
    backend.inject_fault("price:1003", count=1)
    try:
        store.read("price:1003")
    except TransientError:
        print("  第一次读: TransientError")
    print("  重试    :", store.read("price:1003"), "（期望 5.0）")


def demo_cache_write_failure_breaks_read():
    print()
    print("=== 4. 缓存写不进去时读接口跟着报错 ===")
    backend = Backend()
    store = CachedStore(backend, ValueCache())
    store.write("price:1004", 3.0)
    store.cache.inject_write_faults(1)
    try:
        value = store.read("price:1004")
    except CacheError as exc:
        print("  读数据源是好的，读接口却抛了:", exc, "（期望返回 3.0）")
    else:
        print("  读接口返回:", value)


def main():
    demo_slow_read_writes_back_stale()
    demo_cold_key_load_amplification()
    demo_failed_load_is_cached()
    demo_cache_write_failure_breaks_read()
    print()
    print("演示结束")


if __name__ == "__main__":
    main()
