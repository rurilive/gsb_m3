"""detmod.matrix：模意义下矩阵运算的朴素实现（改造前基线）。

围绕模运算矩阵做几件最基础的事，全部按定义直白实现，规模一大就慢但结果正确：

  - det_definitional        行列式：按定义递归展开第一行，累计带符号余子式；
  - perm_det                行列式：枚举全排列，按排列的逆序奇偶取符号累加；
  - mat_mul                 矩阵乘法：三重循环逐项累加；
  - inverse_adjugate        矩阵求逆：伴随矩阵除以行列式，靠逐个余子式拼伴随阵；
  - solve_cramer            解线性方程组：逐项克拉默法则，每个分量一个行列式；
  - det_terms / elim_ops    规模计数：全排列展开项数与高斯消元操作次数。

模数不一定是素数：求逆元时先试扩展欧几里得，遇到无逆元的情形如实报出不可逆，
绝不返回一个看似正确的假值。所有异常统一继承 DetErro 基类：
MatrixErro / DetErro 派生类见下。

文件末尾还给模意义下的秩与行向量线性相关判定一条朴素路径：秩按最大非零子式的
阶数枚举行子集与列子集，做法直观但子集数量随阶数指数增长。

本文件是改造前的基线，朴素路径在改造之后不得删除，新的快速路径必须与它对同一
批输入给出的结果逐项对齐。
"""

from itertools import combinations


class DetErro(Exception):
    """模矩阵工具包所有异常的基类，非法输入与非法操作一律快速失败。"""


class MatrixErro(DetErro):
    """矩阵形状非法：参差不齐、非方阵、行列不匹配、空矩阵。"""


class ModErro(DetErro):
    """模数非法：不是正整数。"""


class InverseErro(DetErro):
    """矩阵不可逆：模数与消元主元没有逆元。"""


