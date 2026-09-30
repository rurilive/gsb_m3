"""matpow.recur：线性递推的朴素实现（改造前基线）。

围绕常系数线性递推做三件最基础的事：

  - nth_term        第n项：按递推式从初值一项一项往上推，每一步整数加乘之后
                    立刻对模取余，推到第n项为止；
  - prefix_sum      前n项和：把逐项推出来的每一项累加起来，再对模取余；
  - nth_term_nonhom 非齐次第n项：递推式后面挂一个附加常数项，同样逐项推。

另外还给矩阵的乘法与幂各留了一条朴素路径 mat_mul 与 mat_pow：乘法用三重循环
一项一项地累加，幂用逐次相乘的循环把同一矩阵连乘若干遍。这些做法直观可靠，
结果一眼能看穿，可项数一旦变大就是线性乃至立方量级地退下去。

本文件是改造前的基线，朴素路径在改造之后不得删除，新的快速路径必须与它对
同一批输入给出的结果逐项对齐。

异常统一继承 RecurErro 基类：TermErro / MatrixErro。
"""


class RecurErro(Exception):
    """递推工具包所有异常的基类，非法输入与非法操作一律快速失败。"""


class TermErro(RecurErro):
    """项数或系数非法：项数为负、递推阶数与初值个数不符、模不是正数。"""


class MatrixErro(RecurErro):
    """矩阵非法：形状参差不齐、行列不匹配、指数为负。"""


def _as_int(value, where):
    """把入参规整成 Python 整数。布尔不算整数，非法即抛 TermErro。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TermErro("%s：必须是整数，收到 %r" % (where, value))
    return value


def _norm_coeffs(coeffs, where):
    """系数序列规整成整数元组，非法即抛 TermErro。"""
    try:
        items = list(coeffs)
    except TypeError:
        raise TermErro("%s：系数必须是可迭代的整数序列，收到 %r" % (where, coeffs))
    if not items:
        raise TermErro("%s：系数不能为空" % where)
    return tuple(_as_int(c, where) for c in items)


def _norm_init(init, where, k):
    """初值序列规整成整数元组，并要求长度与递推阶数一致。"""
    try:
        items = list(init)
    except TypeError:
        raise TermErro("%s：初值必须是可迭代的整数序列，收到 %r" % (where, init))
    if len(items) != k:
        raise TermErro("%s：初值个数必须等于递推阶数，期望 %d 个，收到 %d 个"
                       % (where, k, len(items)))
    return tuple(_as_int(v, where) for v in items)


def _pow_mod_int(base, exp, mod):
    """整数的快速幂，逐位平方法，每一步乘法之后立刻取模。"""
    result = 1 % mod
    b = base % mod
    e = exp
    while e > 0:
        if e & 1:
            result = (result * b) % mod
        b = (b * b) % mod
        e >>= 1
    return result


def mat_mul(a, b, mod):
    """朴素矩阵乘法：三重循环，内层逐项累加与外层逐项取模。

    形状不匹配（a 的列数不等于 b 的行数）抛 MatrixErro。mod 不是正数抛
    MatrixErro。空矩阵（零行或零列）按平凡结果处理。
    """
    mod = _as_int(mod, "矩阵乘法取模")
    if mod <= 0:
        raise MatrixErro("矩阵乘法：模必须是正整数，收到 %r" % (mod,))
    ra = len(a)
    if ra:
        ca = len(a[0])
        for i in range(1, ra):
            if len(a[i]) != ca:
                raise MatrixErro("矩阵乘法：左侧矩阵第 %d 行长度与首行不一致" % (i + 1))
    else:
        ca = 0
    rb = len(b)
    if rb:
        cb = len(b[0])
        for j in range(1, rb):
            if len(b[j]) != cb:
                raise MatrixErro("矩阵乘法：右侧矩阵第 %d 行长度与首行不一致" % (j + 1))
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

    e 为负数抛 MatrixErro；e 为零返回同阶单位矩阵；方阵形状非法抛
    MatrixErro。指数很大时，这里要做指数那么多次矩阵乘法。
    """
    e = _as_int(e, "矩阵幂指数")
    if e < 0:
        raise MatrixErro("矩阵幂：指数不能为负，收到 %r" % (e,))
    n = len(a)
    if n == 0:
        return []
    for i in range(n):
        if len(a[i]) != n:
            raise MatrixErro("矩阵幂：只支持方阵，第 %d 行长度不是 %d" % (i + 1, n))
    eye = [[1 if i == j else 0 for j in range(n)] for i in range(n)]
    out = eye
    for _ in range(e):
        out = mat_mul(out, a, mod)
    return out


