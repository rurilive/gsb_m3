"""chainkit：矩阵连乘的最优括号化与派生问题的朴素实现。

链是一串矩阵的维度，用一维整数序列 dims 表示：dim(i) 是第 i 个矩阵的行数
（i 从 0 起），末尾多出的一个数是最后一个矩阵的列数。矩阵个数 n 等于
len(dims) 减一。乘积里相邻两矩阵要能相乘，须前一个的列数等于后一个的行数，
即 dims 全序列相邻不必额外约束，链本身保证可乘；单个矩阵或空链另行规定。

本模块当前是直白写法：对每个区间枚举全部分裂点，左右两半各自递归重算代价，
最优括号化也靠同一套枚举，判定某括号化是否合法及算它的乘法次数靠逐段重扫。
结果正确，但链一长重复子问题就被反复重算，量级很快上去。

链一长为零或一时没有分裂点，本模块按约定给退化结果：乘法次数为零，方案的
个数为一。链为零或一的括号化是空串，从空串算出的乘法次数也是零。
"""


class ChainError(Exception):
    """chainkit 里所有可诊断错误的基类。

    message 是单行说明；position 是出错位置（链上的下标或括号串上的下标）；
    data 是出错时问题数据的人读摘要。上层按本基类统一捕获。
    """

    def __init__(self, message, position=0, data=""):
        super().__init__(message)
        self.message = message
        self.position = position
        self.data = data

    def __str__(self):
        return "%s (position %d)" % (self.message, self.position)


def check_dims(dims):
    """校验维度序列并返回矩阵个数。

    dims 必须是非空整数序列，每个数都得是正整数；负数或零会使某步不可乘，
    一律抛 ChainError。空序列抛 ChainError（无法确定矩阵个数）。
    """
    dims = list(dims)
    if len(dims) == 0:
        raise ChainError("维度序列不能为空", position=0, data="")
    for i, d in enumerate(dims):
        if not isinstance(d, int) or isinstance(d, bool):
            raise ChainError("维度必须是整数", position=i, data=str(d))
        if d <= 0:
            raise ChainError("维度必须为正", position=i, data=str(d))
    return len(dims) - 1


def _check_range(n, i, j):
    """校验区间端点（左闭右闭的矩阵下标），越界或左大于右抛 ChainError。

    调用方须先排除链长为零的情形（在链上取不出任何下标），本函数只处理
    n 至少为一时的区间。
    """
    for k in (i, j):
        if not isinstance(k, int) or isinstance(k, bool):
            raise ChainError("区间端点必须是整数", position=0, data=str(k))
    if i < 0 or i >= n or j < 0 or j >= n:
        raise ChainError("区间端点越界", position=i, data="")
    if j < i:
        raise ChainError("区间不合法", position=j, data="")


def _cost_two(a, b, c):
    """三个相邻维度给出的乘法次数：前两维相乘再乘第三维。"""
    return a * b * c


def naive_cost(dims, i, j):
    """朴素求第 i 到第 j 个矩阵（左闭右闭）相乘的最少标量乘法次数。

    对每个分裂点 k 把区间切成左右两半，左右各自递归重算代价，取和最小者。
    区间里没有矩阵或只有一个矩阵时乘法次数为零。
    """
    n = check_dims(dims)
    if n == 0:
        raise ChainError("空链没有可取的区间", position=0, data="")
    _check_range(n, i, j)
    if i == j:
        return 0
    best = None
    for k in range(i, j):
        left = naive_cost(dims, i, k)
        right = naive_cost(dims, k + 1, j)
        here = left + right + _cost_two(dims[i], dims[k + 1], dims[j + 1])
        if best is None or here < best:
            best = here
    return best


def naive_optimal(dims, i, j):
    """朴素求第 i 到第 j 个矩阵的最少乘法次数与一个最优括号化方案。

    枚举分裂点的方式与 naive_cost 相同，方案按递归回代拼出来，返回
    (次数, 方案)，方案是嵌套的二元组，叶子是矩阵下标。
    """
    n = check_dims(dims)
    if n == 0:
        raise ChainError("空链没有可取的区间", position=0, data="")
    _check_range(n, i, j)
    if i == j:
        return 0, i
    best = None
    best_split = None
    for k in range(i, j):
        left = naive_cost(dims, i, k)
        right = naive_cost(dims, k + 1, j)
        here = left + right + _cost_two(dims[i], dims[k + 1], dims[j + 1])
        if best is None or here < best:
            best = here
            best_split = k
    left_plan = naive_optimal(dims, i, best_split)[1]
    right_plan = naive_optimal(dims, best_split + 1, j)[1]
    return best, (left_plan, right_plan)


