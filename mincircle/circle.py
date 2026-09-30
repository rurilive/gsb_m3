"""circle: 改造前的最小圆覆盖工具。

这里只有最直接的做法：先把所有点两两配对，求出每一对点确定的最小圆；再枚
举所有三点组合，求出过这三点的外接圆；把这些候选圆逐条记下来，然后拿每一
个候选到全部点里逐点核验，能包住全部点的才算合格；在合格的候选里挑平方半
径最小的那一个。空点集给零半径的零圆，单点给以该点为心的零半径圆，两点给
以两点连线为直径的圆。点的坐标一律是整数；圆心与半径都用精确的有理数表示，
半径一律以平方半径参与比较与取舍，全程不碰浮点，也不开平方，结果没有半分
不确定性。整体先枚举点对与三点、再对每个候选逐点核验，规模一大就立方甚至
更高，点一多就撑不住。本文件是改造前的基线，不含任何增量式随机结构。
"""

from fractions import Fraction

__all__ = ["Erro", "Circle", "brute_min_circle"]


class Erro(Exception):
    """本模块所有自定义错误的基类。"""


class Circle:
    """一个圆，圆心与平方半径都是精确的有理数。

    平面上一个点，横纵坐标各自是一个有理数。平方半径就是半径的平方，也是
    一个有理数，一律用它参与比较，不去开平方。圆心坐标与平方半径都可以写
    成两个整数之比，所以全程是精确运算，不引入任何浮点。空点集的圆，圆心在
    原点、平方半径为零；单点的圆，圆心就是该点、平方半径为零。
    """

    __slots__ = ("cx", "cy", "r2")

    def __init__(self, cx, cy, r2):
        self.cx = Fraction(cx)
        self.cy = Fraction(cy)
        self.r2 = Fraction(r2)

    def __eq__(self, other):
        if not isinstance(other, Circle):
            return NotImplemented
        return (
            self.cx == other.cx
            and self.cy == other.cy
            and self.r2 == other.r2
        )

    def __hash__(self):
        return hash((self.cx, self.cy, self.r2))

    def __repr__(self):
        return "Circle(cx=%s, cy=%s, r2=%s)" % (self.cx, self.cy, self.r2)

    def contains(self, point):
        """判断这个圆是不是包住了给定的一个点。

        点到圆心的距离平方不超过平方半径就算包住，两边都是精确有理数，全
        程比较即可，无需开平方。
        """
        x, y = point
        dx = Fraction(x) - self.cx
        dy = Fraction(y) - self.cy
        return dx * dx + dy * dy <= self.r2


def _normalize(points):
    """校验点集并原样返回一串坐标对。

    点集必须是一串点，每个点是一对整数坐标。原样保留输入顺序与重复出现的
    点；重复点对覆盖结果没有影响，但也接受，不做去重。
    """
    if not isinstance(points, (list, tuple)):
        raise Erro("点集必须是列表或元组")
    out = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise Erro("每个点必须是两个整数组成的一对")
        x, y = p[0], p[1]
        if isinstance(x, bool) or isinstance(y, bool):
            raise Erro("点的坐标必须是整数")
        if not isinstance(x, int) or not isinstance(y, int):
            raise Erro("点的坐标必须是整数")
        out.append((x, y))
    return out


def _circle_of_pair(a, b):
    """两点定圆：圆心取中点，平方半径取距离平方的四分之一。

    两点连线的中点就是圆心，两点距离的一半就是半径，半径的平方记成整数比
    的形式，全程精确。
    """
    cx = Fraction(a[0] + b[0], 2)
    cy = Fraction(a[1] + b[1], 2)
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    r2 = Fraction(dx * dx + dy * dy, 4)
    return Circle(cx, cy, r2)


def _circle_of_triple(a, b, c):
    """三点定圆：求过这三点的外接圆，三点共线时返回空。

    以第一个点为基准，取两条边的向量与它们对应的平方和之差，解出圆心坐标；
    若三点共线，两条垂直平分线平行，判别式为零，此时返回空，交由调用方判定。
    """
    ax, ay = a[0], a[1]
    ux, uy = b[0] - ax, b[1] - ay
    vx, vy = c[0] - ax, c[1] - ay
    det = ux * vy - uy * vx
    if det == 0:
        return None
    r1 = (b[0] * b[0] + b[1] * b[1]) - (a[0] * a[0] + a[1] * a[1])
    r2 = (c[0] * c[0] + c[1] * c[1]) - (a[0] * a[0] + a[1] * a[1])
    cx = Fraction(r1 * vy - r2 * uy, 2 * det)
    cy = Fraction(ux * r2 - vx * r1, 2 * det)
    dx = cx - ax
    dy = cy - ay
    rr = dx * dx + dy * dy
    return Circle(cx, cy, rr)


def _covers(circle, points):
    """核验一个圆是不是包住了给定的全部点。"""
    for p in points:
        if not circle.contains(p):
            return False
    return True


def brute_min_circle(points):
    """枚举全部点对与三点组合，求覆盖全部点的最小圆。

    先把每一对点确定的最小圆作为候选，再枚举所有三点组合求外接圆，逐条放
    进候选表；随后把每一个候选拿到全部点里逐点核验，只留能包住全部点的；
    在合格的候选里取平方半径最小的那一个作为答案。空点集与单点由入口处直
    接给出。
    """
    pts = _normalize(points)
    n = len(pts)
    if n == 0:
        return Circle(0, 0, 0)
    if n == 1:
        return Circle(pts[0][0], pts[0][1], 0)
    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            candidates.append(_circle_of_pair(pts[i], pts[j]))
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                cand = _circle_of_triple(pts[i], pts[j], pts[k])
                if cand is not None:
                    candidates.append(cand)
    best = None
    for cand in candidates:
        if not _covers(cand, pts):
            continue
        if best is None or cand.r2 < best.r2:
            best = cand
    if best is None:
        best = _circle_of_pair(pts[0], pts[0])
    return best
