"""assignmatch 的指派工具（改造前的现状）。

现在只有一条朴素路：给定代价矩阵求最小总代价的完美指派、求最大收益指派、判断
某个指派是不是最优、求最大匹配下的最优指派，全靠枚举全部置换再逐个算总代价。
置换数随工人数阶乘上涨。匈牙利增广与费用流这类做法见任务描述。
"""

#: 表示不可用组合的哨兵，矩阵里既可以写 None 也可以写这个无穷大。
INF = float("inf")


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class MatrixError(Erro):
    """代价矩阵参数非法。"""


def _is_number(value):
    """是不是真正的整数或浮点数，布尔值不算，无穷大也不算普通代价。"""
    if isinstance(value, bool):
        return False
    return isinstance(value, int) or isinstance(value, float)


def _is_blocked(cell):
    """这个格子是不是不可用组合。None 与 INF 都表示不可用。"""
    if cell is None:
        return True
    if isinstance(cell, float) and cell == INF:
        return True
    return False


def _check_matrix(cost):
    """校验代价矩阵并返回行数与列数。

    矩阵是若干行，每行若干列，行列都不允许为空，格子必须是数字或表示不可用组合
    的 None 与 INF。所有行必须等长。
    """
    if cost is None:
        raise MatrixError("cost must not be None")
    try:
        rows = len(cost)
    except TypeError:
        raise MatrixError("cost must be a sequence of rows")
    if rows == 0:
        raise MatrixError("cost must have at least one row")
    cols = None
    for row in cost:
        try:
            width = len(row)
        except TypeError:
            raise MatrixError("each row must be a sequence")
        if width == 0:
            raise MatrixError("each row must have at least one column")
        if cols is None:
            cols = width
        elif width != cols:
            raise MatrixError("rows must have the same length")
        for cell in row:
            if _is_blocked(cell):
                continue
            if not _is_number(cell):
                raise MatrixError("each cell must be a number or None")
    return rows, cols


def _check_square(cost):
    """完美指派要求工人数与任务数相等。"""
    rows, cols = _check_matrix(cost)
    if rows != cols:
        raise MatrixError("perfect assignment needs a square matrix")
    return rows


def permutation_count(n):
    """n 个工人的全部置换总数，也就是朴素枚举要过一遍的候选数。"""
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise MatrixError("n must be a non-negative int")
    total = 1
    for k in range(2, n + 1):
        total *= k
    return total


def _permute(items):
    """把一串互不相同的元素按字典序逐个吐出全排列，最直白的递归枚举。"""
    if len(items) <= 1:
        yield tuple(items)
        return
    for index in range(len(items)):
        head = items[index]
        rest = items[:index] + items[index + 1:]
        for tail in _permute(rest):
            yield (head,) + tail


def enumerate_permutations(n):
    """逐个吐出零到 n 减一的全排列，按字典序，最直白的递归枚举。"""
    for permutation in _permute(list(range(n))):
        yield permutation


def _total_cost(cost, assignment):
    """一个指派方案的总代价，矩阵里不可用的格子会让总代价变成无穷大。"""
    total = 0
    for worker, task in enumerate(assignment):
        cell = cost[worker][task]
        if _is_blocked(cell):
            return INF
        total += cell
    return total


def _canonical(assignment):
    """把指派方案化成可比较的键：工人编号升序，各工人取最小任务编号。

    未接活的工人排在已接活之后，这样在同样大小与同样总代价的方案里，优先让编号
    小的工人接上编号小的任务。
    """
    key = []
    for task in assignment:
        if task is None:
            key.append((1, 0))
        else:
            key.append((0, task))
    return tuple(key)


def min_cost_assignment(cost):
    """求最小总代价的完美指派，枚举全部置换再逐个算总代价取最小。

    返回总代价与指派方案，方案是每个工人对应的任务编号列表；总代价并列时取工人
    编号升序、每工人任务编号最小者。要求方阵且没有不可用组合。
    """
    n = _check_square(cost)
    best = None
    for permutation in enumerate_permutations(n):
        total = _total_cost(cost, permutation)
        key = (total, _canonical(permutation))
        if best is None or key < best[0]:
            best = (key, permutation)
    return {"cost": best[0][0], "assignment": list(best[1])}


def max_profit_assignment(cost):
    """求最大总收益的指派，枚举全部置换再逐个算总收益取最大。

    口径与最小代价分开：这里比的是越大越好。要求方阵且没有不可用组合。
    """
    n = _check_square(cost)
    best = None
    for permutation in enumerate_permutations(n):
        total = _total_cost(cost, permutation)
        key = (-total, _canonical(permutation))
        if best is None or key < best[0]:
            best = (key, total, permutation)
    return {"cost": best[1], "assignment": list(best[2])}


