"""演示：提交几个延时任务，随时钟推进逐个到期。"""
from delayq import DelayedQueue, FakeClock


def main():
    clock = FakeClock(start=100.0)
    q = DelayedQueue(clock=clock)

    q.add(lambda: print("  [A] 整点报表            t=%.0f" % clock.monotonic()), delay=2.0)
    q.add(lambda: print("  [B] 缓存清理            t=%.0f" % clock.monotonic()), delay=2.0)
    q.add(lambda: print("  [C] 健康检查            t=%.0f" % clock.monotonic()), delay=5.0)
    q.add(lambda: print("  [D] 会话续期            t=%.0f" % clock.monotonic()), delay=2.0, key="renew")
    q.add(lambda: print("  [D'] 会话续期(重复提交)  t=%.0f" % clock.monotonic()), delay=2.0, key="renew")

    print("=== 消费循环：每推进 1 秒轮询一次 ===")
    for _ in range(6):
        clock.advance(1.0)
        while True:
            task = q.pop_ready()
            if task is None:
                break
            task()
        wait = q.peek()
        print("  t=%.0f 剩余 %d 个, peek=%s" % (
            clock.monotonic(), len(q), "None" if wait is None else "%.1f" % wait))

    print("演示结束")


if __name__ == "__main__":
    main()
