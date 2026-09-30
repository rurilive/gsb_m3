"""huffman 现状演示。

第一段：朴素哈夫曼——线性重扫挑最小权重建树，再逐字符编码与解码。
第二段：预留的优先队列建树演示位子（见文末注释）。
"""

from huffman import HuffmanCodec, NaiveIndexHeap, build_frequency


def main():
    print("=== 朴素哈夫曼：重扫建树、编码、解码 ===")
    text = "abracadabra"
    codec = HuffmanCodec(build_frequency(text))
    print("  符号表 ->", codec.symbols())
    print("  码表 ->", codec.code_table())
    bits = codec.encode(text)
    print("  编码 ->", bits)
    print("  解码 ->", codec.decode(bits))
    print("  加权路径长度 ->", codec.weighted_path_length())
    print("  平均码长 ->", codec.average_length())
    print("  线性重扫次数 ->", codec.rescan_count())

    print("=== 朴素索引堆：取出顺序确定 ===")
    heap = NaiveIndexHeap()
    for item in [(2, "b"), (1, "a"), (2, "c"), (1, "d")]:
        heap.push(item)
    print("  依次取出 ->", [heap.pop() for _ in range(len(heap))])

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
