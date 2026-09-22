"""kvsec 现状演示。

第一段：写入几笔订单，看主键读取与全量扫描。
第二段：覆盖写、删除，再看二级索引查询与计数。
第三段：预留的在线维护、落盘与恢复演示位子（见文末注释）。
"""

import os
import shutil
import tempfile

from kvsec import KVStore, SecondaryIndex


def main():
    workdir = tempfile.mkdtemp(prefix="kvsec-demo-")
    try:
        store = KVStore(os.path.join(workdir, "orders"))
        index = SecondaryIndex(store, "status")

        print("=== 写入与全量扫描 ===")
        orders = [
            ("o-1001", {"status": "new", "amount": 120}),
            ("o-1002", {"status": "new", "amount": 80}),
            ("o-1003", {"status": "paid", "amount": 200}),
        ]
        for key, record in orders:
            store.put(key, record)
        print("  keys ->", store.keys())
        print("  scan ->", store.scan())
        print("  get(o-1002) ->", store.get("o-1002"))

        print("=== 覆盖写、删除与索引查询 ===")
        store.put("o-1002", {"status": "paid", "amount": 80})
        store.delete("o-1003")
        print("  lookup(new)  ->", index.lookup("new"))
        print("  lookup(paid) ->", index.lookup("paid"))
        print("  values       ->", index.values())
        print("  index.stats  ->", index.stats())
        print("  store.stats  ->", store.stats())
        store.close()

        print("=== 在线维护、落盘与恢复（待补） ===")
        # 演示位子：重开同一个目录的存储与索引，展示重启后的
        # 查询、增量维护计数、以及索引文件损坏后的自愈。

        print("demo 目录：", workdir)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
