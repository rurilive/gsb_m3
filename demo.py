"""DeadLetterQueue 演示。

第一段：消费失败沉入死信，下游修好后整体重放捞回。
第二段：按失败原因分组沉淀、定向重放、保留期与容量归档。
"""

from deadletter.queue import DeadLetterQueue


class Consumer:
    """按 id 决定成败的假消费者，broken 可随时改动。"""

    def __init__(self, broken):
        self.broken = set(broken)

    def __call__(self, msg):
        if msg["id"] in self.broken:
            raise ValueError("downstream rejected %s" % msg["id"])
        print(f"    处理 {msg['id']} payload={msg['payload']}")


class TypedConsumer:
    """按 id 抛指定异常的假消费者，errors 里没有的 id 视为成功。"""

    def __init__(self, errors):
        self.errors = dict(errors)

    def __call__(self, msg):
        exc = self.errors.get(msg["id"])
        if exc is not None:
            raise exc("downstream rejected %s" % msg["id"])
        print(f"    处理 {msg['id']} payload={msg['payload']}")


class FakeClock:
    """可手动推进的注入时钟。"""

    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


def main():
    print("=== 消费失败与死信沉淀（max_retries=2） ===")
    consumer = Consumer(["m1", "m2"])
    q = DeadLetterQueue(consumer, max_retries=2)
    for _ in range(2):
        q.consume({"id": "m1", "payload": {"n": 1}})
        q.consume({"id": "m2", "payload": {"n": 2}})
    for rec in q.dead():
        print(f"  死信 {rec['msg']['id']} attempts={rec['attempts']} "
              f"reason={rec['reason']} dead_at={rec['dead_at']}")

    print("=== 下游修好后整体重放 ===")
    consumer.broken.clear()
    recovered = q.retry_dead()
    print(f"  恢复 {recovered} 条，剩余死信 {len(q.dead())} 条")

    print("=== 按失败原因分组沉淀 ===")
    clock = FakeClock(1000.0)
    typed = TypedConsumer({"m3": ValueError, "m4": ValueError,
                           "m5": TimeoutError})
    q2 = DeadLetterQueue(typed, max_retries=1, retention=30.0, capacity=3,
                         clock=clock)
    for mid in ("m3", "m4", "m5"):
        q2.consume({"id": mid, "payload": {"n": mid}})
    print(f"  当前分组: {q2.groups()}")
    for rec in q2.dead_group("ValueError"):
        print(f"  [ValueError] {rec['msg']['id']} payload={rec['msg']['payload']} "
              f"attempts={rec['attempts']} detail={rec['detail']!r}")

    print("=== 只重放 ValueError 组（m3 已修，m4 仍坏） ===")
    del typed.errors["m3"]
    recovered = q2.replay("ValueError")
    print(f"  恢复 {recovered} 条，TimeoutError 组没被动: "
          f"{[r['msg']['id'] for r in q2.dead_group('TimeoutError')]}")
    for rec in q2.dead_group("ValueError"):
        print(f"  退回原组 {rec['msg']['id']} attempts={rec['attempts']} "
              f"reason={rec['reason']} dead_at={rec['dead_at']}")

    print("=== 时钟推进，超保留期的死信归档 ===")
    clock.advance(31.0)   # now=1031.0，死信沉淀于 1000.0，保留期 30
    print(f"  sweep 归档 {q2.sweep()} 条，剩余死信 {len(q2.dead())} 条")
    for rec in q2.archived():
        print(f"  归档[{rec['cause']}] {rec['msg']['id']} "
              f"reason={rec['reason']} dead_at={rec['dead_at']} "
              f"archived_at={rec['archived_at']}")

    print("=== 容量超限，最老的挪入归档 ===")
    clock2 = FakeClock(2000.0)
    full = TypedConsumer({"x1": ValueError, "x2": ValueError,
                          "x3": TimeoutError, "x4": TimeoutError})
    q3 = DeadLetterQueue(full, max_retries=1, capacity=2, clock=clock2)
    for mid in ("x1", "x2", "x3", "x4"):
        q3.consume({"id": mid, "payload": mid})
    clock2.advance(1.0)
    print(f"  sweep 归档 {q3.sweep()} 条，死信区剩 "
          f"{[r['msg']['id'] for r in q3.dead()]}")
    for group in q3.groups() + ["ValueError"]:
        for rec in q3.archived(group):
            print(f"  归档[{group}] {rec['msg']['id']} cause={rec['cause']} "
                  f"archived_at={rec['archived_at']}")


if __name__ == "__main__":
    main()
