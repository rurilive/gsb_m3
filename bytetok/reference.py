"""朴素逐字节参考实现。

这是分词行为的地面真值：一个字节一个 token，没有任何合并。
任何走样（少一字节、乱序、丢信息）都能在这里被抓出来。
"""


def naive_encode(vocab, data):
    """把每个字节单独映射成 id，结果长度恒等于字节数。"""
    if not isinstance(data, bytes):
        raise TypeError("naive_encode 只接受 bytes，收到 %r" % (type(data).__name__,))
    return [vocab.token_id(bytes([value])) for value in data]


def naive_decode(vocab, ids):
    """把 id 序列按字节拼回去。对纯字节词表即 encode 的逆操作。"""
    return b"".join(vocab.token(token_id) for token_id in ids)
