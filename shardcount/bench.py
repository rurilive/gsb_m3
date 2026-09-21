"""吞吐基准：同一台机器上同场比不同计数器的热键递增吞吐。

measure 让 threads 个线程围着热键打点，跑 seconds 秒，返回每秒操作数
（多轮取最好，抹掉调度噪声）；candidates 列出进比对的实现，以后加了新
实现在这里登记一行就能进表，表里给出相对单锁基线的倍数。
"""

import time
import threading

from shardcount.counter import LockCounter

DEFAULT_THREADS = (1, 2, 4, 8)
DEFAULT_SECONDS = 1.0
DEFAULT_TRIALS = 2
HOT_KEY = "hot"


def _run_once(make_counter, threads, seconds, key, sleep):
    counter = make_counter()
    stop = threading.Event()
    counts = [0] * threads

    def work(index):
        ops = 0
        incr = counter.incr
        while not stop.is_set():
            incr(key)
            ops += 1
        counts[index] = ops

    workers = [threading.Thread(target=work, args=(i,)) for i in range(threads)]
    started = time.perf_counter()
    for worker in workers:
        worker.start()
    sleep(seconds)
    stop.set()
    for worker in workers:
        worker.join()
    elapsed = time.perf_counter() - started
    return sum(counts) / elapsed


def measure(make_counter, threads, seconds=DEFAULT_SECONDS, key=HOT_KEY,
            trials=DEFAULT_TRIALS, sleep=time.sleep):
    """量 threads 个线程对同一个热键递增的吞吐，返回每秒操作数。"""
    return max(
        _run_once(make_counter, threads, seconds, key, sleep)
        for _ in range(trials)
    )


def candidates():
    """进比对的实现列表：(名字, 建计数器的可调用对象)。"""
    return [
        ("lock", LockCounter),
    ]


def main(threads=DEFAULT_THREADS, seconds=DEFAULT_SECONDS, trials=DEFAULT_TRIALS):
    print("热键递增吞吐，%g 秒一轮、%d 轮取最好" % (seconds, trials))
    print("%-12s" % "实现" + "".join("%14s" % ("%d 线程" % t) for t in threads))
    baseline = None
    for name, make_counter in candidates():
        cells = [measure(make_counter, t, seconds=seconds, trials=trials) for t in threads]
        if baseline is None:
            baseline = cells
        line = "%-12s" % name + "".join("%14.0f" % c for c in cells)
        line += "   相对单锁 " + " ".join("%.2fx" % (c / b) for c, b in zip(cells, baseline))
        print(line)


if __name__ == "__main__":
    main()
