"""偏移探针：看对端墙上钟比本机快多少。

现在的口径一锤子买卖：跑一次往返，拿对端收到请求那一下的读数减去本地
发出那一下的读数。请求方向在路上走了多久，估计就偏多少；不滤波，也不
给任何质量信息，链路抖一下或者对端读错一次，数字就跟着走样。
"""


class OffsetProbe:
    """单次偏移探针。"""

    def __init__(self, loopback):
        self._loopback = loopback

    def probe(self):
        """跑一次往返，返回一个偏移估计，单位秒。"""
        t0, t1, _t2, _t3 = self._loopback.exchange()
        return t1 - t0
