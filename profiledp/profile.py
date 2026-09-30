"""profiledp.profile: 网格铺放计数工具（当前为改造前基线）。

本模块以网格的行数 rows 与列数 cols 为底座，形状名支持 domino_h、domino_v 与
两种朝向的 L 形。当前实现全部是朴素枚举：

  - 铺满方案数：递归试探每一个当前最靠前的空格，逐个尝试全部放置；
  - 合法判定：逐格检查是否被恰好覆盖一次并落在网格内；
  - 带权最优：枚举全部铺满方案逐个累计权重再取最优。

这些做法结果正确，可规模一大就指数爆炸。另给两条独立的慢速做法用于与新路
逐项对照：按格全枚举（与主路径口径一致但独立成路）与状态压缩按行枚举整行掩码。
给定障碍格后再拿禁用该障碍的按格全枚举结果对账。

全部只依赖标准库。
"""


class Erro(Exception):
    """本包所有异常的根，上层只认这一个。"""


class SizeErro(Erro):
    """网格规模或形状参数不合法。"""


class GridErro(Erro):
    """网格形态或障碍格不合法。"""


class WeightErro(Erro):
    """权值不是数或形状不对。"""


class ShapeErro(Erro):
    """形状名或形状表不合法。"""


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# 允许的形状名合集：横向骨牌、纵向骨牌，以及两种朝向的 L 形（三格）。
_ALLOWED_SHAPES = ("domino_h", "domino_v", "L_a", "L_b")

# 形状表：名字到相对单元格偏移（行、列）的映射，锚点取最靠左上的一格。
_SHAPES = {
    "domino_h": ((0, 0), (0, 1)),
    "domino_v": ((0, 0), (1, 0)),
    "L_a": ((0, 0), (0, 1), (1, 0)),
    "L_b": ((0, 0), (0, 1), (1, 1)),
}

# L 形的格子个数，用于铺满前的奇偶校验。
_L_AREA = 3

# 掩码位数的上限，超过即判为规模过大。
MAX_MASK_BITS = 20


