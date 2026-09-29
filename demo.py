"""boundedq 演示。

第一段：朴素无界先进先出队列的入队、出队与窥视。
第二段：预留的有界背压与关闭演示位子（见文末注释）。
"""

from boundedq.queue import FifoQueue


def main():
    print("=== 无界先进先出队列 ===")
    q = FifoQueue()
    for name in ("alpha", "beta", "gamma"):
        q.push(name)
    print("  入队后长度:", len(q))
    print("  peek 看一眼队首:", q.peek())
    print("  依次出队:", [q.pop(), q.pop(), q.pop()])
    print("  空队列出队:", q.pop())

    # TODO(有界队列改造): 有界背压与关闭语义实现后，在这里加一段演示：
    # 建一个容量固定的小队列，先塞满，再放一个生产者观察它被背压卡住，
    # 消费者取走一个后生产者得以继续；随后关闭队列，演示入队被拒，
    # 而已经入队的元素仍能被消费者逐个取完，取空后取出返回结束标注。


if __name__ == "__main__":
    main()