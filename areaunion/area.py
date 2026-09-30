"""areaunion 基线实现：轴对齐矩形集合的面积与周长工具的最朴素做法。

全部能力都把横纵坐标离散化后对每个小格逐个判定，格子数是坐标数量的平方，
矩形一多就慢，但结果正确。本文件是改造前的现状，不是最终应当的样子。
"""

__all__ = [
    "RectSet",
    "Erro",
    "RectErro",
    "CountErro",
    "IndexErro",
]


class Erro(Exception):
    """本包全部异常的基类。"""


class RectErro(Erro):
    """矩形数据不合法。"""


class CountErro(Erro):
    """覆盖次数参数不合法。"""


class IndexErro(Erro):
    """下标不合法。"""


def _is_int(x):
    """严格整数判定，布尔不算整数。"""
    return isinstance(x, int) and not isinstance(x, bool)


def _check_rect(raw, what):
    """校验一个矩形，返回四元组 (x1, y1, x2, y2)。"""
    if not isinstance(raw, (tuple, list)) or len(raw) != 4:
        raise RectErro("%s 必须是四元组" % what)
    x1, y1, x2, y2 = raw[0], raw[1], raw[2], raw[3]
    for v in (x1, y1, x2, y2):
        if not _is_int(v):
            raise RectErro("%s 端点必须是整数" % what)
    if x1 > x2:
        raise RectErro("%s 左端不得大于右端" % what)
    if y1 > y2:
        raise RectErro("%s 下端不得大于上端" % what)
    return (x1, y1, x2, y2)


