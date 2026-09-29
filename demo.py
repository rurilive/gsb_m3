"""jobrig 演示。

第一段：朴素先进先出工作队列的入队、出队与窥视。
第二段：预留的依赖调度与抢占演示位子（见文末注释）。
"""

from jobrig.queue import FifoQueue


def main():
    print("=== 先进先出工作队列 ===")
    q = FifoQueue()
    for name in ("alpha", "beta", "gamma"):
        q.push(name)
    print("  入队后队列长度:", len(q))
    print("  peek 看一眼队首:", q.peek())
    print("  依次出队:", [q.pop(), q.pop(), q.pop()])
    print("  空队列出队:", q.pop())

    # TODO(调度器改造): 依赖调度与抢占实现后，在这里加一段演示：
    # 先声明 a -> b -> c 的依赖链，只有前置成功后继才就绪，
    # 再放入低优先级任务与高优先级任务，观察高优先级先被取走。


if __name__ == "__main__":
    main()
