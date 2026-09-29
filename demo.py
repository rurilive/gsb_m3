"""FlatXor 现状演示。

第一段: 加入元素, 看线性扫描下的异或最大 / 最小, 不大于计数与数对异或最大。
第二段: 预留的按位字典树演示位子 (见文末注释)。
"""

from xorlib.xor import FlatXor


def main():
    print("=== 朴素异或集合 ===")
    s = FlatXor()
    for v in (3, 10, 5, 25, 2, 8):
        s.add(v)

    print(f"  len          = {len(s)}")
    print(f"  values       = {s.values()}")
    print(f"  max_xor(8)   = {s.max_xor(8)}")
    print(f"  min_xor(8)   = {s.min_xor(8)}")
    print(f"  count_le(6)  = {s.count_le(6)}")
    print(f"  max_xor_pair = {s.max_xor_pair()}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
