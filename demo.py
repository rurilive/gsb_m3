"""packwire 现状演示。

第一段：一个样例消息的编码、体积与往返。
第二段：紧凑格式落地后的演示位子（见文末注释）。
"""

from packwire import decode, encode

SAMPLE = [
    "orders", 1, [
        [1001, "gpu-a100", 8],
        [1002, "gpu-v100", 16],
        [1003, "cpu-xeon", 64],
    ],
]


def main():
    raw = encode(SAMPLE)
    print("=== 定长格式编码 ===")
    print("逻辑值: %r" % (SAMPLE,))
    print("字节数: %d" % len(raw))
    print("十六进制: %s" % raw.hex())
    print("解回来一致: %s" % (decode(raw) == SAMPLE))

    print()
    print("--- 单个值的编码开销 ---")
    for value in [1, 1000, "gpu", [1, 2, 3]]:
        blob = encode(value)
        print("%-14r %3d 字节  %s" % (value, len(blob), blob.hex()))

    # TODO(紧凑格式): 紧凑编码与规范形落地后，在这里补一段演示：
    # 1) 同一份 SAMPLE 的新格式编码，跟上面的定长编码比体积，打印规范形十六进制
    # 2) 用 StreamDecoder 把编码后的字节流按小片喂进去，和一次性解码对一下
    # 3) 拿 tests/vectors.py 的向量做一次逐字节对拍，打印结果


if __name__ == "__main__":
    main()
