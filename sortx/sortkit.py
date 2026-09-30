"""sortx 的排序核心：线性时间排序族的朴素（基线）实现。

本模块当前只提供最直白的能力，全部落在内置排序之上：

    - 整数排序、非负整数排序、定点数排序都直接调用内置的全排序；
    - 按自定义键排序先把键算出来，再交给内置排序；
    - 稳定判据另靠一列相等元素的原始下标逐个核对，不靠排序算出来的顺序；
    - 遍历数列把取值上限与取值下限数一遍。

这些做法朴素但正确，结果与内置排序逐项一致，代价靠内置排序兜底，并没有
真正的计数、基数或者分桶过程。它们同时是包内其余部分与测试所依赖的现状，
必须保持正确且确定，改造时不许删除，要留下来做对照。
"""

import math


class SortxError(Exception):
    """本包所有异常的基类，调用方捕获它就能兜住全部失败。"""


class EmptyInputError(SortxError):
    """输入为空，或在不允许为空的地方拿到了空序列。"""


class NotIntegerError(SortxError):
    """元素、键或者参数不是整数。"""


class ValueOutOfRangeError(SortxError):
    """取值超出当前排序方式允许的范围，或者字段不可比较。"""


class UnstableResultError(SortxError):
    """稳定判据没过：相等元素之间的相对次序被打乱。"""


def _as_int_sequence(values):
    """把入参规范成一份整数列表，顺带做取值校验。"""
    try:
        data = list(values)
    except TypeError:
        raise NotIntegerError("输入必须是可迭代的整数序列")
    result = []
    for value in data:
        if not isinstance(value, int) or isinstance(value, bool):
            raise NotIntegerError("元素必须是整数")
        result.append(int(value))
    return result


def _as_number_sequence(values):
    """把入参规范成一份整数或者浮点数的列表，供定点数排序使用。"""
    try:
        data = list(values)
    except TypeError:
        raise NotIntegerError("输入必须是可迭代的数值序列")
    result = []
    for value in data:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NotIntegerError("元素必须是整数或者定点数")
        result.append(value)
    return result


def integer_sort(values):
    """把一串整数排成升序，直接交给内置全排序。"""
    data = _as_int_sequence(values)
    return sorted(data)


def nonnegative_sort(values):
    """把一串非负整数排成升序。

    先遍历一遍确认没有负数，再交给内置全排序。
    """
    data = _as_int_sequence(values)
    for value in data:
        if value < 0:
            raise ValueOutOfRangeError("非负整数排序不接受负数")
    return sorted(data)


def fixed_sort(values, digits=0):
    """把一串带固定小数位的定点数排成升序。

    小数位是零时按整数处理；大于零时先把每个数按位数放大成整数，调用
    内置全排序之后再缩回去。
    """
    if not isinstance(digits, int) or isinstance(digits, bool) or digits < 0:
        raise NotIntegerError("小数位必须是非负整数")
    data = _as_number_sequence(values)
    if digits == 0:
        return sorted(data)
    scale = 10 ** digits
    scaled = []
    for value in data:
        scaled.append(int(math.floor(value * scale + 0.5)))
    return [value / scale for value in sorted(scaled)]


def key_sort(values, key):
    """按自定义键排序。

    先把每个元素的键算出来，再交给内置全排序，返回键的升序结果。
    """
    data = list(values)
    try:
        decorated = [(key(item), item) for item in data]
    except TypeError:
        raise ValueOutOfRangeError("键不可比较")
    try:
        decorated.sort(key=lambda pair: pair[0])
    except TypeError:
        raise ValueOutOfRangeError("键不可比较")
    return [item for _, item in decorated]


def count_max(values):
    """遍历一遍求最大值，空序列返回零。"""
    data = _as_int_sequence(values)
    best = None
    for value in data:
        if best is None or value > best:
            best = value
    return 0 if best is None else best


def count_min(values):
    """遍历一遍求最小值，空序列返回零。"""
    data = _as_int_sequence(values)
    best = None
    for value in data:
        if best is None or value < best:
            best = value
    return 0 if best is None else best


def _stable_verdict(values, order):
    """核对给定次序相对原序列是否稳定。

    order 是一串原始下标，应当是 range(len(values)) 的一个排列，表示排序
    之后每个位置上站着的是原来第几个元素。稳定判据很直白：凡是取值相等的
    两个元素，原来下标小的在 order 里必须排在前面。
    """
    data = _as_int_sequence(values)
    indices = list(order)
    if sorted(indices) != list(range(len(data))):
        raise ValueOutOfRangeError("次序必须是原始下标的一个排列")
    rank = {}
    for position, index in enumerate(indices):
        rank[index] = position
    groups = {}
    for index, value in enumerate(data):
        groups.setdefault(value, []).append(index)
    for index_list in groups.values():
        for left, right in zip(index_list, index_list[1:]):
            if rank[left] > rank[right]:
                raise UnstableResultError("相等元素之间的相对次序被打乱")
    return True


def sort_and_assert_stable(values):
    """对同一批整数既给排序结果，又给出稳定判据。

    把每个元素连同它的原始下标一起交给内置排序，再从结果里把下标列取出
    来交给稳定判据核对。返回排序后的列表，判据不过就抛异常。
    """
    data = _as_int_sequence(values)
    decorated = sorted((value, index) for index, value in enumerate(data))
    order = [index for _, index in decorated]
    _stable_verdict(data, order)
    return [value for value, _ in decorated]


def compare_with_builtin(values):
    """把本包的排序结果与内置全排序逐项比对。

    返回二元组：本包给出的结果，以及是否与内置排序逐项一致。
    """
    data = _as_int_sequence(values)
    ours = integer_sort(data)
    theirs = sorted(data)
    same = len(ours) == len(theirs)
    if same:
        for left, right in zip(ours, theirs):
            if left != right:
                same = False
                break
    return ours, same


def max_value(values):
    """求取值上限，空序列返回零。"""
    return count_max(values)


def describe_family():
    """列出本包最终要提供的成员，眼下只有整数排序是可用的。"""
    return ["整数的线性时间排序族", "非负整数排序", "定点数排序"]


_LAST_PROBE = None


def probe_kernel(values):
    """返回一次探测的内核信息，顺带记下模块级最近一次探测。

    这个入口故意在模块级留了一份可变状态，用来暴露不确定性：同一批输入
    重复调用，返回值里的探针序号会随着调用历史一起变，结果不再稳定。改造
    后这份模块级状态要撤掉，同样的输入重复跑必须给出完全一致的结果。
    """
    global _LAST_PROBE
    size = len(_as_int_sequence(values))
    if _LAST_PROBE is None:
        _LAST_PROBE = {"calls": 0}
    _LAST_PROBE["calls"] += 1
    return {"size": size, "calls": _LAST_PROBE["calls"]}
