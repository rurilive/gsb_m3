"""bloomx 现状演示。

第一段：用基线 ExactSet 加入若干元素，再判断若干元素的存在性。
第二段：预留的迭代演示位子（见文末注释）。
"""

from bloomx import ExactSet


def main():
    print("=== 精确成员集合（现有能力） ===")
    s = ExactSet()
    for name in ["alice", "bob", "carol", "dave"]:
        s.add(name)
    for name in ["alice", "bob", "carol", "dave", "eve", "frank"]:
        print(f"  contains({name!r}) -> {s.contains(name)}")
    print(f"  当前元素个数 -> {s.size()}")

    # TODO(位图与哈希改造): 概率成员集合实现后，在这里加一段演示：
    # 用推导出的容量与哈希数建一个 BloomFilter，加入一批元素，
    # 再对一批确定不在集合里的元素做查询，打印被误判为存在的个数与
    # 实测假阳性率，观察它随位数组增大而下降。


if __name__ == "__main__":
    main()
