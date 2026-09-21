"""packwire 紧凑格式演示。

第一段：样例消息的紧凑编码、体积（对比旧定长格式）与往返。
第二段：单个值的编码开销。
第三段：StreamDecoder 分块喂入，结果与一次性解码一致。
第四段：tests/vectors.py 参考向量逐字节对拍。
"""

from packwire import StreamDecoder, decode, encode
from tests.vectors import VECTORS

SAMPLE = [
    "orders", 1, [
        [1001, "gpu-a100", 8],
        [1002, "gpu-v100", 16],
        [1003, "cpu-xeon", 64],
    ],
]


def legacy_size(obj):
    """旧定长格式（整数定长 8 字节、长度头 4 字节）会占用的字节数。"""
    if isinstance(obj, bool):
        obj = int(obj)
    if isinstance(obj, int):
        return 1 + 8
    if isinstance(obj, str):
        return 1 + 4 + len(obj.encode("utf-8"))
    if isinstance(obj, list):
        return 1 + 4 + sum(legacy_size(item) for item in obj)
    raise TypeError(type(obj).__name__)


def main():
    raw = encode(SAMPLE)
    print("=== 紧凑格式编码 ===")
    print("逻辑值: %r" % (SAMPLE,))
    print("字节数: %d（旧定长格式 %d）" % (len(raw), legacy_size(SAMPLE)))
    print("十六进制: %s" % raw.hex())
    print("解回来一致: %s" % (decode(raw) == SAMPLE))

    print()
    print("--- 单个值的编码开销 ---")
    for value in [1, 1000, "gpu", [1, 2, 3], b"\x00\x01", 0.5, {"up": True}]:
        blob = encode(value)
        print("%-14r %3d 字节  %s" % (value, len(blob), blob.hex()))

    print()
    print("--- StreamDecoder 分块喂入 ---")
    decoder = StreamDecoder()
    for i in range(0, len(raw), 3):
        decoder.feed(raw[i:i + 3])
    got = decoder.finish()
    print("按 3 字节一片喂入，解出一致: %s" % (got == SAMPLE,))

    print()
    print("--- 参考向量逐字节对拍 ---")
    mismatches = 0
    for value, hex_text in VECTORS:
        if encode(value).hex() != hex_text:
            mismatches += 1
            print("对不上: %r" % (value,))
    print("向量 %d 条，不一致 %d 条" % (len(VECTORS), mismatches))


if __name__ == "__main__":
    main()
