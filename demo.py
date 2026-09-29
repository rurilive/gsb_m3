"""bitlib 现状演示。

第一段：BoolBits 设若干位、查位计数与置位清单。
第二段：字级位运算改造的集合运算与位计数演示（见文末注释）。
"""

from bitlib import BoolBits


def main():
    print("=== 布尔列表位集合 ===")
    b = BoolBits(16)
    for i in (1, 4, 9, 15):
        b.set(i)
    print("  置位清单:", b.to_list())
    print("  位计数:", b.count())
    print("  第 4 位取值:", b.get(4))
    b.clear(4)
    print("  清零第 4 位后取值:", b.get(4))

    other = BoolBits(16)
    other.set(4)
    other.set(15)
    print("  与:", b.intersection(other).to_list(), "或:", b.union(other).to_list())

    # TODO(字级位运算改造): 字级位集合就位后在这里补一段演示：
    # 用整数数组按机器字打包位，置位、清零、取值用位运算操作到字；
    # 求两个集合的与、或、异或、差与补，按字整体运算，并与布尔列表口径逐项一致；
    # 再演示求置位总数、找第一个置位与第 k 个置位。


if __name__ == "__main__":
    main()
