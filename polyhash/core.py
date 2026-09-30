"""polyhash 的核心实现：多项式哈希字符串池（改造前基线）。

当前只提供一份最直白的 StringPool：判等、最长公共前缀、批量查重三件事
全部靠逐字符比较完成，结果正确，但代价随串长与查询次数线性增长。
这里既没有滚动哈希，也没有前缀哈希与取模幂，更没有多重基数防碰撞的意识。
"""


class PolyHashError(Exception):
    """字符串池的统一错误基类，所有对外报错都从这里派生。"""


def build_text(seed, length):
    """用固定线性同余序列拼出一段确定性的小写字符串。

    同一个 seed 与 length 每次调用都得到完全相同的文本，供演示与测试
    构造可复现的输入。length 为负时直接报错。
    """
    if length < 0:
        raise PolyHashError("长度不能为负")
    state = (int(seed) * 2654435761 + 1013904223) & 0xFFFFFFFF
    chars = []
    for _ in range(length):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        chars.append(chr(ord("a") + state % 26))
    return "".join(chars)


class StringPool:
    """持有一批字符串并支持判等、最长公共前缀与查重的朴素串池。

    所有比较都逐字符进行，每一次字符位置的比较都会计入访问计数，
    用来暴露当前实现对串长与查询次数的依赖。
    """

    def __init__(self):
        self._items = []
        self._access = 0

    def add(self, text):
        """登记一段字符串，返回它的下标，下标即插入顺序。"""
        if not isinstance(text, str):
            raise PolyHashError("只能登记字符串")
        self._items.append(text)
        return len(self._items) - 1

    def size(self):
        """当前串池里字符串的个数。"""
        return len(self._items)

    def get(self, index):
        """按下标取回字符串副本。"""
        return self._lookup(index)

    def _lookup(self, index):
        if not isinstance(index, int) or index < 0 or index >= len(self._items):
            raise PolyHashError("下标越界")
        return self._items[index]

    @property
    def access_count(self):
        """累计发生过的字符位置比较次数。"""
        return self._access

    def reset_access_count(self):
        """把访问计数归零。"""
        self._access = 0

    def equal(self, left, right):
        """逐字符判断两串是否相等，返回布尔。"""
        a = self._lookup(left)
        b = self._lookup(right)
        limit = min(len(a), len(b))
        pos = 0
        while pos < limit:
            self._access += 1
            if a[pos] != b[pos]:
                return False
            pos += 1
        self._access += 1
        return len(a) == len(b)

    def lcp(self, left, right):
        """逐字符求两串最长公共前缀的长度。"""
        a = self._lookup(left)
        b = self._lookup(right)
        limit = min(len(a), len(b))
        pos = 0
        while pos < limit:
            self._access += 1
            if a[pos] != b[pos]:
                break
            pos += 1
        return pos

    def duplicates(self):
        """找出全部相重串，返回按下标升序排好的分组列表。

        每个分组是一个下标元组，只含下标个数大于等于二的分组，
        分组之间按各分组最小下标升序排列。
        """
        total = len(self._items)
        placed = [False] * total
        groups = []
        for anchor in range(total):
            if placed[anchor]:
                continue
            group = [anchor]
            for other in range(anchor + 1, total):
                if placed[other]:
                    continue
                if self.equal(anchor, other):
                    group.append(other)
                    placed[other] = True
            if len(group) > 1:
                placed[anchor] = True
                groups.append(tuple(group))
        return groups