def _as_int(value, where):
    """把入参规整成 Python 整数。布尔不算整数，非法即抛 ModErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ModErro("%s：必须是整数，收到 %r" % (where, value))
    return value


def _norm_mod(mod):
    """模数校验：必须是正整数，否则抛 ModErro。"""
    mod = _as_int(mod, "取模")
    if mod <= 0:
        raise ModErro("取模：模数必须是正整数，收到 %r" % (mod,))
    return mod


def _check_mod(mod):
    """模数校验的别名，供各公开入口调用。"""
    return _norm_mod(mod)


def _norm_square(a, where):
    """把矩阵规整成整数方阵，形状非法即抛 MatrixErro。"""
    if not isinstance(a, (list, tuple)):
        raise MatrixErro("%s：矩阵必须是列表或元组，收到 %r" % (where, a))
    rows = list(a)
    n = len(rows)
    for i in range(n):
        if not isinstance(rows[i], (list, tuple)):
            raise MatrixErro("%s：第 %d 行不是序列" % (where, i + 1))
        if len(rows[i]) != n:
            raise MatrixErro("%s：只支持方阵，第 %d 行长度不是 %d"
                             % (where, i + 1, n))
        for v in rows[i]:
            _as_int(v, "%s元素" % where)
    return [list(r) for r in rows]


def _minor(a, i, j):
    """去掉第i行第j列之后的余子式矩阵。"""
    return [row[:j] + row[j + 1:] for k, row in enumerate(a) if k != i]


# --------------------------------------------------------------------
# 求逆元：先试扩展欧几里得，无逆元如实报出
# --------------------------------------------------------------------
def egcd(a, b):
    """扩展欧几里得：返回 (g, x, y) 使 a*x + b*y == g == gcd(a, b)。"""
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r != 0:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    return old_r, old_s, old_t


def mod_inverse(value, mod):
    """求 value 在模 mod 下的逆元。

    先试扩展欧几里得，当且仅当 gcd(value, mod) 为一逆元存在。无逆元时抛
    InverseErro，绝不返回假值。mod 不是正整数抛 ModErro。
    """
    mod = _norm_mod(mod)
    v = _as_int(value, "逆元底数") % mod
    g, x, _ = egcd(v, mod)
    if g != 1:
        raise InverseErro("逆元不存在：%d 与模 %d 的公约数是 %d"
                          % (v, mod, g))
    return x % mod


def egcd_steps(a, b):
    """单独统计扩展欧几里得辗转相除的轮数，供规模对照使用。"""
    old_r, r = a, b
    steps = 0
    while r != 0:
        old_r, r = r, old_r % r
        steps += 1
    return steps


def _inv(value, mod):
    """内部求逆元，失败抛 InverseErro。"""
    return mod_inverse(value, mod)


# --------------------------------------------------------------------
# 矩阵乘法：三重循环
# --------------------------------------------------------------------
def mat_mul(a, b, mod):
    """朴素矩阵乘法：三重循环内层逐项累加，最后对模取余。

    形状不匹配（a 的列数不等于 b 的行数）抛 MatrixErro；mod 不是正整数抛
    ModErro。空矩阵按平凡结果处理。
    """
    mod = _norm_mod(mod)
    ra = len(a)
    if ra:
        ca = len(a[0])
        for i in range(1, ra):
            if len(a[i]) != ca:
                raise MatrixErro("矩阵乘法：左侧第 %d 行长度与首行不一致" % (i + 1))
    else:
        ca = 0
    rb = len(b)
    if rb:
        cb = len(b[0])
        for j in range(1, rb):
            if len(b[j]) != cb:
                raise MatrixErro("矩阵乘法：右侧第 %d 行长度与首行不一致" % (j + 1))
    else:
        cb = 0
    if ca != rb:
        raise MatrixErro("矩阵乘法：左矩阵列数 %d 与右矩阵行数 %d 不匹配"
                         % (ca, rb))
    if ra == 0 or cb == 0:
        return []
    out = [[0] * cb for _ in range(ra)]
    for i in range(ra):
        for j in range(cb):
            acc = 0
            for t in range(ca):
                acc += a[i][t] * b[t][j]
            out[i][j] = acc % mod
    return out


def mat_pow(a, e, mod):
    """朴素矩阵幂：把同一个矩阵连乘 e 遍。

    e 为负抛 MatrixErro；e 为零返回同阶单位矩阵；非方阵抛 MatrixErro。
    """
    e = _as_int(e, "矩阵幂指数")
    if e < 0:
        raise MatrixErro("矩阵幂：指数不能为负，收到 %r" % (e,))
    mod = _norm_mod(mod)
    n = len(a)
    if n == 0:
        return []
    for i in range(n):
        if len(a[i]) != n:
            raise MatrixErro("矩阵幂：只支持方阵，第 %d 行长度不是 %d" % (i + 1, n))
    eye = _identity(n)
    out = eye
    for _ in range(e):
        out = mat_mul(out, a, mod)
    return out


def _identity(n):
    """n 阶单位矩阵。"""
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


# --------------------------------------------------------------------
# 行列式：按定义递归展开
# --------------------------------------------------------------------
def det_definitional(a, mod):
    """行列式：按定义对第一行展开，累计带符号余子式，阶乘量级。

    n 为零返回一（空矩阵行列式约定为一）。非方阵抛 MatrixErro，mod 非法抛
    ModErro。
    """
    mod = _norm_mod(mod)
    m = _norm_square(a, "行列式")
    n = len(m)
    return _det_rec(m, mod)


def _det_rec(a, mod):
    """递归展开的内部实现。"""
    n = len(a)
    if n == 0:
        return 1 % mod
    if n == 1:
        return a[0][0] % mod
    if n == 2:
        return (a[0][0] * a[1][1] - a[0][1] * a[1][0]) % mod
    total = 0
    sign = 1
    for j in range(n):
        sub = _minor(a, 0, j)
        total += sign * a[0][j] * _det_rec(sub, mod)
        sign = -sign
    return total % mod


def _permutations(n):
    """枚举零到n减一的全部排列，按字典序逐个产出（朴素升序）。"""
    items = list(range(n))
    if n == 0:
        yield []
        return
    out = []

    def rec(chosen, rest):
        if not rest:
            out.append(tuple(chosen))
            return
        for k in range(len(rest)):
            rec(chosen + [rest[k]], rest[:k] + rest[k + 1:])

    rec([], items)
    for p in out:
        yield p


def _perm_sign(p):
    """排列的符号：逆序数为偶返回一，为奇返回负一。"""
    inv = 0
    n = len(p)
    for i in range(n):
        for j in range(i + 1, n):
            if p[i] > p[j]:
                inv += 1
    return -1 if inv % 2 else 1


def perm_det(a, mod):
    """行列式：枚举全排列，按排列逆序数的奇偶取符号累加，阶乘量级。"""
    mod = _norm_mod(mod)
    m = _norm_square(a, "全排列行列式")
    n = len(m)
    total = 0
    for p in _permutations(n):
        term = _perm_sign(p)
        for i in range(n):
            term *= m[i][p[i]]
        total += term
    return total % mod


def det_terms(n):
    """全排列展开的项数，等于 n 的阶乘。"""
    _as_int(n, "阶数")
    if n < 0:
        raise MatrixErro("阶数不能为负，收到 %r" % (n,))
    out = 1
    for i in range(2, n + 1):
        out *= i
    return out


# --------------------------------------------------------------------
# 矩阵求逆：伴随矩阵除以行列式
# --------------------------------------------------------------------
def _cofactor(m, i, j, mod):
    """代数余子式：去掉第i行第j列的余子式行列式再乘符号。"""
    sub = _minor(m, i, j)
    sign = -1 if (i + j) % 2 else 1
    return sign * _det_rec(sub, mod)


def inverse_adjugate(a, mod):
    """矩阵求逆：先算行列式，再逐个代数余子式拼伴随阵，最后乘行列式的逆元。

    奇异矩阵（行列式与模数无逆元）抛 InverseErro；非方阵抛 MatrixErro。
    """
    mod = _norm_mod(mod)
    m = _norm_square(a, "求逆")
    n = len(m)
    if n == 0:
        return []
    d = _det_rec(m, mod) % mod
    if d == 0:
        raise InverseErro("矩阵不可逆：行列式在模 %d 下为零" % (mod,))
    d_inv = mod_inverse(d, mod)
    adj = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            adj[j][i] = _cofactor(m, i, j, mod) % mod
    out = [[(adj[i][j] * d_inv) % mod for j in range(n)] for i in range(n)]
    return out


# --------------------------------------------------------------------
# 解线性方程组：克拉默法则
# --------------------------------------------------------------------
def _replace_col(m, j, col):
    """把矩阵第j列替换成列向量 col。"""
    out = [list(r) for r in m]
    for i in range(len(out)):
        out[i][j] = col[i]
    return out


def solve_cramer(coeff, rhs, mod):
    """克拉默法则解方程组：每个未知量各算一次行列式。

    系数矩阵奇异时抛 InverseErro（无唯一解）；形状不匹配抛 MatrixErro。
    """
    mod = _norm_mod(mod)
    m = _norm_square(coeff, "方程组系数")
    n = len(m)
    if len(rhs) != n:
        raise MatrixErro("方程组：常数项个数 %d 与阶数 %d 不符" % (len(rhs), n))
    rhs = [_as_int(v, "常数项") for v in rhs]
    d = _det_rec(m, mod) % mod
    if d == 0:
        raise InverseErro("方程组无唯一解：系数行列式在模 %d 下为零" % (mod,))
    d_inv = mod_inverse(d, mod)
    sol = []
    for j in range(n):
        mj = _replace_col(m, j, rhs)
        sol.append((_det_rec(mj, mod) * d_inv) % mod)
    return sol


# --------------------------------------------------------------------
# 规模计数：全排列项数与高斯消元操作次数
# --------------------------------------------------------------------
def perm_count(n):
    """全排列展开路线的项数对照，等于 n 的阶乘。"""
    return det_terms(n)


def elimination_ops(n):
    """高斯消元消元阶段的操作次数对照：每列对下方各行做一次行消元。

    返回值与阶数 n 的三次方同阶，用于与全排列项数摆在一起对照两路的量级差距。
    """
    _as_int(n, "阶数")
    if n < 0:
        raise MatrixErro("阶数不能为负，收到 %r" % (n,))
    ops = 0
    for col in range(n):
        for row in range(col + 1, n):
            ops += 1
    return ops


# --------------------------------------------------------------------
# 秩与行向量线性相关：按最大非零子式的阶数
# --------------------------------------------------------------------
def _norm_rect(a, where):
    """把矩阵规整成整数矩阵，允许非方阵，但各行长度必须一致。"""
    if not isinstance(a, (list, tuple)):
        raise MatrixErro("%s：矩阵必须是列表或元组，收到 %r" % (where, a))
    rows = list(a)
    n = len(rows)
    if n == 0:
        return []
    if not isinstance(rows[0], (list, tuple)):
        raise MatrixErro("%s：第 1 行不是序列" % where)
    width = len(rows[0])
    for i in range(n):
        if not isinstance(rows[i], (list, tuple)):
            raise MatrixErro("%s：第 %d 行不是序列" % (where, i + 1))
        if len(rows[i]) != width:
            raise MatrixErro("%s：第 %d 行长度与首行不一致" % (where, i + 1))
        for v in rows[i]:
            _as_int(v, "%s元素" % where)
    return [list(r) for r in rows]


def _has_nonzero_minor(m, k, mod):
    """是否存在 k 阶非零子式：枚举 k 行组合与 k 列组合逐一求行列式。"""
    rows = range(len(m))
    cols = range(len(m[0]))
    for rs in combinations(rows, k):
        for cs in combinations(cols, k):
            sub = [[m[i][j] for j in cs] for i in rs]
            if _det_rec(sub, mod) % mod != 0:
                return True
    return False


def mat_rank(a, mod):
    """模意义下的矩阵的秩：最大的非零子式阶数。

    零矩阵的秩为零，单位阵的秩等于阶数。允许非方阵，秩不超过行数与列数的较小
    者。mod 不是正整数抛 ModErro，矩阵形状非法抛 MatrixErro。
    """
    mod = _norm_mod(mod)
    m = _norm_rect(a, "求秩")
    if not m:
        return 0
    upper = min(len(m), len(m[0]))
    for k in range(upper, 0, -1):
        if _has_nonzero_minor(m, k, mod):
            return k
    return 0


def row_rank(vectors, mod):
    """一组行向量的秩，等于把它们摞成矩阵后的秩。"""
    return mat_rank(vectors, mod)


def rows_dependent(vectors, mod):
    """判断一组行向量在模下是否线性相关。

    当且仅当它们的秩小于向量个数时为相关；一个向量也没有时不算相关。
    """
    mod = _norm_mod(mod)
    m = _norm_rect(vectors, "线性相关判定")
    if not m:
        return False
    return mat_rank(m, mod) < len(m)


class MatrixKit:
    """模矩阵朴素工具集（改造前基线）。

    各条路径实际发生的计数进入一次调用前归零后重新累加，不依赖模块级可变状态。
    """

    def __init__(self):
        self.last_perm_terms = 0
        self.last_elim_ops = 0

    def determinant(self, a, mod):
        """行列式：递归展开，记录全排列等价的展开项数。"""
        mod = _norm_mod(mod)
        m = _norm_square(a, "行列式")
        self.last_perm_terms = det_terms(len(m))
        return _det_rec(m, mod)

    def det_by_perm(self, a, mod):
        """行列式：全排列枚举，与递归展开逐项一致。"""
        return perm_det(a, mod)

    def is_invertible(self, a, mod):
        """是否可逆：行列式在模下与模数互素即为可逆。"""
        mod = _norm_mod(mod)
        m = _norm_square(a, "可逆判定")
        if len(m) == 0:
            return False
        d = _det_rec(m, mod) % mod
        g, _, _ = egcd(d, mod)
        return g == 1

    def inverse(self, a, mod):
        """求逆矩阵，不可逆抛 InverseErro。"""
        return inverse_adjugate(a, mod)

    def multiply(self, a, b, mod):
        """矩阵乘法。"""
        return mat_mul(a, b, mod)

    def power(self, a, e, mod):
        """矩阵幂，逐次相乘。"""
        return mat_pow(a, e, mod)

    def solve(self, coeff, rhs, mod):
        """解线性方程组（唯一解口径）。"""
        return solve_cramer(coeff, rhs, mod)
