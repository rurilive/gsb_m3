"""huffx 现状演示。

第一段：朴素哈夫曼——线性重扫挑最小频次建树，逐字符编码与解码。
第二段：预留的堆与优先队列演示位子（见文末注释）。
"""

from huffx import HuffmanTree, build_frequency


def main():
    print("=== 朴素哈夫曼：重扫建树、编码、解码 ===")
    text = "abracadabra"
    tree = HuffmanTree(build_frequency(text))
    print("  符号 ->", tree.symbols())
    print("  码表 ->", tree.code_table())
    bits = tree.encode(text)
    print("  编码 ->", bits)
    print("  解码 ->", tree.decode(bits))
    print("  加权路径长度 ->", tree.weighted_path_length())
    print("  平均码长 ->", tree.average_length())
    print("  定长口径平均码长 ->", tree.naive_average_length())
    print("  建树线性重扫次数 ->", tree.rescan_count())

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
