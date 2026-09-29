"""差异计算：只做等长字符串的逐位比较。

当前能力非常有限：先把两个串对齐到相同长度（长度不等直接报错），
再逐个下标比较字符是否相同，统计不同的字符个数。没有插入、没有删除、
没有编辑距离，也没有任何对齐或回溯信息。
"""


class EditError(Exception):
    """editlab 的统一异常基类，后续所有自定义异常都从这里派生。"""


class LengthMismatchError(EditError):
    """两个字符串长度不等时抛出。"""


class HammDiff:
    """逐位比较的差异字符计数器。"""

    def diff_count(self, a, b):
        """返回 a 与 b 逐位不同的字符个数。

        要求两串长度相等；长度不等抛 LengthMismatchError。
        """
        if not isinstance(a, str) or not isinstance(b, str):
            raise TypeError("diff_count expects str arguments")
        if len(a) != len(b):
            raise LengthMismatchError(
                "length mismatch: %d != %d" % (len(a), len(b))
            )
        count = 0
        for x, y in zip(a, b):
            if x != y:
                count += 1
        return count

    def common_positions(self, a, b):
        """返回两串中字符相同的下标列表，要求等长。"""
        if len(a) != len(b):
            raise LengthMismatchError(
                "length mismatch: %d != %d" % (len(a), len(b))
            )
        return [i for i, (x, y) in enumerate(zip(a, b)) if x == y]
