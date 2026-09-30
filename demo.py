"""演示脚本：跑一小段有序多重集合的现有能力。

直接运行 python3 demo.py 应当正常退出（返回码为 0）。
"""

from splayx.btree import SortedBag


def run_baseline():
    b = SortedBag()
    for x in [5, 1, 4, 4, 2, 8]:
        b.insert(x)
    print("当前元素(升序):", b.to_list())
    print("中序遍历:", b.inorder())
    print("长度:", len(b))
    print("第 0 小:", b.kth(0), " 第 3 小:", b.kth(3))
    print("小于 4 的个数:", b.rank(4))
    print("4 的前驱:", b.predecessor(4))
    print("4 的后继:", b.successor(4))
    print("区间 [2, 5] 内的个数:", b.count_range(2, 5))
    b.remove(5)
    print("删除 5 之后:", b.to_list())


def run_upgraded():
    # TODO: 第二段演示（实现后补）
    pass


def main():
    run_baseline()
    run_upgraded()


if __name__ == "__main__":
    main()
