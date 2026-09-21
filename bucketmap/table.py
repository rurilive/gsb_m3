"""分桶链表的哈希表，单线程实现。

每个桶就是一条 (key, value) 链，装载因子超过阈值时桶数翻倍并重哈希。
值不能是 None，None 用来表示缺失，所以 get 的默认值也不许是 None。
"""


class HashMap:
    """单线程哈希表。

    capacity：初始桶数；load_factor：装载因子阈值，size 超过
    capacity * load_factor 就翻倍；auto_grow=False 时只负责读写，
    什么时候扩容交给外层调度。
    """

    def __init__(self, capacity=8, load_factor=0.75, auto_grow=True):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if load_factor <= 0:
            raise ValueError("load_factor must be > 0")
        self._buckets = [[] for _ in range(int(capacity))]
        self._load_factor = float(load_factor)
        self._auto_grow = bool(auto_grow)
        self._size = 0

    @property
    def buckets(self):
        """桶列表本身，按桶腾挪时直接用它。"""
        return self._buckets

    @property
    def capacity(self):
        return len(self._buckets)

    @property
    def load_factor(self):
        return self._load_factor

    @property
    def size(self):
        return self._size

    def __len__(self):
        return self._size

    def bucket_index(self, key):
        """key 落在哪个桶。"""
        return hash(key) % len(self._buckets)

    def put(self, key, value):
        """写入并返回该键的原值，键不存在时返回 None。"""
        if value is None:
            raise ValueError("value must not be None")
        bucket = self._buckets[self.bucket_index(key)]
        for pos, (k, old) in enumerate(bucket):
            if k == key:
                bucket[pos] = (key, value)
                return old
        bucket.append((key, value))
        self._size += 1
        if self._auto_grow and self._size > len(self._buckets) * self._load_factor:
            self._grow()
        return None

    def get(self, key, default=None):
        for k, value in self._buckets[self.bucket_index(key)]:
            if k == key:
                return value
        return default

    def delete(self, key):
        """删除键，返回是否真的删掉了。桶整体重建，链上顺序不变。"""
        index = self.bucket_index(key)
        bucket = self._buckets[index]
        for pos, (k, _value) in enumerate(bucket):
            if k == key:
                self._buckets[index] = bucket[:pos] + bucket[pos + 1:]
                self._size -= 1
                return True
        return False

    def items(self):
        """全部 (key, value)，按桶序拼接。"""
        entries = []
        for bucket in self._buckets:
            entries.extend(bucket)
        return entries

    def keys(self):
        return [key for key, _value in self.items()]

    def _grow(self):
        """翻倍重哈希，单线程里一步到位。"""
        old = self._buckets
        self._buckets = [[] for _ in range(len(old) * 2)]
        for bucket in old:
            for key, value in bucket:
                self._buckets[self.bucket_index(key)].append((key, value))
