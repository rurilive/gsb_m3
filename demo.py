"""weightsem 现状演示。

第一段：拿一把普通计数信号量，连续取几个许可，看可用与已持有怎么变，
再在取空之后取一次，看它怎么报错；
第二段：预留的加权获取与超时演示位子（见文末注释）。
"""

from weightsem.semaphore import Semaphore, SemaphoreBusy


def main():
    print("=== 普通计数信号量 ===")
    sem = Semaphore(3)
    print("  初始 可用 %d 已持有 %d 总数 %d"
          % (sem.available, sem.held, sem.capacity))
    sem.acquire()
    print("  取一个后 可用 %d 已持有 %d" % (sem.available, sem.held))
    sem.acquire()
    print("  再取一个后 可用 %d 已持有 %d" % (sem.available, sem.held))
    try:
        sem.acquire()
        sem.acquire()
    except SemaphoreBusy as exc:
        print("  取空之后还被取: %s" % (exc,))
    print("  此刻 可用 %d 已持有 %d" % (sem.available, sem.held))
    sem.release()
    print("  还回一个后 可用 %d 已持有 %d" % (sem.available, sem.held))

    # TODO(加权与超时): 在 weightsem 里补出带注入时钟的加权信号量之后，在这里加一段
    # 演示：用同一个持有者连续 acquire 不同的权重，打印每次之后可用与已持有怎么变，看
    # 出可重入是累加到同一个持有者身上的；再让一个请求要的许可超过剩余可用，推进注入
    # 时钟跨过 timeout，捕获抛出的超时异常并打印，随后打印可用许可与等待者数量，确认
    # 这次超时的请求没有占走任何许可；最后演示一次容量缩容，打印缩小容量之后已持有与
    # 可用仍然满足持有加已用不超过容量。


if __name__ == "__main__":
    main()