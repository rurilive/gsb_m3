"""minplus.minplus：最小加矩阵与递推的朴素实现（改造前基线）。

围绕有向带权图与最小加代数做三件最基础的事：

  - shortest_paths   固定步数最短路：从每个起点出发，走恰好若干步后到每个终点的
                     最短距离。做成一张距离表，每推进一步就把整张表重新扫一遍做
                     重复松弛，步数多大就扫多少遍，一遍是立方量级。
  - step_transitions 定步数状态转移：给一张初值向量，每转移一步就按边逐项枚举取
                     最小加，推一步整条向量重扫一遍，步数多大就推多少步。
  - matrix_power     最小加矩阵的幂：把同一个矩阵连乘幂次那么多遍，指数多大就要做
                     多少次矩阵乘法，每次乘法又是立方量级的三重循环。

另有 mat_mul 做一次最小加矩阵乘法。无穷大用 math.inf 表示，最小加乘法里
无穷加任何数仍是无穷，因此不可达点在结果里保持无穷。这些做法直观可靠，结果一眼
能看穿，可步数或指数一大就退化成线性乃至立方量级。

本文件是改造前的基线，朴素路径在改造之后不得删除，新的快速路径必须与它对同一批
输入给出的结果逐项对齐。

异常统一继承 MinPlusErro 基类：MatrixErro / PatternErro。
"""

import math

INF = math.inf


class MinPlusErro(Exception):
    """minplus 所有异常的基类，非法输入与非法操作一律快速失败。"""


class MatrixErro(MinPlusErro):
    """矩阵或边非法：形状参差不齐、行列不匹配、边不是三元组、边权不是实数、向量长度不符。"""


class PatternErro(MinPlusErro):
    """步数非法：步数不是整数或为负数。"""


# ---------------------------------------------------------------------------
# 规整与校验
# ---------------------------------------------------------------------------

def _norm_steps(steps, where):
    """步数必须是整数且非负，布尔不算整数，非法抛 PatternErro。"""
    if isinstance(steps, bool) or not isinstance(steps, int):
        raise PatternErro("%s：步数必须是整数，收到 %r" % (where, steps))
    if steps < 0:
        raise PatternErro("%s：步数不能为负，收到 %r" % (where, steps))
    return steps


def _norm_weight(weight):
    """边权必须是实数，布尔不算，非法抛 MatrixErro。"""
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise MatrixErro("边权必须是实数，收到 %r" % (weight,))
    return float(weight)


def _norm_matrix(matrix, where):
    """把矩阵规整成行列表并校验各行等长，非法抛 MatrixErro。"""
    if isinstance(matrix, (str, bytes)):
        raise MatrixErro("%s：矩阵必须是可迭代的行序列，收到 %r" % (where, matrix))
    try:
        rows = [list(row) for row in matrix]
    except TypeError:
        raise MatrixErro("%s：矩阵必须是可迭代的行序列，收到 %r" % (where, matrix))
    if rows:
        width = len(rows[0])
        for i in range(1, len(rows)):
            if len(rows[i]) != width:
                raise MatrixErro("%s：第 %d 行长度与首行不一致" % (where, i + 1))
    return rows


def _norm_vector(vec, where):
    """把向量规整成实数列表，非法抛 MatrixErro。"""
    if isinstance(vec, (str, bytes)):
        raise MatrixErro("%s：向量必须是可迭代的实数序列，收到 %r" % (where, vec))
    try:
        return [float(x) for x in vec]
    except (TypeError, ValueError):
        raise MatrixErro("%s：向量元素必须是实数，收到 %r" % (where, vec))


def _collect(nodes, edges):
    """整理节点顺序与边三元组；节点按出现顺序登记，重复登记保持不变。

    返回 (order, index, triples)，triples 里的边权已规整成实数。边不是三元组或
    边权不是实数，抛 MatrixErro。
    """
    order = []
    index = {}

    def register(node):
        if node not in index:
            index[node] = len(order)
            order.append(node)

    for node in nodes or ():
        register(node)
    triples = []
    for item in edges or ():
        try:
            u, v, w = item
        except (TypeError, ValueError):
            raise MatrixErro("边必须是 (u, v, weight) 三元组，收到 %r" % (item,))
        register(u)
        register(v)
        triples.append((u, v, _norm_weight(w)))
    return order, index, triples


