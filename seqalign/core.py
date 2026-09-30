"""序列比对与编辑距离的朴素实现。

当前每条能力都走同一条笨路：求最长公共子序列时枚举两个串的全部子序列组合，
逐个检查是不是公共子序列再取最长；求编辑距离时对每一步枚举删除、插入、替换
三种操作各递归一次，同一对前缀会被反复重算；求最小编辑方案时对同一段前缀
重新展开一遍又一遍。这些路径结果都对，口径也固定，但长度一上去，枚举的状态数
就指数甚至更高量级地膨胀。全部实现只用标准库，且不依赖任何模块级可变状态。
"""


class SeqAlignError(Exception):
    """本模块所有错误的基类，上层只认这一个根。"""


class EmptyInputError(SeqAlignError):
    """要求非空串的入口收到空串时抛出。"""


class TypeMismatchError(SeqAlignError):
    """入口收到的参数不是字符串时抛出。"""


def _iter_subsequences(seq):
    """按固定顺序枚举 seq 的全部子序列。

    用位掩码从零数到二的 n 次方减一，第 i 位为一表示取第 i 个字符。
    同一串每次枚举的顺序完全一致，结果只由输入决定。
    """
    n = len(seq)
    for mask in range(1 << n):
        picked = []
        for i in range(n):
            if mask & (1 << i):
                picked.append(seq[i])
        yield "".join(picked)


class SeqAlign:
    """序列比对的朴素求解器，全部能力都靠枚举。

    每个方法都是只读的，不在实例或模块上缓存任何中间结果，同一个实例
    重复调用给出完全一致的答案。
    """

    def lcs_length(self, a, b):
        """最长公共子序列的长度，逐个枚举全部子序列组合取最长。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        best = 0
        for sub in _iter_subsequences(a):
            if best >= len(sub):
                continue
            for other in _iter_subsequences(b):
                if len(other) < len(sub):
                    continue
                if sub == other and len(sub) > best:
                    best = len(sub)
                    break
        return best

    def lcs_string(self, a, b):
        """一条具体的最长公共子序列。

        先枚举出最长长度，再按前序取枚举顺序里第一条达到该长度的公共子序列，
        作为并列时的固定口径，结果确定。
        """
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        best_len = self.lcs_length(a, b)
        if best_len == 0:
            return ""
        for i, sub in enumerate(_iter_subsequences(a)):
            if len(sub) != best_len:
                continue
            seen = False
            for other in _iter_subsequences(b):
                if other == sub and len(other) == best_len:
                    seen = True
                    break
            if seen:
                return sub
        return ""

    def edit_distance(self, a, b):
        """把 a 改成 b 的最少插入、删除、替换次数，逐步枚举三种操作递归。"""
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

    def indel_distance(self, a, b):
        """只允许插入和删除时的最少步数，等于两串长度之和减两倍最长公共子序列长度。"""
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeMismatchError("参数必须是字符串")
        return len(a) + len(b) - 2 * self.lcs_length(a, b)

    def lcs_substring(self, a, b):
        """最长公共子串的长度，枚举 a 的全部子串去 b 里逐个查找比对。"""
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