def assignment_cost(cost, assignment):
    """给定指派方案求总代价。方案长度必须与工人数一致。"""
    rows, _cols = _check_matrix(cost)
    if assignment is None:
        raise MatrixError("assignment must not be None")
    try:
        length = len(assignment)
    except TypeError:
        raise MatrixError("assignment must be a sequence")
    if length != rows:
        raise MatrixError("assignment length must match worker count")
    for task in assignment:
        if task is None:
            raise MatrixError("assignment used here must be complete")
        if not isinstance(task, int) or isinstance(task, bool):
            raise MatrixError("task must be an int")
        if task < 0 or task >= len(cost[0]):
            raise MatrixError("task out of range")
    total = 0
    for worker, task in enumerate(assignment):
        cell = cost[worker][task]
        if _is_blocked(cell):
            raise MatrixError("assignment uses a blocked cell")
        total += cell
    return total


def is_optimal(cost, assignment, mode="min"):
    """判断给定指派方案是不是最优，比的是它同口径下的极致值。

    mode 取 min 时与最小总代价比，取 max 时与最大总收益比。比较都走枚举老路。
    """
    if mode == "min":
        best = min_cost_assignment(cost)
    elif mode == "max":
        best = max_profit_assignment(cost)
    else:
        raise MatrixError("mode must be min or max")
    return assignment_cost(cost, assignment) == best["cost"]


def _enumerate_partial(cost):
    """枚举全部可行方案，每个工人要么空着，要么接一个还没被接的任务。

    只走可用的格子，用来处理工人数与任务数不等、以及某些组合不可用的情形。
    """
    rows, cols = _check_matrix(cost)
    result = []

    def walk(worker, used, acc):
        if worker == rows:
            result.append(tuple(acc))
            return
        acc.append(None)
        walk(worker + 1, used, acc)
        acc.pop()
        for task in range(cols):
            if task in used:
                continue
            if _is_blocked(cost[worker][task]):
                continue
            used.add(task)
            acc.append(task)
            walk(worker + 1, used, acc)
            acc.pop()
            used.remove(task)

    walk(0, set(), [])
    return result


def best_partial_assignment(cost):
    """求最大匹配下的最优指派，枚举全部可行方案后按大小、总代价、编号取定。

    工人数与任务数不等、或某些组合不可用时用这里。先比接活人数越大越好，再比总
    代价越小越好，并列时按工人编号升序、每工人任务编号最小取定。
    """
    best = None
    for acc in _enumerate_partial(cost):
        size = 0
        total = 0
        for worker, task in enumerate(acc):
            if task is not None:
                size += 1
                total += cost[worker][task]
        key = (-size, total, _canonical(acc))
        if best is None or key < best[0]:
            best = (key, acc, size, total)
    return {
        "size": best[2],
        "cost": best[3],
        "assignment": list(best[1]),
    }


class AssignTools:
    """绑定一张代价矩阵的指派工具，只有枚举置换这一条路。

    求最小代价指派、求最大收益指派、求总代价、判断是否最优、求最大匹配最优都提
    供方法，并累计枚举置换的次数，供与匈牙利增广次数对照规模。
    """

    def __init__(self, cost):
        _check_matrix(cost)
        self._cost = [list(row) for row in cost]
        self._perm_count = 0

    def reset_permutation_count(self):
        """把置换枚举计数清零。"""
        self._perm_count = 0

    def permutation_count(self):
        """自上次清零以来累计枚举了多少个候选方案。"""
        return self._perm_count

    def min_cost_assignment(self):
        """朴素求最小代价完美指派，枚举全部置换，计数随工人数阶乘上涨。"""
        n = _check_square(self._cost)
        self._perm_count += permutation_count(n)
        return min_cost_assignment(self._cost)

    def max_profit_assignment(self):
        """朴素求最大收益指派，同样枚举全部置换。"""
        n = _check_square(self._cost)
        self._perm_count += permutation_count(n)
        return max_profit_assignment(self._cost)

    def assignment_cost(self, assignment):
        """给定方案求总代价。"""
        return assignment_cost(self._cost, assignment)

    def is_optimal(self, assignment, mode="min"):
        """判断方案是否最优。"""
        return is_optimal(self._cost, assignment, mode=mode)

    def best_partial_assignment(self):
        """朴素求最大匹配下的最优指派，枚举全部可行方案。"""
        candidates = _enumerate_partial(self._cost)
        self._perm_count += len(candidates)
        return best_partial_assignment(self._cost)