def _base_matrix(triples, index, size):
    """一步转移矩阵：对角线为无穷，只放显式边，平行边取最小权，自环照常写入。

    对角线不用零填充，走一步就必须离开原地，这样矩阵的幂才严格对应到恰好走
    若干步；原地不动的语义由零步时的单位矩阵给出。
    """
    dist = [[INF] * size for _ in range(size)]
    for u, v, w in triples:
        i = index[u]
        j = index[v]
        if w < dist[i][j]:
            dist[i][j] = w
    return dist


def _identity(size):
    """最小加单位矩阵：对角线为零，其余为无穷。"""
    return [[0.0 if i == j else INF for j in range(size)] for i in range(size)]


# ---------------------------------------------------------------------------
# 最小加矩阵乘法与幂（朴素）
# ---------------------------------------------------------------------------

def _mat_mul(a, b):
    """最小加矩阵乘法：三重循环，逐对取最小加。假定形状已校验。"""
    rows = len(a)
    cols = len(b[0]) if b else 0
    inner = len(b)
    out = [[INF] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            best = INF
            for t in range(inner):
                cand = a[i][t] + b[t][j]
                if cand < best:
                    best = cand
            out[i][j] = best
    return out


def mat_mul(a, b):
    """最小加矩阵乘法，形状不匹配抛 MatrixErro，空矩阵按平凡结果处理。"""
    a = _norm_matrix(a, "mat_mul 左矩阵")
    b = _norm_matrix(b, "mat_mul 右矩阵")
    if a and b and len(a[0]) != len(b):
        raise MatrixErro("mat_mul：左矩阵列数 %d 与右矩阵行数 %d 不匹配"
                         % (len(a[0]), len(b)))
    if not a or not b:
        return []
    return _mat_mul(a, b)


def _check_square(matrix, where):
    size = len(matrix)
    for i in range(size):
        if len(matrix[i]) != size:
            raise MatrixErro("%s：只支持方阵，第 %d 行长度不是 %d"
                             % (where, i + 1, size))
    return size


def matrix_power(a, exponent):
    """最小加矩阵的幂：把矩阵连乘 exponent 遍，零次幂给单位矩阵。

    指数为负或不是整数抛 PatternErro；非方阵抛 MatrixErro。指数很大时这里要做
    指数那么多次矩阵乘法。
    """
    a = _norm_matrix(a, "matrix_power 底矩阵")
    exponent = _norm_steps(exponent, "matrix_power 幂次")
    size = _check_square(a, "matrix_power")
    if size == 0:
        return []
    out = _identity(size)
    for _ in range(exponent):
        out = _mat_mul(out, a)
    return out


# ---------------------------------------------------------------------------
# 固定步数最短路（重复松弛）
# ---------------------------------------------------------------------------

def _walk(base, steps):
    """从单位矩阵起，每步用一步转移矩阵把整张表重扫一遍，做 steps 遍。

    表 cur 记恰好走 k 步的最短距离：cur 起初是零步的单位矩阵，之后
    new[i][j] = min over t (cur[i][t] + base[t][j])，一遍推进一条边。步数多大就
    扫多少遍，是立方量级乘以步数。
    """
    size = len(base)
    cur = _identity(size)
    for _ in range(steps):
        nxt = [[INF] * size for _ in range(size)]
        for i in range(size):
            curi = cur[i]
            for j in range(size):
                best = INF
                for t in range(size):
                    cand = curi[t] + base[t][j]
                    if cand < best:
                        best = cand
                nxt[i][j] = best
        cur = nxt
    return cur


def shortest_paths(nodes, edges, steps):
    """恰好走 steps 步的最短距离表，返回 (矩阵, 节点顺序)。

    steps 为零给单位矩阵（对角线为零，其余为无穷）；不可达点保持无穷。步数非法
    抛 PatternErro，边非法抛 MatrixErro。
    """
    steps = _norm_steps(steps, "shortest_paths 步数")
    order, index, triples = _collect(nodes, edges)
    size = len(order)
    if size == 0:
        return [], order
    base = _base_matrix(triples, index, size)
    return _walk(base, steps), order


# ---------------------------------------------------------------------------
# 定步数状态转移（逐步枚举）
# ---------------------------------------------------------------------------

def step_transitions(init, nodes, edges, steps):
    """初值向量按一步转移推 steps 步，返回 (向量, 节点顺序)。

    每推进一步就按边逐项枚举取最小加：new[j] = min over i (cur[i] + base[i][j])，
    推一步整条向量重扫一遍。steps 为零返回初值本身。初值长度与节点数不符抛
    MatrixErro。向量元素是实数，无穷用 math.inf 表示。
    """
    steps = _norm_steps(steps, "step_transitions 步数")
    order, index, triples = _collect(nodes, edges)
    size = len(order)
    if size == 0:
        return [], order
    base = _base_matrix(triples, index, size)
    vec = _norm_vector(init, "step_transitions 初值")
    if len(vec) != size:
        raise MatrixErro("step_transitions：初值长度 %d 与节点数 %d 不符"
                         % (len(vec), size))
    cur = vec
    for _ in range(steps):
        nxt = [INF] * size
        for j in range(size):
            best = INF
            for i in range(size):
                cand = cur[i] + base[i][j]
                if cand < best:
                    best = cand
            nxt[j] = best
        cur = nxt
    return cur, order


# ---------------------------------------------------------------------------
# 工具集（带计数）
# ---------------------------------------------------------------------------

class MatPlusKit:
    """最小加工具集朴素实现（改造前基线）。

    每次调用前把对应的计数归零后再重新累加，计数只反映这一次调用，不把上一次的
    数值带进来：

      iter_steps  上一次 shortest_paths 实际做的整表松弛遍数
      trans_steps 上一次 step_transitions 实际做的向量推进步数
      mult_count  上一次 matrix_power 实际做的最小加矩阵乘法次数
    """

    def __init__(self):
        self.iter_steps = 0
        self.trans_steps = 0
        self.mult_count = 0

    def shortest_paths(self, nodes, edges, steps):
        self.iter_steps = 0
        steps = _norm_steps(steps, "shortest_paths 步数")
        order, index, triples = _collect(nodes, edges)
        size = len(order)
        if size == 0:
            return [], order
        base = _base_matrix(triples, index, size)
        cur = _identity(size)
        for _ in range(steps):
            nxt = [[INF] * size for _ in range(size)]
            for i in range(size):
                curi = cur[i]
                for j in range(size):
                    best = INF
                    for t in range(size):
                        cand = curi[t] + base[t][j]
                        if cand < best:
                            best = cand
                    nxt[i][j] = best
            cur = nxt
            self.iter_steps += 1
        return cur, order

    def step_transitions(self, init, nodes, edges, steps):
        self.trans_steps = 0
        steps = _norm_steps(steps, "step_transitions 步数")
        order, index, triples = _collect(nodes, edges)
        size = len(order)
        if size == 0:
            return [], order
        base = _base_matrix(triples, index, size)
        vec = _norm_vector(init, "step_transitions 初值")
        if len(vec) != size:
            raise MatrixErro("step_transitions：初值长度 %d 与节点数 %d 不符"
                             % (len(vec), size))
        cur = vec
        for _ in range(steps):
            nxt = [INF] * size
            for j in range(size):
                best = INF
                for i in range(size):
                    cand = cur[i] + base[i][j]
                    if cand < best:
                        best = cand
                nxt[j] = best
            cur = nxt
            self.trans_steps += 1
        return cur, order

    def matrix_power(self, a, exponent):
        self.mult_count = 0
        a = _norm_matrix(a, "matrix_power 底矩阵")
        exponent = _norm_steps(exponent, "matrix_power 幂次")
        size = _check_square(a, "matrix_power")
        if size == 0:
            return []
        out = _identity(size)
        for _ in range(exponent):
            out = _mat_mul(out, a)
            self.mult_count += 1
        return out
