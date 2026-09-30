"""persist 现状演示。

第一段：朴素可持久化数组——建一个长度四的数组，连做几次单点修改，
再回查旧版本，打印各版本快照与一次第 k 小查询。
第二段：预留的持久化线段树与独立朴素路径对照演示位子（见文末注释）。
"""

from persist import PersistentArray


def main():
    print("=== 整份拷贝的朴素可持久化数组（基线） ===")
    arr = PersistentArray(4, 0)
    v1 = arr.modify(0, 1, 5)
    v2 = arr.modify(v1, 1, 1)
    v3 = arr.modify(v1, 2, 3)
    print("  版本总数 %d" % arr.version_count())
    for v in range(arr.version_count()):
        print("  版本 %d 快照 %r" % (v, arr.snapshot(v)))
    print("  版本 %d 下标 1 回查 %d" % (v2, arr.query(v2, 1)))
    print("  版本 %d 下标 1 回查 %d（分支未受影响）" % (v3, arr.query(v3, 1)))
    print("  区间 %d..%d 第 2 小 %d" % (0, v3, arr.kth(0, v3, 2)))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
