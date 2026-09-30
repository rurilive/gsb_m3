"""crtkit 现状：同余方程组的朴素试值实现。

这里只有改造前的基线做法：不约分、不求逆元，一律从一个候选整数
往上一格一格地试，直到同时满足全部同余式为止。结果对，但值域一大
就慢得离谱，而且每一步都走着同一个计数口径，方便对照规模。
"""


class CrtkitError(Exception):
    """crtkit 全部异常的基类。"""


class EmptySystemError(CrtkitError):
    """同余方程组为空。"""


class InvalidModulusError(CrtkitError):
    """模数不是正整数。"""


class NoSolutionError(CrtkitError):
    """同余方程组没有解。"""


class InvalidRangeError(CrtkitError):
    """查询区间的上下界颠倒。"""


class InvalidBoundsError(CrtkitError):
    """穷举上界不是正整数。"""


def normalize_modulus(m):
    """校验模数并返回整数形式。模数必须是不小于一的整数。"""
    if isinstance(m, bool) or not isinstance(m, int):
        raise InvalidModulusError("模数必须是整数")
    if m < 1:
        raise InvalidModulusError("模数必须不小于一")
    return int(m)


def normalize_residue(a, m):
    """把余数规约到零到模数减一的范围内。"""
    return int(a) % normalize_modulus(m)


def _normalized_system(residues, moduli):
    """把两个序列配成一对一并规约，供后续所有做法共用。"""
    residues = list(residues)
    moduli = list(moduli)
    if len(residues) != len(moduli):
        raise InvalidModulusError("余数个数与模数个数不一致")
    if len(moduli) == 0:
        raise EmptySystemError("同余方程组为空")
    pairs = []
    for a, m in zip(residues, moduli):
        mod = normalize_modulus(m)
        pairs.append((int(a) % mod, mod))
    return pairs


def _max_search_limit(pairs, cap):
    """朴素搜索的上界：取 cap 与全部模数之和的较大者。"""
    total = sum(m for _, m in pairs)
    return max(int(cap), total)


def search_first_solution(residues, moduli, cap=100000):
    """从零开始逐个候选整数往上试，返回第一个同时满足全部方程的解。"""
    pairs = _normalized_system(residues, moduli)
    limit = _max_search_limit(pairs, cap)
    candidate = 0
    while candidate <= limit:
        ok = True
        for a, m in pairs:
            if candidate % m != a:
                ok = False
                break
        if ok:
            return candidate
        candidate += 1
    return None


def count_search_steps(residues, moduli, cap=100000):
    """数一下朴素试值在本组方程上要试探多少个候选整数才找到解。"""
    pairs = _normalized_system(residues, moduli)
    limit = _max_search_limit(pairs, cap)
    candidate = 0
    tried = 0
    while candidate <= limit:
        tried += 1
        ok = True
        for a, m in pairs:
            if candidate % m != a:
                ok = False
                break
        if ok:
            return tried
        candidate += 1
    return tried


def has_solution(residues, moduli, cap=100000):
    """是否存在解：也靠同一个试值过程判定。"""
    return search_first_solution(residues, moduli, cap) is not None


def solve(residues, moduli, cap=100000):
    """给出方程组的一个解；找不到就抛无解异常。"""
    found = search_first_solution(residues, moduli, cap)
    if found is None:
        raise NoSolutionError("在给定上界内没有找到解")
    return found


def smallest_non_negative(residues, moduli, cap=100000):
    """最小非负解：朴素做法直接把试出来的第一个解当作最小非负解。"""
    return solve(residues, moduli, cap)


def solutions_in_range(residues, moduli, low, high, cap=100000):
    """给出区间 low 到 high 内全部满足方程的解。"""
    scan_low = int(low)
    scan_high = int(high)
    if scan_high < scan_low:
        raise InvalidRangeError("区间上界小于下界")
    if scan_low < 0:
        scan_low = 0
    pairs = _normalized_system(residues, moduli)
    limit = _max_search_limit(pairs, cap)
    if scan_high > limit:
        scan_high = limit
    found = []
    candidate = scan_low
    while candidate <= scan_high:
        ok = True
        for a, m in pairs:
            if candidate % m != a:
                ok = False
                break
        if ok:
            found.append(candidate)
        candidate += 1
    return found


def count_in_range(residues, moduli, low, high, cap=100000):
    """区间内的解个数，也靠逐个候选整数试出来。"""
    return len(solutions_in_range(residues, moduli, low, high, cap))
