"""FlatMap 现状演示。

第一段：跑通基线功能（插入、覆盖、删除、区间查询、大小）。
第二段：B 树改造后补一轮插入、分裂与区间查询演示（见文末占位）。
"""

from btreex.store import FlatMap


def main():
    print("=== 平铺有序映射 ===")
    m = FlatMap()
    for k in (5, 1, 4, 2, 3):
        m.put(k, k * k)
    print(f"  keys        = {m.keys()}")
    print(f"  get(4)      = {m.get(4)}")
    print(f"  get(9)      = {m.get(9)}")
    print(f"  range(2, 4) = {m.keys_in_range(2, 4)}")
    print(f"  size        = {m.size()}")
    print(f"  delete(4)   = {m.delete(4)}")
    print(f"  keys        = {m.keys()}")

    # TODO: 第二段演示（实现后补）——补一轮插入触发分裂、按区间范围查询、
    # 按序遍历全部键值。


if __name__ == "__main__":
    main()