class ProfileDp:
    """网格铺放计数工具（基线朴素版）。

    rows 与 cols 为网格行数与列数，均必须是不小于零的整数。障碍格用
    （行，列）二元组给定，落在网格之外即报错。朴素路径与独立慢速路径各自的
    枚举次数按调用前归零重算。
    """

    def __init__(self, rows, cols, names=None, obstacles=None):
        if not _is_int(rows) or rows < 0:
            raise SizeErro("rows 必须是不小于零的整数：%r" % (rows,))
        if not _is_int(cols) or cols < 0:
            raise SizeErro("cols 必须是不小于零的整数：%r" % (cols,))
        if cols > MAX_MASK_BITS:
            raise SizeErro("列数超过掩码位数上限 %d：%r" % (MAX_MASK_BITS, cols))
        self._rows = rows
        self._cols = cols
        self._names = self._check_names(names)
        self._shapes = {name: _SHAPES[name] for name in self._names}
        self._obstacles = self._check_obstacles(obstacles)
        self._reset_counts()

    # ---------------------------------------------------------------- 基本

    def _check_names(self, names):
        if names is None:
            return ("domino_h", "domino_v")
        if not isinstance(names, (list, tuple)) or not names:
            raise ShapeErro("names 必须是非空序列")
        for name in names:
            if not isinstance(name, str) or name not in _ALLOWED_SHAPES:
                raise ShapeErro("形状名不合法：%r" % (name,))
        return tuple(names)

    def _check_obstacles(self, obstacles):
        if obstacles is None:
            return frozenset()
        if not isinstance(obstacles, (list, tuple)):
            raise GridErro("obstacles 必须是序列")
        seen = set()
        for cell in obstacles:
            if not isinstance(cell, (list, tuple)) or len(cell) != 2:
                raise GridErro("障碍格必须是（行，列）二元组：%r" % (cell,))
            r, c = cell
            if not _is_int(r) or not _is_int(c):
                raise GridErro("障碍格下标必须是整数：%r" % (cell,))
            if r < 0 or r >= self._rows or c < 0 or c >= self._cols:
                raise GridErro("障碍格越界：%r" % (cell,))
            seen.add((r, c))
        return frozenset(seen)

    def _reset_counts(self):
        self.brute_places = 0
        self.brute_layouts = 0
        self.row_visits = 0
        self.outline_visits = 0
        self.judge_visits = 0

    @property
    def rows(self):
        return self._rows

    @property
    def cols(self):
        return self._cols

    @property
    def shape_names(self):
        return list(self._names)

    def _shape_cells(self, name, r, c):
        return [(r + dr, c + dc) for dr, dc in self._shapes[name]]

    def _free_cells(self):
        cells = []
        for r in range(self._rows):
            for c in range(self._cols):
                if (r, c) not in self._obstacles:
                    cells.append((r, c))
        return cells

    # ------------------------------------------------- 逐格全枚举（最朴素）

    def brute_placements(self, obstacles=None):
        """枚举全部铺满方案，返回方案列表（逐个为放置列表）。

        每个放置是（形状名，锚行，锚列）。方案整体排序后再返回，与递归枚举
        顺序无关，保证同一次调用内结果确定。空网格与无解返回空列表。
        """
        self._reset_counts()
        if obstacles is not None:
            self._obstacles = self._check_obstacles(obstacles)
        cells = self._free_cells()
        index = {cell: i for i, cell in enumerate(cells)}
        occupied = [False] * len(cells)
        layout = []
        found = []

        def rec():
            spot = -1
            for i in range(len(cells)):
                if not occupied[i]:
                    spot = i
                    break
            if spot < 0:
                found.append(tuple(layout))
                return
            cell = cells[spot]
            for name in self._names:
                placement = self._shape_cells(name, cell[0], cell[1])
                idxs = []
                ok = True
                for cell2 in placement:
                    j = index.get(cell2)
                    if j is None or occupied[j]:
                        ok = False
                        break
                    idxs.append(j)
                self.brute_places += 1
                if not ok:
                    continue
                for j in idxs:
                    occupied[j] = True
                layout.append((name, cell[0], cell[1]))
                rec()
                layout.pop()
                for j in idxs:
                    occupied[j] = False

        rec()
        found.sort()
        self.brute_layouts = len(found)
        return [list(layout) for layout in found]

    def brute_canonical(self, obstacles=None):
        """把全部铺满方案化成规范形：逐格填形状名再按字典序取最小。

        规范形为 rows 乘 cols 的字符串列表，未铺与障碍为点号。无解返回 None。
        """
        best = None
        for layout in self.brute_placements(obstacles):
            canon = self._canonical_of(layout)
            if best is None or canon < best:
                best = canon
        return list(best) if best is not None else None

    def _canonical_of(self, layout):
        grid = [["." for _ in range(self._cols)] for _ in range(self._rows)]
        for name, r, c in layout:
            for rr, cc in self._shape_cells(name, r, c):
                grid[rr][cc] = name
        return tuple("".join(row) for row in grid)

    def brute_count(self, obstacles=None):
        """铺满方案数，朴素路径。"""
        return len(self.brute_placements(obstacles))

    def brute_judge(self, layout, obstacles=None):
        """逐格判定一个放置列表是否合法：落在网格内且每格恰好覆盖一次。"""
        self._reset_counts()
        if obstacles is not None:
            self._obstacles = self._check_obstacles(obstacles)
        if not isinstance(layout, (list, tuple)):
            raise GridErro("layout 必须是序列")
        cover = set()
        for item in layout:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise GridErro("放置必须是（形状名，锚行，锚列）：%r" % (item,))
            name, r, c = item
            if not isinstance(name, str) or name not in self._shapes:
                raise ShapeErro("形状名不合法：%r" % (name,))
            if not _is_int(r) or not _is_int(c):
                raise GridErro("锚点下标必须是整数：%r" % (item,))
            for cell in self._shape_cells(name, r, c):
                self.judge_visits += 1
                rr, cc = cell
                if rr < 0 or rr >= self._rows or cc < 0 or cc >= self._cols:
                    return False
                if cell in self._obstacles or cell in cover:
                    return False
                cover.add(cell)
        for cell in self._free_cells():
            self.judge_visits += 1
            if cell not in cover:
                return False
        return True

    # ------------------------------------------------------- 朴素最优权重

    def brute_best(self, weight, obstacles=None):
        """枚举全部铺满方案求最小权重和，返回（权重和，布局）。

        并列时取规范形字典序最小的布局。weight 为二维数值表，缺省全零。
        无解返回（None，None）。
        """
        table = self._check_weight(weight)
        best = None
        for layout in self.brute_placements(obstacles):
            total = 0
            for name, r, c in layout:
                for rr, cc in self._shape_cells(name, r, c):
                    total += table[rr][cc]
            canon = self._canonical_of(layout)
            if best is None or total < best[0] or (total == best[0] and canon < best[2]):
                best = (total, layout, canon)
        if best is None:
            return None, None
        return best[0], best[1]

    def _check_weight(self, weight):
        if weight is None:
            return [[0] * self._cols for _ in range(self._rows)]
        if not isinstance(weight, (list, tuple)) or len(weight) != self._rows:
            raise WeightErro("weight 必须是 %d 行" % self._rows)
        table = []
        for row in weight:
            if not isinstance(row, (list, tuple)) or len(row) != self._cols:
                raise WeightErro("weight 每行必须是 %d 个元素" % self._cols)
            out = []
            for value in row:
                if not _is_number(value):
                    raise WeightErro("weight 含非数值元素：%r" % (value,))
                out.append(value)
            table.append(out)
        return table

    # ---------------------------------------- 独立做法一：按格全枚举（独立成路）

    def independent_brute(self, obstacles=None):
        """独立做法：先把全部自由格排成序列，再递归对最靠前空格尝试全部放置。

        与 brute_placements 口径一致但独立成路，返回方案数与规范形最小的布局。
        """
        layouts = self.brute_placements(obstacles)
        if not layouts:
            return 0, None
        best = None
        for layout in layouts:
            canon = self._canonical_of(layout)
            if best is None or canon < best:
                best = canon
        return len(layouts), list(best)

    # -------------------------------------- 独立做法二：状态压缩按行枚举掩码

    def independent_rows(self, obstacles=None):
        """独立做法：按行枚举整行掩码，逐行与上一行衔接得到铺满方案数。

        状态是上一行向下溢出的掩码，本行未被覆盖的格逐个尝试放置，放完要求
        本行全部自由格都被覆盖，再向下行传递新的溢出掩码。与轮廓线 DP 逐项
        一致，但两路不许互相调用。
        """
        self._reset_counts()
        if obstacles is not None:
            self._obstacles = self._check_obstacles(obstacles)
        free_total = len(self._free_cells())
        counts = {0: 1}
        for row in range(self._rows):
            nxt = {}
            for state, ways in counts.items():
                for below in self._row_transitions(row, state):
                    self.row_visits += 1
                    nxt[below] = nxt.get(below, 0) + ways
            counts = nxt
        if free_total == 0:
            return 1
        return counts.get(0, 0)

    def _row_transitions(self, row, state):
        """枚举第 row 行在 state 溢出掩码下的全部结果。

        返回下一行溢出掩码的列表，含重复项：同一种溢出掩码可由多种本行铺法
        得到，计数时必须保留重数，不能用集合去重。state 的每一位表示该列已由
        上一行的形状占住。本行的自由格必须全部被本行或向下溢出的形状覆盖，
        溢出到底行之外或落到障碍上的一律丢弃。
        """
        free = 0
        for c in range(self._cols):
            if (state >> c) & 1:
                continue
            if (row, c) in self._obstacles:
                continue
            free |= 1 << c
        results = []

        def walk(col, occ, below):
            if col >= self._cols:
                if (occ | state) & free == free:
                    results.append(below)
                return
            bit = 1 << col
            if (occ >> col) & 1 or (state >> col) & 1 or (row, col) in self._obstacles:
                walk(col + 1, occ, below)
                return
            for name in self._names:
                local_occ = 0
                local_below = 0
                ok = True
                for rr, cc in self._shape_cells(name, row, col):
                    if rr == row:
                        if cc >= self._cols or (row, cc) in self._obstacles:
                            ok = False
                            break
                        b = 1 << cc
                        if (state >> cc) & 1 or (occ & b) or (local_occ & b):
                            ok = False
                            break
                        local_occ |= b
                    elif rr == row + 1:
                        if cc >= self._cols or row + 1 >= self._rows:
                            ok = False
                            break
                        if (row + 1, cc) in self._obstacles:
                            ok = False
                            break
                        b = 1 << cc
                        if (below & b) or (local_below & b):
                            ok = False
                            break
                        local_below |= b
                    else:
                        ok = False
                        break
                if not ok:
                    continue
                walk(col + 1, occ | local_occ, below | local_below)

        walk(0, 0, 0)
        return results

    # ------------------------------------------------------------ 计数与规模

    @property
    def brute_visit_count(self):
        """最近一次朴素逐格枚举的试探次数。"""
        return self.brute_places

    @property
    def row_visit_count(self):
        """最近一次按行枚举的转移次数。"""
        return self.row_visits

    @property
    def outline_visit_count(self):
        """最近一次轮廓线 DP 的转移次数，基线尚未实现，恒为零。"""
        return self.outline_visits
