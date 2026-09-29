"""演示脚本：跑一小段有序统计结构的现有功能。

直接运行 python3 demo.py 应当正常退出（返回码为 0）。
"""

from ostat.stat import SortList


def run_baseline():
    s = SortList()
    for x in [5, 1, 4, 4, 2, 8]:
        s.insert(x)
    print("当前元素(升序):", s.to_list())
    print("长度:", len(s))
    print("第 0 小:", s.kth(0), " 第 3 小:", s.kth(3))
    print("小于 4 的个数:", s.rank(4))
    print("区间 [2, 5] 内的个数:", s.count_range(2, 5))
    s.remove(5)
    print("删除 5 之后:", s.to_list())


def main():
    run_baseline()
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
