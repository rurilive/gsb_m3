"""editlab 现状演示。

第一段：两个等长串的逐位比较。
第二段：预留的编辑距离与对齐演示位子（见文末注释）。
"""

from editlab.diff import HammDiff


def main():
    print("=== 逐位比较 ===")
    d = HammDiff()
    a = "kitten"
    b = "sitten"
    print(f"  a = {a}")
    print(f"  b = {b}")
    print(f"  diff_count = {d.diff_count(a, b)}")
    print(f"  common_positions = {d.common_positions(a, b)}")

    # TODO(编辑距离改造): 编辑距离与对齐实现后，在这里加一段演示：
    # 打印两串的编辑距离、一条编辑脚本（对齐），以及把脚本施加到源串得到目标串。


if __name__ == "__main__":
    main()
