"""poolx 现状演示。

第一段：用朴素同步执行器提交若干纯函数任务，查看结果、下标与等待口径。
第二段：预留的并发改造演示位子（见文末注释）。
"""

from poolx.pool import SyncPool


def _square(x):
    return x * x


def _double(x):
    return x + x


def main():
    print("=== 朴素同步执行器（现有能力） ===")
    pool = SyncPool()
    i0 = pool.submit(_square, 3)
    i1 = pool.submit(_double, 3)
    i2 = pool.submit(_square, -4)
    print("  提交下标         -> {} {} {}".format(i0, i1, i2))
    print("  results()        -> {}".format(pool.results()))
    print("  get(1)           -> {}".format(pool.get(1)))
    print("  size()           -> {}".format(pool.size()))
    print("  wait() 返回      -> {}".format(pool.wait()))
    pool.shutdown()
    print("  shutdown() 之后 size -> {}".format(pool.size()))

    # TODO: 第二段演示（实现后补）
    # 线程池与结果凭据改造完成后，在这里补一轮演示：
    # 一次性提交一批纯函数任务，等全部完成后逐个凭据取结果并与顺序执行对照；
    # 再提交一个必然抛异常的任务，展示取结果时原样抛出且不影响其它任务；
    # 最后关闭执行器，演示关闭后再提交会被快速拒绝。


if __name__ == "__main__":
    main()
