"""平铺有序映射基线：FlatMap。

全部键值塞在一个平铺数组里：一个按键升序维护的键列表，配一条与之平行的
取值列表。插入时线性找到插入点，再把后半段整体后移；删除时线性定位，再把
后半段整体前移。没有任何树结构，没有节点，没有分裂与合并。规模一大，每次
增删都要搬动一大段数据。
"""


def _check_key(key):
    """键必须是整数或字符串，其它一律视为非法键。"""
    if isinstance(key, bool) or not isinstance(key, (int, str)):
        raise ValueError("非法键: %r" % (key,))
    return key


class FlatMap:
    """平铺有序数组实现的有序键值映射。"""

    def __init__(self):
        self._keys = []
        self._vals = []

    def put(self, key, val):
        """插入或覆盖 key。

        键已存在则就地覆盖其值并返回 False；是新键则线性找位插入并返回 True。
        """
        _check_key(key)
        for i in range(len(self._keys)):
            k = self._keys[i]
            if k == key:
                self._vals[i] = val
                return False
            if k > key:
                self._keys.insert(i, key)
                self._vals.insert(i, val)
                return True
        self._keys.append(key)
        self._vals.append(val)
        return True

    def _locate(self, key):
        """二分查找：命中返回下标，未命中返回 None。"""
        _check_key(key)
        lo = 0
        hi = len(self._keys) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            k = self._keys[mid]
            if k == key:
                return mid
            if k < key:
                lo = mid + 1
            else:
                hi = mid - 1
        return None

    def get(self, key, default=None):
        """二分查找取值，键不存在返回 default。"""
        i = self._locate(key)
        if i is None:
            return default
        return self._vals[i]

    def delete(self, key):
        """线性删除：删到返回 True，键不存在返回 False 且不动结构。"""
        _check_key(key)
        for i in range(len(self._keys)):
            if self._keys[i] == key:
                self._keys.pop(i)
                self._vals.pop(i)
                return True
        return False

    def keys_in_range(self, lo, hi):
        """闭区间 [lo, hi] 的键值对，按键升序。

        两端等号都算；lo 大于 hi 视为越界，报 ValueError。
        """
        _check_key(lo)
        _check_key(hi)
        if lo > hi:
            raise ValueError("区间越界: lo > hi")
        i = self._locate(lo)
        if i is None:
            i = 0
            while i < len(self._keys) and self._keys[i] < lo:
                i += 1
        out = []
        while i < len(self._keys) and self._keys[i] <= hi:
            out.append((self._keys[i], self._vals[i]))
            i += 1
        return out

    def keys(self):
        """按键升序返回全部键的副本。"""
        return list(self._keys)

    def items(self):
        """按键升序返回全部键值对的副本。"""
        return list(zip(self._keys, self._vals))

    def size(self):
        """当前键值对数量。"""
        return len(self._keys)

    def __len__(self):
        return len(self._keys)

    def __contains__(self, key):
        return self._locate(key) is not None
