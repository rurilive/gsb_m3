"""primesieve 现状演示。

第一段：给定上界，用逐数试除求素数、分解若干整数、求欧拉函数值、
统计某区间素数个数，并打印累计试除次数；
第二段：预留的线性筛与快速分解演示位子（见文末注释）。
"""

from primesieve.sieve import Sieve


def main():
    print("=== 朴素逐数试除 ===")
    s = Sieve(50)
    s.reset_counts()
    print("  上界 %d 以内的素数 -> %s" % (s.upper(), s.primes()))
    for x in (1, 2, 12, 97, 128):
        print("  %d 的质因子 -> %s" % (x, s.factorize(x)))
    print("  720 的质因子 -> %s" % (s.factorize(720),))
    print("  分解一批 -> %s" % (s.factorize_all([10, 49, 100]),))
    print("  1 到 20 的欧拉函数值 -> %s"
          % (tuple(s.euler_phi(x) for x in range(1, 21)),))
    print("  [2, 30] 内素数个数 -> %d" % s.count_primes(2, 30))
    print("  累计试除次数 -> %d" % s.trial_divisions())

    # TODO: 第二段演示（实现后补）
    #
    # 在 primesieve 里补出线性筛与最小质因子表之后，在这里加一段演示：
    # 先对同一个上界做一次线性筛，取回全部素数并与上面逐数试除的结果逐项
    # 对照；再据最小质因子表做一次近似对数级的快速分解，与上面反复试除的
    # 分解结果对照；接着对欧拉函数值、区间素数个数、批量分解逐项核对两条
    # 路是否一致；然后打印线性筛的标记次数与逐数试除次数的差距；最后覆盖
    # 上界为零或一、上界为素数、素数幂、含大素因子、分解一和零等边界。


if __name__ == "__main__":
    main()
