"""编辑距离与序列对齐的朴素实现。

当前每条能力都走最直白的笨路：求都把第一个串改成第二个串的最少单字符
增删改次数时，对每一步把删除、插入、替换三种操作各递归展开一次，同一对
前缀会被反复重算，分支大面积重叠；求最长公共子序列时枚举第一个串的全部
子序列再去第二个串里逐个查找；求最长公共子串时枚举第一个串的全部子串。
这些路径结果都对，口径也固定，但长度一上去，枚举的状态数就指数甚至更高
量级地膨胀。全部实现只用标准库，不依赖任何模块级可变状态。
"""


class EditPathError(Exception):
    """本模块所有错误的基类，上层只认这一个根。"""


class TypeMismatchError(EditPathError):
    """入口收到的参数不是字符串时抛出。"""


def _iter_subsequences(seq):
    """按固定顺序枚举 seq 的全部子序列。

    用位掩码从零数到二的 n 次方减一，第 i 位为一表示取第 i 个字符，
    同一串每次枚举顺序完全一致，结果只由输入决定。
    """
    n = len(seq)
    for mask in range(1 << n):
        picked = []
        for i in range(n):
            if mask & (1 << i):
                picked.append(seq[i])
        yield "".join(picked)


class EditPath:
    """编辑距离与序列对齐的朴素求解器，全部能力都靠枚举。

    每个方法都是只读的，不在实例或模块上缓存任何中间结果，同一个实例
    重复调用给出完全一致的答案。
    """

    def edit_distance(self, a, b):
        """把 a 改成 b 的最少增删改次数，逐步枚举三种操作各递归一次。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        return self._edit_rec(a, b, len(a), len(b))

    def _edit_rec(self, a, b, i, j):
        """对前缀 a 的前 i 个与 b 的前 j 个，枚举三种操作各递归一次。"""
        if i == 0:
            return j
        if j == 0:
            return i
        if a[i - 1] == b[j - 1]:
            return self._edit_rec(a, b, i - 1, j - 1)
        replace = self._edit_rec(a, b, i - 1, j - 1) + 1
        delete = self._edit_rec(a, b, i - 1, j) + 1
        insert = self._edit_rec(a, b, i, j - 1) + 1
        return min(replace, delete, insert)

    def weighted_distance(self, a, b, replace_cost, delete_cost, insert_cost):
        """三种操作各配置权重后的最少代价，仍靠逐步枚举递归展开。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        for cost in (replace_cost, delete_cost, insert_cost):
            if not isinstance(cost, int) or isinstance(cost, bool) or cost < 0:
                raise TypeMismatchError("权重必须是非负整数")
        return self._weighted_rec(a, b, len(a), len(b),
                                  replace_cost, delete_cost, insert_cost)

    def _weighted_rec(self, a, b, i, j, rc, dc, ic):
        """对前缀逐位展开三种操作，各自带上权重取最小代价。"""
        if i == 0:
            return j * ic
        if j == 0:
            return i * dc
        if a[i - 1] == b[j - 1]:
            return self._weighted_rec(a, b, i - 1, j - 1, rc, dc, ic)
        replace = self._weighted_rec(a, b, i - 1, j - 1, rc, dc, ic) + rc
        delete = self._weighted_rec(a, b, i - 1, j, rc, dc, ic) + dc
        insert = self._weighted_rec(a, b, i, j - 1, rc, dc, ic) + ic
        return min(replace, delete, insert)

    def indel_distance(self, a, b):
        """只允许插入删除时的最少步数，等于两串长度之和减两倍最长公共子序列长度。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        return len(a) + len(b) - 2 * self.lcs_length(a, b)

    def lcs_length(self, a, b):
        """最长公共子序列的长度，枚举第一个串的全部子序列再逐个查找。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        best = 0
        for sub in _iter_subsequences(a):
            if len(sub) > best and sub in b:
                best = len(sub)
        return best

    def lcs_substring(self, a, b):
        """最长公共子串的长度，枚举第一个串的全部子串去第二个串里查找。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        best = 0
        for i in range(len(a)):
            for j in range(i + 1, len(a) + 1):
                piece = a[i:j]
                if len(piece) > best and piece in b:
                    best = len(piece)
        return best

    def lcs_prefix(self, a, b):
        """最长公共前缀的长度，从首字符逐个往下比。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        n = min(len(a), len(b))
        k = 0
        while k < n and a[k] == b[k]:
            k += 1
        return k
