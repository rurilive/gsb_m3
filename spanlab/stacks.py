"""序列左右边界的朴素实现（改造前的基线，纯标准库）。

只用最直白的双向扫描：求每个位置两侧第一个更近的更大或更小元素时，就从该位置
出发向左和向右一格一格地看；求柱状图最大矩形面积、所有子数组最小值之和与最大值
之和、每个元素作为最小值的子数组个数，也全是双重循环枚举。规模一大就是平方量级，
但每一步都照着定义做，结果对。

约定：

- 某一侧没有满足条件的元素时返回约定值 -1。
- 更大与更小都取严格比较，即必须严格大于或严格小于。
- 返回的列表与底层数据无关，调用方改动它不影响内部。
"""

_CONVENTION = -1


class SpanError(Exception):
    """spanlab 自己抛出的异常统一派生自这个基类。"""


class InvalidInputError(SpanError):
    """入参不合法：非整数、非法下标、非法取值口径。"""


class NotSpanableError(SpanError):
    """对空序列查询左右边界：没有位置可查。"""


def _check_values(values):
    """校验输入序列：可迭代、元素为整数且 bool 不算整数。返回新列表。"""
    try:
        items = list(values)
    except TypeError:
        raise InvalidInputError("values must be an iterable of integers")
    for x in items:
        if isinstance(x, bool) or not isinstance(x, int):
            raise InvalidInputError("values must all be integers")
    return items


def _check_index(values, i):
    """校验下标：必须是整数、bool 不算、且在序列范围内。"""
    if isinstance(i, bool) or not isinstance(i, int):
        raise InvalidInputError("index must be an integer")
    if i < 0 or i >= len(values):
        raise InvalidInputError("index out of range")


def first_greater_left(values, i):
    """从位置 i 向左看，返回左侧第一个严格大于它的下标，没有返回 -1。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    j = i - 1
    while j >= 0:
        if data[j] > target:
            return j
        j -= 1
    return _CONVENTION


def first_greater_right(values, i):
    """从位置 i 向右看，返回右侧第一个严格大于它的下标，没有返回 -1。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    n = len(data)
    j = i + 1
    while j < n:
        if data[j] > target:
            return j
        j += 1
    return _CONVENTION


def first_smaller_left(values, i):
    """从位置 i 向左看，返回左侧第一个严格小于它的下标，没有返回 -1。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    j = i - 1
    while j >= 0:
        if data[j] < target:
            return j
        j -= 1
    return _CONVENTION


def first_smaller_right(values, i):
    """从位置 i 向右看，返回右侧第一个严格小于它的下标，没有返回 -1。"""
    data = _check_values(values)
    _check_index(data, i)
    target = data[i]
    n = len(data)
    j = i + 1
    while j < n:
        if data[j] < target:
            return j
        j += 1
    return _CONVENTION


def bounds_greater(values):
    """一次求出全部位置左右两侧第一个更大元素，返回两份下标列表。"""
    data = _check_values(values)
    n = len(data)
    left = [-1] * n
    right = [-1] * n
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            if data[j] > target:
                left[i] = j
                break
            j -= 1
        j = i + 1
        while j < n:
            if data[j] > target:
                right[i] = j
                break
            j += 1
    return left, right


def bounds_smaller(values):
    """一次求出全部位置左右两侧第一个更小元素，返回两份下标列表。"""
    data = _check_values(values)
    n = len(data)
    left = [-1] * n
    right = [-1] * n
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            if data[j] < target:
                left[i] = j
                break
            j -= 1
        j = i + 1
        while j < n:
            if data[j] < target:
                right[i] = j
                break
            j += 1
    return left, right


def _nearest_smaller_strict(heights, i):
    """向左向右各找第一个严格更小的下标，返回两者的组合。"""
    n = len(heights)
    target = heights[i]
    j = i - 1
    left = -1
    while j >= 0:
        if heights[j] < target:
            left = j
            break
        j -= 1
    j = i + 1
    right = n
    while j < n:
        if heights[j] < target:
            right = j
            break
        j += 1
    return left, right


def largest_rectangle(heights):
    """柱状图中最大矩形面积，逐位置把它当作最矮的那一根再向两侧扩。"""
    data = _check_values(heights)
    n = len(data)
    best = 0
    for i in range(n):
        left, right = _nearest_smaller_strict(data, i)
        width = right - left - 1
        area = data[i] * width
        if area > best:
            best = area
    return best


def sum_of_subarray_mins(values):
    """所有子数组的最小值之和，用双重循环枚举子区间再取最小值。"""
    data = _check_values(values)
    n = len(data)
    total = 0
    for i in range(n):
        current = data[i]
        for j in range(i, n):
            if data[j] < current:
                current = data[j]
            total += current
    return total


def sum_of_subarray_maxs(values):
    """所有子数组的最大值之和，用双重循环枚举子区间再取最大值。"""
    data = _check_values(values)
    n = len(data)
    total = 0
    for i in range(n):
        current = data[i]
        for j in range(i, n):
            if data[j] > current:
                current = data[j]
            total += current
    return total


def count_subarrays_as_min(values):
    """每个元素作为最小值出现的子数组个数，按元素逐个向两侧扩。"""
    data = _check_values(values)
    n = len(data)
    counts = [0] * n
    for i in range(n):
        target = data[i]
        left = i - 1
        while left >= 0 and data[left] > target:
            left -= 1
        right = i + 1
        while right < n and data[right] >= target:
            right += 1
        counts[i] = (i - left) * (right - i)
    return counts


def count_brute_scans(values):
    """统计朴素路径做一次左右边界查询总共要比较多少次。"""
    data = _check_values(values)
    n = len(data)
    total = 0
    for i in range(n):
        target = data[i]
        j = i - 1
        while j >= 0:
            total += 1
            if data[j] > target:
                break
            j -= 1
        j = i + 1
        while j < n:
            total += 1
            if data[j] > target:
                break
            j += 1
    return total
