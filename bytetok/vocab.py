"""字节词表：256 个基础字节 token，id 与字节值一一对应。

初始词表里 token(0) 是 b"\\x00"，token(255) 是 b"\\xff"。
后续新增的 token 一律追加在当前末尾，id 只增不改；同一 token
重复 add 返回第一次分配的 id。

词表还随 token 一起持久化两类训练产物：

- 合并规则 merges：按学习顺序排列的 (左 id, 右 id) 元组列表。
- 特殊标记 specials：登记过的 token 集合，编码时整段保留、不参与合并。
"""

import base64


_MAGIC = "bytetok-vocab/v1"


def _b64(data):
    return base64.b64encode(data).decode("ascii")


def _unb64(text):
    return base64.b64decode(text.encode("ascii"))


class Vocabulary:
    """token（bytes）与整数 id 的双向映射。"""

    def __init__(self):
        self._tokens = [bytes([value]) for value in range(256)]
        self._ids = {token: index for index, token in enumerate(self._tokens)}
        self._specials = set()
        self._merges = []

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
        """登记特殊标记：str 按 UTF-8 转字节，bytes 原样登记。

        空字节串不是合法标记，抛 ValueError。重复登记幂等，
        已登记的普通 token 也会获得特殊标记身份。
        """
        if isinstance(token, str):
            token = token.encode("utf-8")
        if not isinstance(token, bytes):
            raise TypeError("token 必须是 bytes 或 str，收到 %r" % (type(token).__name__,))
        if not token:
            raise ValueError("空字节串不能作为特殊标记")
        token_id = self.add(token)
        self._specials.add(token)
        return token_id

    def is_special(self, token):
        """token 字节串是否登记为特殊标记。"""
        return token in self._specials

    def special_tokens(self):
        """按 id 升序返回全部特殊标记（副本）。"""
        return [token for token in self._tokens if token in self._specials]

    def register_merge(self, left_id, right_id):
        """登记一条合并规则：左 token 接右 token 合并成新 token 并追加。

        规则按调用顺序保存，训练顺序即应用优先级。合并结果已存在时
        返回既有 id，不重复登记规则。
        """
        token = self.token(left_id) + self.token(right_id)
        if token in self._ids:
            return self._ids[token]
        new_id = self.add(token)
        self._merges.append((left_id, right_id))
        return new_id

    def merges(self):
        """按学习顺序返回合并规则列表（副本）。"""
        return list(self._merges)

    def save(self, path):
        """把词表（含特殊标记与合并规则）写成纯文本文件。

        每行一条记录，字段以空格分隔、字节内容走 base64：

        - ``b <b64>``：普通新增 token。
        - ``s <b64>``：特殊标记。
        - ``m <结果> <左> <右>``：合并产生的 token 与规则两侧。

        行序即 id 序，load 后 id、特殊标记身份、合并顺序逐项还原。
        """
        merged = {}
        for left_id, right_id in self._merges:
            merged[self.token(left_id) + self.token(right_id)] = (
                self.token(left_id),
                self.token(right_id),
            )
        lines = [_MAGIC]
        for token in self._tokens[256:]:
            if token in self._specials:
                lines.append("s " + _b64(token))
            elif token in merged:
                left, right = merged[token]
                lines.append("m %s %s %s" % (_b64(token), _b64(left), _b64(right)))
            else:
                lines.append("b " + _b64(token))
        with open(path, "w", encoding="ascii", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")

    @classmethod
    def load(cls, path):
        """save 的逆操作：还原词表、特殊标记身份与合并规则顺序。"""
        with open(path, "r", encoding="ascii") as handle:
            lines = handle.read().splitlines()
        if not lines or lines[0] != _MAGIC:
            raise ValueError("不是 bytetok 词表文件：%r" % (path,))
        vocab = cls()
        for line in lines[1:]:
            fields = line.split(" ")
            kind = fields[0]
            if kind == "b":
                vocab.add(_unb64(fields[1]))
            elif kind == "s":
                vocab.add_special(_unb64(fields[1]))
            elif kind == "m":
                token, left, right = _unb64(fields[1]), _unb64(fields[2]), _unb64(fields[3])
                if token not in vocab:
                    vocab.register_merge(vocab.token_id(left), vocab.token_id(right))
            else:
                raise ValueError("无法识别的记录：%r" % (line,))
        return vocab

    def tokens(self):
        """按 id 升序返回全部 token 的字节串列表（副本）。"""
        return list(self._tokens)