class RectSet(object):
    """一个轴对齐矩形集合，附带并集面积、周长与覆盖次数面积等朴素查询。"""

    def __init__(self, rects=()):
        items = []
        if not isinstance(rects, (tuple, list)):
            raise RectErro("矩形集合必须是元组或列表")
        for i, raw in enumerate(rects):
            items.append(_check_rect(raw, "第 %d 个矩形" % i))
        self._items = items
        self._judge_calls = 0

    @property
    def rects(self):
        return list(self._items)

    def count(self):
        return len(self._items)

    # ---------- 坐标离散化 ----------

    def _xs(self):
        values = []
        for x1, y1, x2, y2 in self._items:
            values.append(x1)
            values.append(x2)
        return _unique_sorted(values)

    def _ys(self):
        values = []
        for x1, y1, x2, y2 in self._items:
            values.append(y1)
            values.append(y2)
        return _unique_sorted(values)

    def cell_count(self):
        """离散化后正面积小格的个数，是朴素逐格路的工作量来源。"""
        xs = self._xs()
        ys = self._ys()
        if len(xs) < 2 or len(ys) < 2:
            return 0
        return (len(xs) - 1) * (len(ys) - 1)

    def _contains_cell(self, rect, xa, xb, ya, yb):
        """判断一个矩形是否完整包含指定的正面积小格。"""
        x1, y1, x2, y2 = rect
        return x1 <= xa and xb <= x2 and y1 <= ya and yb <= y2

    def _covered_grid(self):
        """逐小格逐矩形判定，返回覆盖布尔矩阵，并记录判定次数。

        每个小格遇到第一个覆盖它的矩形就停下，不再看后面的矩形。
        """
        xs = self._xs()
        ys = self._ys()
        nx = len(xs) - 1
        ny = len(ys) - 1
        self._judge_calls = 0
        grid = []
        for i in range(nx):
            xa = xs[i]
            xb = xs[i + 1]
            column = []
            for j in range(ny):
                ya = ys[j]
                yb = ys[j + 1]
                covered = False
                for rect in self._items:
                    self._judge_calls += 1
                    if self._contains_cell(rect, xa, xb, ya, yb):
                        covered = True
                        break
                column.append(covered)
            grid.append(column)
        return xs, ys, grid

    def _count_grid(self):
        """逐小格把全部矩形都数一遍，返回每格被覆盖的次数矩阵。

        与覆盖布尔矩阵不同，这里对每个小格从不提前退出，把每个矩形都判一次，
        因此判定次数与小格数、矩形数之积成正比。
        """
        xs = self._xs()
        ys = self._ys()
        nx = len(xs) - 1
        ny = len(ys) - 1
        self._judge_calls = 0
        grid = []
        for i in range(nx):
            xa = xs[i]
            xb = xs[i + 1]
            column = []
            for j in range(ny):
                ya = ys[j]
                yb = ys[j + 1]
                c = 0
                for rect in self._items:
                    self._judge_calls += 1
                    if self._contains_cell(rect, xa, xb, ya, yb):
                        c += 1
                column.append(c)
            grid.append(column)
        return xs, ys, grid

    # ---------- 逐点判定 ----------

    def covers_point(self, x, y):
        """返回覆盖该点的矩形下标序列，边界算覆盖。"""
        if not _is_int(x) or not _is_int(y):
            raise RectErro("查询点坐标必须是整数")
        hits = []
        for i in range(len(self._items)):
            x1, y1, x2, y2 = self._items[i]
            if x1 <= x and x <= x2 and y1 <= y and y <= y2:
                hits.append(i)
        return hits

    def coverage_count_at(self, x, y):
        return len(self.covers_point(x, y))

    def is_covered(self, x, y):
        for x1, y1, x2, y2 in self._items:
            if x1 <= x and x <= x2 and y1 <= y and y <= y2:
                return True
        return False

    # ---------- 面积 ----------

    def union_area(self):
        """覆盖至少一次的并集面积，逐小格逐矩形判定，遇覆盖即停。"""
        xs, ys, grid = self._covered_grid()
        total = 0
        for i in range(len(grid)):
            width = xs[i + 1] - xs[i]
            if width <= 0:
                continue
            for j in range(len(grid[i])):
                if not grid[i][j]:
                    continue
                height = ys[j + 1] - ys[j]
                if height > 0:
                    total += width * height
        return total

    def area_at_least(self, k):
        """被至少 k 个矩形覆盖的面积，逐小格把矩形全数一遍。"""
        if not _is_int(k) or k < 1:
            raise CountErro("覆盖次数必须是正整数")
        xs, ys, grid = self._count_grid()
        total = 0
        for i in range(len(grid)):
            width = xs[i + 1] - xs[i]
            if width <= 0:
                continue
            for j in range(len(grid[i])):
                if grid[i][j] < k:
                    continue
                height = ys[j + 1] - ys[j]
                if height > 0:
                    total += width * height
        return total

    def area_exactly(self, k):
        """恰好被 k 个矩形覆盖的面积，k 可以为零。"""
        if not _is_int(k) or k < 0:
            raise CountErro("覆盖次数必须是非负整数")
        xs, ys, grid = self._count_grid()
        total = 0
        for i in range(len(grid)):
            width = xs[i + 1] - xs[i]
            if width <= 0:
                continue
            for j in range(len(grid[i])):
                if grid[i][j] != k:
                    continue
                height = ys[j + 1] - ys[j]
                if height > 0:
                    total += width * height
        return total

    def max_overlap(self):
        """离散小格上的最大覆盖次数。"""
        xs, ys, grid = self._count_grid()
        best = 0
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if grid[i][j] > best:
                    best = grid[i][j]
        return best

    # ---------- 周长 ----------

    def perimeter(self):
        """并集区域边界的总周长，水平边与垂直边分别累加。

        先取覆盖布尔矩阵，再在小格的边上找覆盖与未覆盖的分界：
        水平边在小格上下两侧取值不同时计入，垂直边在小格左右两侧取值不同时计入。
        只统计正面积覆盖，退化矩形不计。
        """
        xs, ys, grid = self._covered_grid()
        nx = len(grid)
        ny = len(grid[0]) if nx else 0

        def cell(i, j):
            if i < 0 or j < 0 or i >= nx or j >= ny:
                return False
            return grid[i][j]

        total = 0
        # 水平边：沿每一条横坐标线，看上下相邻小格的覆盖是否不同。
        for j in range(ny + 1):
            edge = 0
            for i in range(nx):
                if cell(i, j - 1) != cell(i, j):
                    edge += xs[i + 1] - xs[i]
            total += edge
        # 垂直边：沿每一条纵坐标线，看左右相邻小格的覆盖是否不同。
        for i in range(nx + 1):
            edge = 0
            for j in range(ny):
                if cell(i - 1, j) != cell(i, j):
                    edge += ys[j + 1] - ys[j]
            total += edge
        return total

    # ---------- 独立逐格标记做法 ----------

    def independent_brute_area(self):
        """独立做法一：离散化后对每个小格完整统计覆盖次数，再累加正次数面积。

        与 union_area 不同，这里对每个小格都把所有矩形判一遍，从不提前退出。
        """
        xs, ys, grid = self._count_grid()
        total = 0
        for i in range(len(grid)):
            width = xs[i + 1] - xs[i]
            for j in range(len(grid[i])):
                if grid[i][j] >= 1 and width > 0:
                    height = ys[j + 1] - ys[j]
                    if height > 0:
                        total += width * height
        return total

    def independent_brute_area_at_least(self, k):
        """独立做法二：离散化后逐格统计覆盖次数，取不低于 k 次的面积。"""
        if not _is_int(k) or k < 1:
            raise CountErro("覆盖次数必须是正整数")
        xs, ys, grid = self._count_grid()
        total = 0
        for i in range(len(grid)):
            width = xs[i + 1] - xs[i]
            for j in range(len(grid[i])):
                if grid[i][j] >= k and width > 0:
                    height = ys[j + 1] - ys[j]
                    if height > 0:
                        total += width * height
        return total

    def independent_brute_perimeter(self):
        """独立做法三：从逐格标记矩阵上单独数一遍水平边与垂直边。"""
        xs, ys, grid = self._covered_grid()
        nx = len(grid)
        ny = len(grid[0]) if nx else 0
        horizontal = 0
        vertical = 0
        for i in range(nx):
            for j in range(ny):
                if not grid[i][j]:
                    continue
                w = xs[i + 1] - xs[i]
                h = ys[j + 1] - ys[j]
                above = j > 0 and grid[i][j - 1]
                below = j + 1 < ny and grid[i][j + 1]
                left = i > 0 and grid[i - 1][j]
                right = i + 1 < nx and grid[i + 1][j]
                if not above:
                    horizontal += w
                if not below:
                    horizontal += w
                if not left:
                    vertical += h
                if not right:
                    vertical += h
        return horizontal + vertical

    # ---------- 全套结果与朴素代价 ----------

    def solve_all(self, k=1):
        """把并集面积、周长、至少 k 次面积与恰好 k 次面积一起求出。"""
        at_least = self.area_at_least(k)
        result = {
            "union_area": self.union_area(),
            "perimeter": self.perimeter(),
            "area_at_least": at_least,
            "area_exactly": self.area_exactly(k),
        }
        return result

    def judge_count(self):
        """最近一次逐格计算里判定小格与矩形的总次数。"""
        return self._judge_calls

    def node_access_count(self):
        """扫描线线段树结点访问次数，逐格基线恒为零。"""
        return 0


def _unique_sorted(values):
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    seen.sort()
    return seen
