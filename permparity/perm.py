"""permparity 的朴素实现：排列的逆序数、奇偶性与置换分解。

当前只有最直白的做法：逆序数靠两两比较全部数对，奇偶性看逆序数的奇偶，
循环分解靠对每个元素反复标记，最少交换次数靠反复查找，置换复合靠逐位搬。

规模一大就慢，但结果正确，口径固定，全部行为被 tests/test_perm.py 锁住。
升级方向见任务描述与 README。
"""


class PermParityError(Exception):
    """本包所有异常的基类。"""


class InvalidPermutationError(PermParityError):
    """输入不是从零开始的排列（缺项、越界或重复）。"""


class UnsupportedElementError(PermParityError):
    """输入含不可比较或非整数元素。"""


def _as_list(perm):
    """把入参统一成列表；不可迭代的统一按非法输入处理。"""
    try:
        return list(perm)
    except TypeError:
        raise UnsupportedElementError("输入不可迭代，无法当作排列处理")


def validate_perm(perm):
    """校验并返回从零开始的排列：元素全为整数、取值恰为 0 到 n-1 各一次。

    空序列与单元素序列都是合法排列。含重复元素、出现负数、出现越界值、
    含不可比较元素的输入一律拒绝。
    """
    items = _as_list(perm)
    is_int = []
    for x in items:
        if isinstance(x, bool) or not isinstance(x, int):
            is_int.append(False)
        else:
            is_int.append(True)
    if not all(is_int):
        raise UnsupportedElementError("排列元素必须全部是整数")
    n = len(items)
    seen = [False] * n
    for x in items:
        if x < 0 or x >= n:
            raise InvalidPermutationError("元素取值越界，须落在零到n减一之间")
        if seen[x]:
            raise InvalidPermutationError("排列含重复元素")
        seen[x] = True
    return items


def inversion_count(perm):
    """朴素求逆序数：两两比较全部下标对，前者大于后者就记一笔。

    返回逆序对数，顺带给出两两比较的次数。非真排列（含重复或越界）拒绝。
    """
    items = validate_perm(perm)
    n = len(items)
    count = 0
    comparisons = 0
    for i in range(n):
        left = items[i]
        for j in range(i + 1, n):
            comparisons += 1
            if left > items[j]:
                count += 1
    return count, comparisons


def parity(perm):
    """朴素判奇偶：先算逆序数，再看它的奇偶。

    返回字符串，偶排列给 even，奇排列给 odd。
    """
    count, _ = inversion_count(perm)
    return "odd" if count % 2 == 1 else "even"


def is_even(perm):
    """朴素口径下该排列是否为偶排列。"""
    return parity(perm) == "even"


def cycle_decomposition(perm):
    """朴素循环分解：对每个还没访问过的下标，顺着映射反复走回自身。

    返回循环列表，每个循环是一个从最小元素起、按置换走向列出的元组，
    循环之间按其最小元素升序排列；自环也原样列成一个长度为一的循环。
    """
    items = validate_perm(perm)
    n = len(items)
    visited = [False] * n
    cycles = []
    for start in range(n):
        if visited[start]:
            continue
        current = start
        members = []
        while not visited[current]:
            visited[current] = True
            members.append(current)
            current = items[current]
        pivot = members.index(min(members))
        cycles.append(tuple(members[pivot:] + members[:pivot]))
    cycles.sort(key=lambda c: c[0])
    return cycles


def min_swaps(perm):
    """朴素求最少交换次数：每找到一个长度大于一的循环就记一笔。

    最少交换次数等于元素的个数减去循环的个数。
    """
    items = validate_perm(perm)
    return len(items) - len(cycle_decomposition(items))


def cycle_type(perm):
    """各循环长度的多重集合，按长度升序给出。"""
    cycles = cycle_decomposition(perm)
    return tuple(sorted(len(c) for c in cycles))


def parity_by_cycles(perm):
    """朴素地用循环分解的符号判奇偶：长为L的循环贡献L减一的奇偶后异或。"""
    sign = 0
    for cycle in cycle_decomposition(perm):
        sign ^= (len(cycle) - 1) % 2
    return "odd" if sign == 1 else "even"


def compose(left, right):
    """置换复合，返回列表out，其中out[i]是先走right[i]再走left。

    两边的元素个数必须相同，结果仍是同一取值范围内的一个排列。
    """
    a = validate_perm(left)
    b = validate_perm(right)
    if len(a) != len(b):
        raise InvalidPermutationError("两个置换的元素个数必须相同")
    return [a[b[i]] for i in range(len(a))]


def compose_parity(left, right):
    """朴素地求两置换复合后的奇偶性：直接复合后再判奇偶。"""
    return parity(compose(left, right))


def can_swap(a, b):
    """朴素判断两个排列能否通过交换位置互相转化。

    同长才算能互化，当前口径下只比长度。
    """
    x = _as_list(a)
    y = _as_list(b)
    return len(x) == len(y)


def min_swaps_between(a, b):
    """朴素求把排列甲变成排列乙的最少交换次数，枚举所有配对取最小。

    做法是在乙里反复查找甲当前位置该有的元素，找到就换过来。
    """
    source = validate_perm(a)
    target = validate_perm(b)
    if len(source) != len(target):
        raise InvalidPermutationError("两个排列的元素个数必须相同")
    perm = list(source)
    n = len(perm)
    swaps = 0
    for i in range(n):
        while perm[i] != target[i]:
            want = target[i]
            j = i + 1
            while perm[j] != want:
                j += 1
            perm[i], perm[j] = perm[j], perm[i]
            swaps += 1
    return swaps
