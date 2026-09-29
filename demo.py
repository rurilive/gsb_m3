"""cuckoox 现状演示。

第一段：用基线 ExactBag 加入若干元素，判断存在性，并做一次删除。
第二段：预留的迭代演示位子（见文末注释）。
"""

from cuckoox import ExactBag


def main():
    print("=== 精确成员集合（现有能力） ===")
    bag = ExactBag()
    for name in ["alice", "bob", "carol", "dave"]:
        bag.add(name)
    for name in ["alice", "bob", "carol", "dave", "eve", "frank"]:
        print("  contains({0!r}) -> {1}".format(name, bag.contains(name)))
    print("  当前元素个数 -> {0}".format(bag.size()))

    bag.discard("dave")
    print("  删除 dave 后 contains('dave') -> {0}".format(bag.contains("dave")))
    print("  当前元素个数 -> {0}".format(bag.size()))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
