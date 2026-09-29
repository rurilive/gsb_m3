"""直接写通存储，纯标准库。

现有能力（基线）：

- DictStore() 建一个内存后端，内部就是一个字典，键是普通字符串；
- put(key, value) 写一条，当场落到后端并返回值，键已存在则覆盖旧值；
- get(key) 取回值，键存在返回 (True, value)，否则返回 (False, None)；
- delete(key) 删一条并返回是否真的删掉，键本来就不在返回 False；
- keys() 按字典序列出全部键；
- dump() 给出全部键值对的快照，键按字典序；
- backend_writes() 报后端被实际写入的次数，逐条累计；
- len() / in 是条目数与成员判断。

这一层是写通的：每次 put 都直接落到后端，写次数一比一，中间没有内存
缓冲，也没有合并、刷盘与读穿。写回缓冲要在它之上另建模块。
"""


class DictStore:
    """每次写都直接落到后端的写通存储。"""

    def __init__(self):
        self._data = {}
        self._writes = 0

    def put(self, key, value):
        """写一条并返回值，键已存在则覆盖旧值。"""
        self._data[key] = value
        self._writes += 1
        return value

    def get(self, key):
        """取回值。命中返回 (True, value)，未命中返回 (False, None)。"""
        if key in self._data:
            return (True, self._data[key])
        return (False, None)

    def delete(self, key):
        """删一条并返回是否真的删掉，键不存在返回 False。"""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def keys(self):
        """全部键，按字典序。"""
        return sorted(self._data)

    def dump(self):
        """全部键值对快照，键按字典序。"""
        return {k: self._data[k] for k in sorted(self._data)}

    def backend_writes(self):
        """后端被实际写入的次数，逐条累计。"""
        return self._writes

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return key in self._data