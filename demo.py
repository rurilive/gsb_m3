"""mvvault 现状演示。

第一段：写入几个键、覆盖与删除，看提交时间戳与当前可见值。
第二段：预留的快照读与版本可见性演示位子（见文末注释）。
"""

from mvvault import MVStore


def main():
    print("=== 版本化写入（现有能力） ===")
    store = MVStore()
    print("  put a=1   -> ts", store.put("a", 1))
    print("  put b=2   -> ts", store.put("b", 2))
    print("  put a=10  -> ts", store.put("a", 10))
    print("  latest_ts ->", store.latest_ts)
    print("  get a     ->", store.get("a"))
    print("  delete b  ->", store.delete("b"))
    print("  keys      ->", store.keys())
    print("  get b     ->", store.get("b"))

    # TODO(快照读与版本可见性): 快照读能力实现后，在这里加一段演示：
    # 先开一个快照，再在快照起点之后继续 put 与 delete，
    # 打印同一时刻用快照读到的旧值、与当前读读到的新值，看两者分道扬镳；
    # 再按提交时间戳读历史版本，落在两次写之间的时间戳要读到中间那一版。

    # TODO(写冲突与回收): 写冲突检测与旧版本回收实现后，在这里加一段演示：
    # 两个写者都基于同一快照提交同一个键，第二个提交应抛冲突；
    # 再对带多个旧版本的键调回收，看边界时间戳之前的版本被清掉、边界起保留，
    # 并打印一次历史查询，确认被回收键只留边界之后的版本。


if __name__ == "__main__":
    main()
