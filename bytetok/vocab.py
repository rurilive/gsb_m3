"""字节词表：256 个基础字节 token，id 与字节值一一对应。

初始词表里 token(0) 是 b"\\x00"，token(255) 是 b"\\xff"。
后续新增的 token 一律追加在当前末尾，id 只增不改；同一 token
重复 add 返回第一次分配的 id。

特殊标记通过 add_special 登记：编码时整段保留、不参与切段与合并，
解码时原样还原。save/load 往返后，普通 token 与特殊标记的 id 完全
一致。
"""


class Vocabulary:
    """token（bytes）与整数 id 的双向映射。"""

    def __init__(self):
        self._tokens = [bytes([value]) for value in range(256)]
        self._ids = {token: index for index, token in enumerate(self._tokens)}
        self._special = {}
        self._special_order = []

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

    def add_special(self, token):
        """登记一个特殊标记：已登记则返回原 id，否则按登记顺序追加。

        token 收 bytes；str 按 UTF-8 编码后登记。空串抛 ValueError。
        特殊标记在 Tokenizer 里整段保留，不参与切段与合并。
        """
        if isinstance(token, str):
            token = token.encode("utf-8")
        token_id = self.add(token)
        if token_id not in self._special:
            self._special[token_id] = token
            self._special_order.append(token_id)
        return token_id

    def is_special(self, token_id):
        """该 id 是否登记为特殊标记。"""
        return token_id in self._special

    def special_tokens(self):
        """按登记顺序返回特殊标记字节串列表（副本）。"""
        return [self._tokens[token_id] for token_id in self._special_order]

    def special_ids(self):
        """按登记顺序返回特殊标记 id 列表（副本）。"""
        return list(self._special_order)

    def tokens(self):
        """按 id 升序返回全部 token 的字节串列表（副本）。"""
        return list(self._tokens)

    def save(self, file):
        """把词表写到路径或已打开的二进制文件对象。

        自有格式：魔数 + 条目数，每条 = 1 字节特殊标志 + 4 字节长度 +
        token 字节。基础 256 字节条目始终落盘。
        """
        if hasattr(file, "write"):
            self._write(file)
        else:
            with open(file, "wb") as handle:
                self._write(handle)

    @classmethod
    def load(cls, file):
        """save 的逆操作：从路径或二进制文件对象读回完整词表。"""
        if hasattr(file, "read"):
            return cls._read(file)
        with open(file, "rb") as handle:
            return cls._read(handle)

    def _write(self, handle):
        handle.write(b"BTKV0001")
        handle.write(len(self._tokens).to_bytes(4, "big"))
        special = set(self._special_order)
        for index, token in enumerate(self._tokens):
            handle.write(bytes([1 if index in special else 0]))
            handle.write(len(token).to_bytes(4, "big"))
            handle.write(token)

    @staticmethod
    def _read_exact(handle, size):
        chunk = handle.read(size)
        if len(chunk) != size:
            raise ValueError("词表文件已截断")
        return chunk

    @classmethod
    def _read(cls, handle):
        if cls._read_exact(handle, 8) != b"BTKV0001":
            raise ValueError("不是 bytetok 词表文件")
        count = int.from_bytes(cls._read_exact(handle, 4), "big")
        vocab = cls()
        vocab._tokens = []
        vocab._ids = {}
        vocab._special = {}
        vocab._special_order = []
        for index in range(count):
            flag = cls._read_exact(handle, 1)[0]
            length = int.from_bytes(cls._read_exact(handle, 4), "big")
            token = cls._read_exact(handle, length)
            token_id = len(vocab._tokens)
            vocab._tokens.append(token)
            vocab._ids[token] = token_id
            if flag:
                vocab._special[token_id] = token
                vocab._special_order.append(token_id)
        if count < 256:
            raise ValueError("词表文件缺少基础字节条目")
        return vocab