class RecurKit:
    """常系数线性递推朴素工具集（改造前基线）。"""

    def __init__(self):
        # 各条路径实际发生的迭代步数与矩阵乘法次数，进入一次调用前归零后重新累加。
        self.iter_steps = 0
        self.mult_count = 0

    # ----------------------------------------------------------------
    # 内部工具
    # ----------------------------------------------------------------
    def _mat_mul(self, a, b, mod):
        self.mult_count += 1
        return mat_mul(a, b, mod)

    # ----------------------------------------------------------------
    # 第n项：按递推式从初值逐项往上推
    # ----------------------------------------------------------------
    def nth_term(self, init, coeffs, n, mod):
        """返回第n项，从初值按递推式逐项迭代到 n，每项之后对模取余。

        第零项是 init[0]，第一项是 init[1]，依此类推，前阶数个项就是 init
        本身。n 为负抛 TermErro；初值个数与递推阶数不符抛 TermErro；模不是
        正数抛 TermErro。
        """
        self.iter_steps = 0
        n = _as_int(n, "第n项项数")
        mod = _as_int(mod, "第n项取模")
        if mod <= 0:
            raise TermErro("第n项：模必须是正整数，收到 %r" % (mod,))
        if n < 0:
            raise TermErro("第n项：项数不能为负，收到 %r" % (n,))
        c = _norm_coeffs(coeffs, "第n项递推系数")
        k = len(c)
        vals = list(_norm_init(init, "第n项初值", k))
        if n < k:
            return vals[n] % mod
        pos = k
        cur = vals
        while pos <= n:
            acc = 0
            for j in range(k):
                acc += c[j] * cur[pos - 1 - j]
            nxt = acc % mod
            cur.append(nxt)
            self.iter_steps += 1
            pos += 1
        return cur[n]

    # ----------------------------------------------------------------
    # 前n项和：把逐项推出来的每一项累加起来
    # ----------------------------------------------------------------
    def prefix_sum(self, init, coeffs, n, mod):
        """返回前n项之和，n 计数从零开始，即第零项到第n-1项的和，最后对模取余。

        逐项推出来的每一项都先对模取余，再累加、再对模取余，最终落在零到
        模减一之间。n 为零时和为零；n 为负抛 TermErro。
        """
        n = _as_int(n, "前n项和项数")
        mod = _as_int(mod, "前n项和取模")
        if mod <= 0:
            raise TermErro("前n项和：模必须是正整数，收到 %r" % (mod,))
        if n < 0:
            raise TermErro("前n项和：项数不能为负，收到 %r" % (n,))
        c = _norm_coeffs(coeffs, "前n项和递推系数")
        k = len(c)
        vals = list(_norm_init(init, "前n项和初值", k))
        if n == 0:
            return 0
        total = 0
        seen = min(n, k)
        for i in range(seen):
            total = (total + vals[i]) % mod
        if n <= k:
            return total
        cur = vals
        pos = k
        while pos < n:
            acc = 0
            for j in range(k):
                acc += c[j] * cur[pos - 1 - j]
            nxt = acc % mod
            cur.append(nxt)
            total = (total + nxt) % mod
            pos += 1
        return total

    # ----------------------------------------------------------------
    # 非齐次第n项：递推式后面挂一个附加常数项
    # ----------------------------------------------------------------
    def nth_term_nonhom(self, init, coeffs, const, n, mod):
        """返回带附加常数项的非齐次递推的第n项。

        递推式是第n项等于各系数乘以更早的对应项之和，再加上一个固定的附加
        常数，每项之后对模取余。const 为零时与齐次口径一致。n 为负抛
        TermErro；初值个数与递推阶数不符抛 TermErro；模不是正数抛 TermErro。
        """
        self.iter_steps = 0
        n = _as_int(n, "非齐次第n项项数")
        const = _as_int(const, "非齐次附加常数")
        mod = _as_int(mod, "非齐次第n项取模")
        if mod <= 0:
            raise TermErro("非齐次第n项：模必须是正整数，收到 %r" % (mod,))
        if n < 0:
            raise TermErro("非齐次第n项：项数不能为负，收到 %r" % (n,))
        c = _norm_coeffs(coeffs, "非齐次第n项递推系数")
        k = len(c)
        vals = list(_norm_init(init, "非齐次第n项初值", k))
        if n < k:
            return vals[n] % mod
        cur = vals
        pos = k
        while pos <= n:
            acc = const
            for j in range(k):
                acc += c[j] * cur[pos - 1 - j]
            nxt = acc % mod
            cur.append(nxt)
            self.iter_steps += 1
            pos += 1
        return cur[n]

    # ----------------------------------------------------------------
    # 快速幂口径（改造后补）：这里只留朴素对照，不算真正的快速幂
    # ----------------------------------------------------------------
    def binary_pow_int(self, base, exp, mod):
        """整数的逐位平方法幂，朴素实现里它只服务于矩阵幂的对照。"""
        base = _as_int(base, "整数幂底数")
        exp = _as_int(exp, "整数幂指数")
        mod = _as_int(mod, "整数幂取模")
        if mod <= 0:
            raise TermErro("整数幂：模必须是正整数，收到 %r" % (mod,))
        if exp < 0:
            raise TermErro("整数幂：指数不能为负，收到 %r" % (exp,))
        return _pow_mod_int(base, exp, mod)
