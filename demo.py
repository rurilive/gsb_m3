"""DeadLetterQueue 现状演示。

第一段：消费失败沉入死信，下游修好后整体重放捞回。
第二段：预留的分组重放与归档演示位子（见文末注释）。
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

    # TODO(分类与归档): 分组沉淀、定向重放、TTL 与容量归档落地后，在这里加一段演示：
    # 让不同 id 以不同异常类型失败，展示按组沉淀的结果；只重放其中一组，
    # 让该组里没修好的消息退回原组并看到重试计数继续累加；
    # 再用注入时钟推进时间，演示超保留期的死信被归档、归档按组可查。


if __name__ == "__main__":
    main()
