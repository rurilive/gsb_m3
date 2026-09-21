"""放行吞吐基准与账本往返口径。

measure 让 threads 个线程围着同一个站点放名额，跑 seconds 秒，返回每秒
放行数（多轮取最好，抹掉调度噪声）；candidates 列出进比对的实现，以后加
了新实现在这里登记一行就能进表；round_trips 数账本流水里的动账次数，是
衡量同步开销的统一口径。纯标准库。
"""

import threading
import time

from slotledger.ledger import Ledger
from slotledger.site import Site

DEFAULT_THREADS = (1, 2, 4, 8)
DEFAULT_SECONDS = 1.0
DEFAULT_TRIALS = 2
POOL = 10 ** 9


def _run_once(make_site, threads, seconds, sleep):
    ledger = Ledger(total=POOL)
    site = make_site(ledger, "bench")
    stop = threading.Event()
    counts = [0] * threads

    def work(index):
        ops = 0
        admit = site.admit
        while not stop.is_set():
            admit(1)
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


def measure(make_site, threads, seconds=DEFAULT_SECONDS, trials=DEFAULT_TRIALS,
            sleep=time.sleep):
    """量 threads 个线程并发放名额的吞吐，返回每秒放行数。"""
    return max(
        _run_once(make_site, threads, seconds, sleep)
        for _ in range(trials)
    )


def candidates():
    """进比对的实现列表：(名字, 建站点的可调用对象)。"""
    return [
        ("naive", lambda ledger, name: Site(ledger, name)),
    ]


def round_trips(ledger, site=None):
    """账本流水里的动账次数，site 给定时时只数该站，衡量同步开销。"""
    entries = ledger.history()
    if site is not None:
        entries = [entry for entry in entries if entry.site == site]
    return sum(1 for entry in entries if entry.kind in ("grant", "retire"))


def main(threads=DEFAULT_THREADS, seconds=DEFAULT_SECONDS, trials=DEFAULT_TRIALS):
    print("并发放名额吞吐，%g 秒一轮、%d 轮取最好" % (seconds, trials))
    print("%-12s" % "实现" + "".join("%14s" % ("%d 线程" % t) for t in threads))
    for name, make_site in candidates():
        cells = [measure(make_site, t, seconds=seconds, trials=trials) for t in threads]
        line = "%-12s" % name + "".join("%14.0f" % c for c in cells)
        print(line)


if __name__ == "__main__":
    main()
