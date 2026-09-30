"""dlx: 精确覆盖问题的朴素求解工具（改造前基线）。

精确定义：给一张零一矩阵，挑出若干行，使每一列恰好被其中一个被挑中的行覆盖
（每一列上被覆盖的次数恰为一）。这里的实现只有最直白的一条路：把矩阵当成二
维表，按行号从小到大枚举，用一张布尔数组记住哪些列已被占用，一遇到列冲突就
退回。每一层递归都对全部尚未占用的列做一遍线性扫描，去找还需要补的列。结果
都对，但同一批行组合会在不同分支上被反复展开，规模一大就指数级变慢；求全部
解、求行数最少的解也是各自把整棵枚举树重走一遍，彼此不共用口径。

纯标准库，无外部依赖。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class ShapeError(Erro):
    """矩阵形状非法，比如不是矩形，或者行列出现负数。"""


class MatrixError(Erro):
    """矩阵内容非法，比如出现零和一以外的取值，或者行号列号越界。"""


def _is_int(value):
    """是不是真正的整数，布尔值不算。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _copy_matrix(matrix):
    """把输入整理成一个由列表组成的新矩阵，每个单元格只留下零或一。

    顺带校验：必须是矩形，格子只能是零或一。返回矩阵、行数、列数。
    """
    if matrix is None:
        raise ShapeError("矩阵不能为空")
    try:
        rows_in = list(matrix)
    except TypeError:
        raise ShapeError("矩阵必须可迭代")
    grid = []
    for row in rows_in:
        try:
            cells = list(row)
        except TypeError:
            raise ShapeError("每一行必须可迭代")
        normalized = []
        for cell in cells:
            if not _is_int(cell):
                raise MatrixError("单元格只能是零或一")
            if cell not in (0, 1):
                raise MatrixError("单元格只能是零或一")
            normalized.append(cell)
        grid.append(normalized)
    width = None
    for cells in grid:
        if width is None:
            width = len(cells)
        elif len(cells) != width:
            raise ShapeError("矩阵必须是矩形")
    if width is None:
        width = 0
    return grid, len(grid), width


def _search(grid, nrows, ncols, chosen, used, start, solutions):
    """从 start 行起往后枚举，把选中的行记进 chosen。

    used[col] 记录该列是否已被占用。每候选一行，就线性检查它覆盖的每一列有没
    有冲突，有冲突立即放弃这一行。全部列都被占用时记下一个解。因为没有任何列
    头跳转，哪一列最紧、该先补哪一列都不看，同一批行组合会在不同分支上被反复
    展开。
    """
    complete = True
    for col in range(ncols):
        if not used[col]:
            complete = False
            break
    if complete:
        solutions.append(list(chosen))
        return
    for row in range(start, nrows):
        conflict = False
        for col in range(ncols):
            if grid[row][col] and used[col]:
                conflict = True
                break
        if conflict:
            continue
        touched = []
        for col in range(ncols):
            if grid[row][col]:
                used[col] = True
                touched.append(col)
        chosen.append(row)
        _search(grid, nrows, ncols, chosen, used, row + 1, solutions)
        chosen.pop()
        for col in touched:
            used[col] = False


def solve(matrix):
    """返回一个精确覆盖解，按行号升序给出行号列表；无解返回空列表。

    朴素做法把全套解枚举出来，再取字典序最小的那一个。
    """
    grid, nrows, ncols = _copy_matrix(matrix)
    solutions = []
    _search(grid, nrows, ncols, [], [False] * ncols, 0, solutions)
    if not solutions:
        return []
    return list(solutions[0])


def solve_all(matrix, max_solutions=None):
    """枚举全部精确覆盖解，按行号列表的字典序升序返回。

    没有做任何去重与剪枝，同一批行组合会被反复展开。上限参数只用于截断本次枚
    举的输出条数，不是整数或为负都报错。
    """
    if max_solutions is not None:
        if not _is_int(max_solutions):
            raise Erro("解数上限必须是整数")
        if max_solutions < 0:
            raise Erro("解数上限不能为负")
    grid, nrows, ncols = _copy_matrix(matrix)
    solutions = []
    _search(grid, nrows, ncols, [], [False] * ncols, 0, solutions)
    solutions.sort()
    if max_solutions is not None:
        return solutions[:max_solutions]
    return solutions


def minimum_solution(matrix):
    """返回选中行数最少的一个解，并列时取字典序最小；无解返回空列表。

    先把全部解枚举出来，再逐个比行数取最小。
    """
    solutions = solve_all(matrix)
    if not solutions:
        return []
    best = solutions[0]
    for sol in solutions[1:]:
        if (len(sol), sol) < (len(best), best):
            best = sol
    return list(best)


def solution_count(matrix):
    """精确覆盖解的个数。"""
    return len(solve_all(matrix))


def is_exact_cover(matrix, rows):
    """给定行集合是不是一个精确覆盖。

    逐行逐列做最直白的检查：行号必须在范围内且不重复，每个被选中的行对列的贡
    献用线性扫描累加，最后看每一列是不是恰好被覆盖一次。
    """
    grid, nrows, ncols = _copy_matrix(matrix)
    picked = list(rows or [])
    for row in picked:
        if isinstance(row, bool) or not _is_int(row):
            raise MatrixError("行号必须是整数")
        if row < 0 or row >= nrows:
            raise MatrixError("行号越界")
    if len(set(picked)) != len(picked):
        return False
    cover = [0] * ncols
    for row in picked:
        for col in range(ncols):
            if grid[row][col]:
                cover[col] += 1
    for col in range(ncols):
        if cover[col] != 1:
            return False
    return True


def column_coverage(matrix, row):
    """某一行覆盖了哪些列，返回升序的列号列表。"""
    grid, nrows, ncols = _copy_matrix(matrix)
    if isinstance(row, bool) or not _is_int(row):
        raise MatrixError("行号必须是整数")
    if row < 0 or row >= nrows:
        raise MatrixError("行号越界")
    return [col for col in range(ncols) if grid[row][col]]


def conflict_columns(matrix, rows):
    """给定行集合里互相冲突的列，返回升序去重的列号列表。

    一列被覆盖两次及以上就算冲突。空行集合返回空列表。
    """
    grid, nrows, ncols = _copy_matrix(matrix)
    picked = list(rows or [])
    for row in picked:
        if isinstance(row, bool) or not _is_int(row):
            raise MatrixError("行号必须是整数")
        if row < 0 or row >= nrows:
            raise MatrixError("行号越界")
    cover = [0] * ncols
    for row in picked:
        for col in range(ncols):
            if grid[row][col]:
                cover[col] += 1
    return [col for col in range(ncols) if cover[col] > 1]


def search_steps(matrix):
    """求解过程中探测过的状态规模，用来和规模更好的做法做对照。

    对每个行子集逐列数覆盖次数，看它是不是一个部分覆盖，最后把通过检查的列数
    累加起来。结果对小矩阵可复现，规模一大就明显膨胀。
    """
    grid, nrows, ncols = _copy_matrix(matrix)
    total = 0
    for mask in range(1 << nrows):
        if mask == 0:
            continue
        for col in range(ncols):
            count = 0
            for row in range(nrows):
                if mask & (1 << row) and grid[row][col]:
                    count += 1
            if count > 1:
                break
            if count == 1:
                total += 1
    return total
