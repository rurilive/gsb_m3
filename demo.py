"""DeadLetterQueue 演示。

前两段：消费失败沉入死信、下游修好后整体重放捞回（现状基线）。
后两段：按失败原因分组与定向重放；保留期与容量上限触发归档。
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

    class DecodeError(Exception):
        """反序列化炸。"""

    class TimeoutError(Exception):
        """超时炸。"""

    class GroupedConsumer:
        """按 id 路由异常类型的消费者，broken 可随时改动。"""

        def __init__(self, broken):
            self.broken = dict(broken)

        def __call__(self, msg):
            mid = msg["id"]
            if mid in self.broken:
                raise self.broken[mid](f"boom {mid}")
            print(f"    处理 {mid} payload={msg['payload']}")

    class ManualClock:
        """可手动推进的注入时钟，便于精确演示归档时刻。"""

        def __init__(self, start=1000.0):
            self.now = start

        def __call__(self):
            return self.now

        def advance(self, delta):
            self.now += delta

    clock = ManualClock()
    gconsumer = GroupedConsumer({})
    gq = DeadLetterQueue(gconsumer, max_retries=2, clock=clock,
                         retention=100.0)
    failures = {
        "d1": DecodeError, "t1": TimeoutError,
        "d2": DecodeError, "t2": TimeoutError,
    }
    for mid, exc_type in failures.items():
        gconsumer.broken[mid] = exc_type
        for _ in range(2):
            gq.consume({"id": mid, "payload": {"n": mid[1:]}})
    for reason, records in gq.dead_groups().items():
        ids = [r["msg"]["id"] for r in records]
        print(f"  堆 {reason}: {ids}")

    print("=== 只重放反序列化那一堆（超时那堆不碰） ===")
    print("  d1 仍坏：退回原堆，attempts 接着往上加（不重置）")
    gconsumer.broken.pop("d2")  # d2 修好，d1 还没修
    recovered = gq.replay_group("DecodeError")
    left = gq.dead_groups()["DecodeError"][0]
    print(f"  恢复 {recovered} 条；{left['msg']['id']} 留在 "
          f"{left['reason']} 堆，attempts={left['attempts']}，"
          f"仍可翻回 payload={left['msg']['payload']}")
    print("  超时堆原样：",
          [r["msg"]["id"] for r in gq.dead_groups()["TimeoutError"]])
    gconsumer.broken.pop("d1")
    recovered = gq.replay_group("DecodeError")
    print(f"  d1 修好后再重放：恢复 {recovered} 条，"
          f"反序列化堆剩余 {gq.dead_groups().get('DecodeError', [])}")

    print("=== 保留期到期：推进注入时钟后归档、按组可查 ===")
    clock.advance(100.0)  # t1/t2 的 dead_at=1000，正好达到保留期
    swept = gq.sweep_retention()
    print(f"  清走 {swept} 条，死信区剩余 {len(gq.dead())} 条")
    archived = gq.archived("TimeoutError")
    for rec in archived:
        print(f"  归档 {rec['msg']['id']} reason={rec['reason']} "
              f"cause={rec['cause']} dead_at={rec['dead_at']} "
              f"archived_at={rec['archived_at']}")

    print("=== 容量上限：新死信满了把最老的挪进归档 ===")
    cap_clock = ManualClock(start=2000.0)
    cap_consumer = GroupedConsumer({})
    cq = DeadLetterQueue(cap_consumer, max_retries=1,
                         clock=cap_clock, max_dead=2)
    for mid, exc_type in (("c1", DecodeError), ("c2", TimeoutError),
                          ("c3", DecodeError)):
        cap_consumer.broken[mid] = exc_type
        cq.consume({"id": mid, "payload": {"n": mid[1:]}})
    print("  死信区（容量 2，c1 最老被挤出）：",
          [r["msg"]["id"] for r in cq.dead()])
    for rec in cq.archived("DecodeError"):
        print(f"  归档 {rec['msg']['id']} reason={rec['reason']} "
              f"cause={rec['cause']} archived_at={rec['archived_at']}")


if __name__ == "__main__":
    main()
