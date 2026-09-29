"""wbuf 现状演示。

第一段：写通存储的读写、命中与未命中、覆盖写与后端写次数。
第二段：预留的缓冲、合并与刷盘演示位子（见文末注释）。
"""

from wbuf import DictStore


def main():
    print("=== 写通读写 ===")
    store = DictStore()
    store.put("alpha", 1)
    store.put("beta", 2)
    print("  命中 alpha:", store.get("alpha"))
    print("  未命中 gamma:", store.get("gamma"))
    print("  键:", store.keys())

    print("=== 写通后端写次数 ===")
    store.put("alpha", 10)  # 同键再写一次
    store.put("alpha", 11)  # 同键又写一次
    print("  alpha 现在的值:", store.get("alpha"))
    print("  后端写次数:", store.backend_writes())
    print("  快照:", store.dump())

    # TODO(缓冲与刷盘): 内存缓冲、同键合并为最新一条、按条数或时间阈值刷盘、
    # 读穿缓冲与后端、脏项计数与崩溃丢缓冲、定时 tick 与幂等重放就位后，
    # 在这里补一遍演示：连续多次写同一个键，打印合并后的待刷项数与被省下的
    # 后端写次数；把时钟往前推过时间阈值触发一次自动刷盘，打印已刷项数、
    # 脏项数与刷盘后的后端快照。


if __name__ == "__main__":
    main()