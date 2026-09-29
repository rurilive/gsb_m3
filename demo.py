"""Small demonstration of the entropack codec.

Run with: python3 demo.py
"""

from entropack import FixedWidth


def baseline_demo():
    text = "abracadabra"
    codec = FixedWidth("abcdr")
    data = codec.encode(text)
    print("text:    ", text)
    print("alphabet:", "".join(codec.symbols))
    print("width:   ", codec.width, "bits per symbol")
    print("encoded: ", data.hex(), "(%d bytes)" % len(data))
    decoded = codec.decode(data, len(text))
    print("decoded: ", decoded)
    print("round trip ok:", decoded == text)


# TODO(变长前缀码改造): 在第二段演示里补一轮建树、编码与解码还原,
# 打印出每个符号的码长与码字、编码后的位流字节、以及解码回来是否与原文
# 逐字一致。


if __name__ == "__main__":
    baseline_demo()
