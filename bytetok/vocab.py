"""字节词表：256 个基础字节 token，id 与字节值一一对应。

初始词表里 token(0) 是 b"\\x00"，token(255) 是 b"\\xff"。
后续新增的 token 一律追加在当前末尾，id 只增不改；同一 token
重复 add 返回第一次分配的 id。
"""


class Vocabulary:
    """token（bytes）与整数 id 的双向映射。"""

    def __init__(self):
        self._tokens = [bytes([value]) for value in range(256)]
        self._ids = {token: index for index, token in enumerate(self._tokens)}

    def size(self):
        """当前 token 数量。"""
        return len(self._tokens)

    def __len__(self):
        return len(self._tokens)

    def __contains__(self, token):
        return token in self._ids

    def token(self, token_id):
        """按 id 取 token 的字节串；越界或非法 id 抛 KeyError。"""
        if not isinstance(token_id, int) or isinstance(token_id, bool):
            raise TypeError("token_id 必须是 int，收到 %r" % (token_id,))
        if token_id < 0 or token_id >= len(self._tokens):
            raise KeyError(token_id)
        return self._tokens[token_id]

    def token_id(self, token):
        """按 token 取 id；未登记的 token 抛 KeyError。"""
        if not isinstance(token, bytes):
            raise TypeError("token 必须是 bytes，收到 %r" % (type(token).__name__,))
        if token not in self._ids:
            raise KeyError(token)
        return self._ids[token]

    def add(self, token):
        """登记一个 token：已存在返回原 id，新 token 追加到末尾并返回新 id。

        空字节串不是合法 token，抛 ValueError。
        """
        if not isinstance(token, bytes):
            raise TypeError("token 必须是 bytes，收到 %r" % (type(token).__name__,))
        if not token:
            raise ValueError("空字节串不能作为 token")
        existing = self._ids.get(token)
        if existing is not None:
            return existing
        self._tokens.append(token)
        self._ids[token] = len(self._tokens) - 1
        return len(self._tokens) - 1

    def tokens(self):
        """按 id 升序返回全部 token 的字节串列表（副本）。"""
        return list(self._tokens)
