"""triplet 的基线朴素实现。

现状：上升三元组计数一律用三重循环枚举全部下标三元组逐一判定；
存在性判定同样靠三重枚举，一旦遇到就把旗标翻转并提前退出；
长度为四或更长的提升子序列计数直接用组合枚举，把每个下标组合取出来
逐个比较相邻两项，结果正确，但组合数量随序列长度按阶乘甚至指数上涨。
"""


class TripletError(Exception):
    """本包全部自定义异常的基类。"""


class InvalidInputError(TripletError):
    """输入不是可接受的整数序列时抛出。"""


class InvalidLengthError(TripletError):
    """要求的最小长度必须是二以上的整数时抛出。"""


def _as_list(values):
    """把输入规整成一份新的整数列表，非法输入当场失败。"""
    if isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
        raise InvalidInputError("需要一个可迭代的整数序列")
    out = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int):
            raise InvalidInputError("序列里出现了非整数元素")
        out.append(item)
    return out


def count_increasing_triplets_naive(values):
    """数严格上升三元组：下标递增且取值严格递增的三元组个数。

    朴素做法：三重循环枚举全部下标三元组，逐个判定三个值是否严格递增。
    """
    data = _as_list(values)
    n = len(data)
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if data[i] < data[j] and data[j] < data[k]:
                    total += 1
    return total


def count_non_decreasing_triplets_naive(values):
    """数非下降三元组：下标递增且取值逐项不下降的三元组个数。

    朴素做法：三重循环枚举全部下标三元组，逐个判定三个值是否非下降。
    """
    data = _as_list(values)
    n = len(data)
    total = 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if data[i] <= data[j] and data[j] <= data[k]:
                    total += 1
    return total


def has_increasing_triplet_naive(values):
    """是否存在上升三元组。

    朴素做法：三重循环枚举，一旦命中就把旗标翻转并提前退出。
    """
    data = _as_list(values)
    n = len(data)
    found = False
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if data[i] < data[j] and data[j] < data[k]:
                    found = True
    return found


def first_increasing_triplet_naive(values):
    """按下标序列字典序最小的那个严格上升三元组，不存在返回 None。

    朴素做法：按 i、j、k 由小到大三重枚举，第一个命中的就是答案。
    """
    data = _as_list(values)
    n = len(data)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if data[i] < data[j] and data[j] < data[k]:
                    return (i, j, k)
    return None


def count_increasing_subseq_of_length_naive(values, length, strict=True):
    """数指定长度（四或更长）的提升子序列个数。

    朴素做法：枚举全部下标组合，逐个比较相邻两项是否满足口径。
    """
    data = _as_list(values)
    if isinstance(length, bool) or not isinstance(length, int) or length < 2:
        raise InvalidLengthError("长度必须是二以上的整数")
    n = len(data)
    total = 0
    if length > n:
        return 0
    combo = list(range(length))
    while True:
        if _is_monotone(data, combo, strict):
            total += 1
        pos = length - 1
        while pos >= 0 and combo[pos] == n - length + pos:
            pos -= 1
        if pos < 0:
            break
        combo[pos] += 1
        for later in range(pos + 1, length):
            combo[later] = combo[later - 1] + 1
    return total


def _is_monotone(data, combo, strict):
    """判定一组下标上的取值是否按口径单调。"""
    for step in range(1, len(combo)):
        left = data[combo[step - 1]]
        right = data[combo[step]]
        if strict:
            if not left < right:
                return False
        else:
            if not left <= right:
                return False
    return True


def enumerate_triplet_trials(values):
    """合计三重枚举比较的累计步数，用来量出朴素路径的平方立方级代价。"""
    data = _as_list(values)
    n = len(data)
    steps = 0
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                steps += 1
    return steps


class TripletAnalysis:
    """把一条整数序列包成一个可反复查询的上升三元组分析器。"""

    def __init__(self, values=()):
        self._data = _as_list(values)

    def to_list(self):
        return list(self._data)

    def __len__(self):
        return len(self._data)

    def is_empty(self):
        return not self._data

    def count_strict(self):
        return count_increasing_triplets_naive(self._data)

    def count_non_decreasing(self):
        return count_non_decreasing_triplets_naive(self._data)

    def has_increasing(self):
        return has_increasing_triplet_naive(self._data)

    def first_triplet(self):
        return first_increasing_triplet_naive(self._data)

    def count_length(self, length, strict=True):
        return count_increasing_subseq_of_length_naive(self._data, length, strict)

    def summary(self):
        """一份固定的统计摘要，键的顺序写死，便于逐项对照。"""
        return {
            "length": len(self._data),
            "strict": self.count_strict(),
            "non_decreasing": self.count_non_decreasing(),
            "has_increasing": self.has_increasing(),
            "first": self.first_triplet(),
        }
