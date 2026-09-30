"""零钱兑换问题的朴素实现（改造前基线）。

只提供一条最直白的递归枚举路径：从目标金额出发，每一层都逐一尝试
每一枚可用的面值，把目标金额减去该面值后继续往下递归，直到金额降到
零或不能再减。结果永远算得对，但同一个子目标会被反复重算，代价随
目标金额指数级上涨。没有任何动态规划，也没有方案计数与可达性区分。
纯标准库，无外部依赖。
"""


class CoinChangeError(Exception):
    """零钱兑换参数错误的基类，继承自 Exception。"""


class NaiveCoinChange:
    """朴素零钱兑换：持有若干面值与目标金额。

    面值以列表给出，允许重复；对外一律把面值按升序、去重后的规范口径
    使用，重面值只算一枚。面值为正整数，可以无限次取用。

    结果用三元组表示，依次是最少硬币数、具体选法、是否可达：
    最少硬币数用一个非负整数给出，凑不出目标时按明确口径报告；
    具体选法是一串面值，按面值升序排列；
    是否可达用布尔值给出，与最少硬币数给不出时相区分。
    """

    def __init__(self, coins, target):
        coins = list(coins)
        for c in coins:
            if not isinstance(c, int) or isinstance(c, bool):
                raise CoinChangeError("coin must be an int")
            if c <= 0:
                raise CoinChangeError("coin must be positive")
        if not isinstance(target, int) or isinstance(target, bool):
            raise CoinChangeError("target must be an int")
        if target < 0:
            raise CoinChangeError("target must not be negative")
        self._coins = sorted(set(coins))
        self._target = target

    def __len__(self):
        return len(self._coins)

    @property
    def coins(self):
        """规范口径下的面值，升序且已去重。"""
        return list(self._coins)

    @property
    def target(self):
        return self._target

    def min_coins(self):
        """递归枚举每一枚可用面值，逐个减目标价，返回最少硬币数。

        凑不出目标时返回一个大于任何可行解的大整数，作为不可达的口径。
        """
        best = self._enumerate(self._target)
        if best >= self._UNREACHABLE:
            return self._UNREACHABLE
        return best

    # 用一个足够大的上界表示不可达，保证任何真实解都严格小于它
    _UNREACHABLE = 1 << 62

    def _enumerate(self, remaining):
        if remaining == 0:
            return 0
        best = self._UNREACHABLE
        for c in self._coins:
            if c <= remaining:
                sub = self._enumerate(remaining - c)
                if sub + 1 < best:
                    best = sub + 1
        return best

    def is_reachable(self):
        """递归枚举判断目标金额是否可达。"""
        return self.min_coins() < self._UNREACHABLE

    def selection(self):
        """给出一组达到最少硬币数的具体选法，按面值升序排列。

        不可达时返回空列表。并列取法按写死的面值升序口径挑选：
        在同为最优的取法里，优先选面值更小的那一枚作为当前这一步。
        """
        if not self.is_reachable():
            return []
        picked = []
        remaining = self._target
        while remaining > 0:
            for c in self._coins:
                if c <= remaining and self._enumerate(remaining - c) + 1 == self._enumerate(remaining):
                    picked.append(c)
                    remaining -= c
                    break
        picked.sort()
        return picked

    def count_min_ways(self):
        """递归枚举统计达到最少硬币数的方案个数。

        方案按面值的多重集合计，同一组面值无论考虑次序都只算一条；
        重复面值已按规范口径去重，故不同的规范面值各算不同。
        不可达时按写死口径返回零。
        """
        best = self.min_coins()
        if best >= self._UNREACHABLE:
            return 0
        return self._count(0, self._target, best)

    def _count(self, start, remaining, steps_left):
        if remaining == 0:
            return 1 if steps_left == 0 else 0
        if steps_left == 0:
            return 0
        total = 0
        # 只按面值下标不降地推进，避免同一组面值被以不同次序重复计数
        for i in range(start, len(self._coins)):
            c = self._coins[i]
            if c <= remaining:
                total += self._count(i, remaining - c, steps_left - 1)
        return total
