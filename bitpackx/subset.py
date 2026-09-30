"""bitpackx 的朴素实现（改造前基线）。

用布尔数组记录可达和：每加一个数就把当前所有可达和逐个取出来加上该数，
内层把已可达的区间整个扫一遍，规模一大就是平方级。功能正确，速度不快。
"""


class BitpackError(Exception):
    """本库所有异常的基类。"""


class InvalidValueError(BitpackError, ValueError):
    """违反数值口径时抛出（负数、非正整数、目标和为负等）。"""


def _check_item(value):
    """正整数校验：非整数、布尔、负数与零一律拒。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidValueError("集合元素必须是正整数")
    if value <= 0:
        raise InvalidValueError("集合元素必须是正整数，负数与零不被接受")
    return value


class BitBag:
    """正整数集合，用布尔数组做朴素的可达和计算。

    reachable(n)：从集合里挑出若干个数使和为 n 时返回真。
    reachable_set(limit)：返回不超过 limit 的全部可行和（升序列表）。
    count(limit)：返回不超过 limit 的可行和个数。
    max2(limit)：返回不超过 limit 的最大可行和，一个都凑不出时返回 None。
    """

    def __init__(self, items=()):
        self._items = []
        for value in items:
            self.add(value)

    def add(self, value):
        self._items.append(_check_item(value))
        return self

    def items(self):
        return list(self._items)

    def _reach(self, limit):
        """布尔数组 reach：下标 n 处为真表示和 n 可达。

        内层用朴素循环：先把当前可达区间整个扫一遍，再逐个把新和标成可达。
        """
        if limit < 0:
            raise InvalidValueError("上限不能为负")
        reach = [False] * (limit + 1)
        reach[0] = True
        for value in self._items:
            if value > limit:
                continue
            for total in range(limit - value, -1, -1):
                if reach[total]:
                    reach[total + value] = True
        return reach

    def reachable(self, target):
        if target < 0:
            raise InvalidValueError("目标和不能为负")
        reach = self._reach(target)
        return reach[target]

    def reachable_set(self, limit):
        reach = self._reach(limit)
        return [total for total in range(limit + 1) if reach[total]]

    def count(self, limit):
        return len(self.reachable_set(limit))

    def max2(self, limit):
        reach = self._reach(limit)
        for total in range(limit, -1, -1):
            if reach[total]:
                return total
        return None