def naive_count(dims, i, j):
    """朴素求第 i 到第 j 个矩阵最优括号化方案的个数。

    枚举每个分裂点，若分裂点处左右之和加本次代价等于区间最优值，就把左右两边
    的方案数相乘后累加。并列最优的多个分裂点都会被算进去。退化为零或一时为一。
    """
    n = check_dims(dims)
    if n == 0:
        raise ChainError("空链没有可取的区间", position=0, data="")
    _check_range(n, i, j)
    if i == j:
        return 1
    best = naive_cost(dims, i, j)
    total = 0
    for k in range(i, j):
        left = naive_cost(dims, i, k)
        right = naive_cost(dims, k + 1, j)
        here = left + right + _cost_two(dims[i], dims[k + 1], dims[j + 1])
        if here == best:
            total += naive_count(dims, i, k) * naive_count(dims, k + 1, j)
    return total


def whole_cost(dims):
    """整条链的最少乘法次数，即 naive_cost 作用于全区间。"""
    n = check_dims(dims)
    if n == 0:
        return 0
    return naive_cost(dims, 0, n - 1)


def whole_optimal(dims):
    """整条链的最少乘法次数与一个最优括号化方案。空链给 (0, None)。"""
    n = check_dims(dims)
    if n == 0:
        return 0, None
    return naive_optimal(dims, 0, n - 1)


def whole_count(dims):
    """整条链最优括号化方案的个数。空链与单矩阵都给一。"""
    n = check_dims(dims)
    if n == 0:
        return 1
    return naive_count(dims, 0, n - 1)


def _plan_text(plan):
    """把一个嵌套方案记成带括号的字符串，叶子写成矩阵下标。"""
    if isinstance(plan, int):
        return str(plan)
    return "(" + _plan_text(plan[0]) + _plan_text(plan[1]) + ")"


def plan_to_string(dims, plan):
    """把一个方案还原成括号字符串。

    叶子直接写矩阵下标；每个内部节点都老老实实写出一对括号把左右包住。链为
    一个矩阵时结果是那个下标，链为空时是空串。
    """
    n = check_dims(dims)
    if n == 0:
        return ""
    return _plan_text(plan)


def parse_plan(dims, plan_text):
    """朴素解析括号串，返回嵌套方案；非法串抛 ChainError。

    语法是：叶子写单个矩阵下标，内部节点写成一左括号后跟左右两个子表达式再跟
    一个右括号。空白忽略。空链只接受空串并返回 None，单矩阵只接受那一个下标。
    串里出现非法字符、括号不配对、下标越界或有剩余内容都抛 ChainError。
    """
    n = check_dims(dims)
    text = plan_text.replace(" ", "")
    if n == 0:
        if text != "":
            raise ChainError("空链的括号串必须是空串", position=0, data=plan_text)
        return None
    plan, pos = _parse(text, 0, n)
    if pos != len(text):
        raise ChainError("括号串有剩余内容", position=pos, data=plan_text)
    return plan


def _parse(text, pos, n):
    """自 pos 起解析一个子表达式，返回 (方案, 新位置)。"""
    if pos >= len(text):
        raise ChainError("括号串提前结束", position=pos, data=text)
    ch = text[pos]
    if ch.isdigit():
        d = int(ch)
        if d >= n:
            raise ChainError("矩阵下标越界", position=pos, data=text)
        return d, pos + 1
    if ch != "(":
        raise ChainError("括号串含非法字符", position=pos, data=text)
    left, pos = _parse(text, pos + 1, n)
    right, pos = _parse(text, pos, n)
    if pos >= len(text) or text[pos] != ")":
        raise ChainError("括号不配对", position=pos, data=text)
    return (left, right), pos + 1


def _leaves(plan):
    """按从左到右的顺序产出方案里的矩阵下标。"""
    if isinstance(plan, int):
        yield plan
    else:
        for x in _leaves(plan[0]):
            yield x
        for x in _leaves(plan[1]):
            yield x


def _walk_cost(dims, plan):
    """递归求一个方案的乘法次数：每个内部结点重扫左右两块的叶子端点。"""
    if isinstance(plan, int):
        return 0
    left_leaves = list(_leaves(plan[0]))
    right_leaves = list(_leaves(plan[1]))
    a = left_leaves[0]
    b = right_leaves[0]
    c = right_leaves[-1]
    return (_walk_cost(dims, plan[0]) + _walk_cost(dims, plan[1])
            + _cost_two(dims[a], dims[b], dims[c + 1]))


def naive_plan_cost(dims, plan_text):
    """朴素从括号串算乘法次数：先解析出括号结构，再逐段重扫累加每层的乘法代价。

    括号串写作矩阵下标加括号，例如两个矩阵相乘写作 (01)，三个写作 (0(12))。
    每一层括号是一次矩阵乘法，重扫它左右两块的叶子端点得到操作数维度，累加
    相乘代价。串非法或维度对不上时抛 ChainError。
    """
    n = check_dims(dims)
    plan = parse_plan(dims, plan_text)
    if n <= 1:
        return 0
    return _walk_cost(dims, plan)

