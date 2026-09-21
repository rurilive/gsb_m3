"""blobvault 演示：内容寻址去重、延迟回收与崩溃恢复。"""

import os
import shutil
import tempfile

from blobvault import ObjectStore
from blobvault.content import TMP_PREFIX
from blobvault.maint import disk_usage

PAYLOAD = b"cost center 7 quarterly contract, approved by legal. " * 400


def main():
    root = tempfile.mkdtemp(prefix="blobvault-demo-")
    try:
        store = ObjectStore(root)

        print("=== 按名字存取（内容寻址）===")
        rel = store.put("contract-a", PAYLOAD)
        print("  put(contract-a, %d bytes) -> %s" % (len(PAYLOAD), rel))
        print("  get(contract-a) -> %d bytes" % len(store.get("contract-a")))

        # 同一份内容换个名字再存一次
        rel2 = store.put("contract-b", PAYLOAD)
        print("  put(contract-b, 同一份内容) -> %s" % rel2)
        print("  两次落盘路径相同: %s" % (rel == rel2,))
        print("  list -> %s" % store.list())
        print("  stats -> %s" % store.stats())
        print("  os.walk 目录占用 -> %d bytes" % disk_usage(root))

        store.delete("contract-b")
        print("  delete(contract-b) 后 list -> %s" % store.list())
        print("  对象仍在（延迟回收）-> %s" % store.stats())

        print()
        print("=== 同一份合同挂 2000 个名字 ===")
        for i in range(2000):
            store.put("cc-%04d" % i, PAYLOAD)
        stats = store.stats()
        usage = disk_usage(root)
        print("  stats -> %s" % stats)
        print("  os.walk 目录占用 -> %d bytes (%.1f KiB)"
              % (usage, usage / 1024))

        print()
        print("=== 回收 ===")
        for i in range(2000):
            store.delete("cc-%04d" % i)
        store.delete("contract-a")
        print("  名字全删后、gc 前 -> %s" % store.stats())
        result = store.gc()
        print("  gc -> %s" % result)
        print("  gc 后 stats -> %s" % store.stats())

        print()
        print("=== 崩溃恢复：重开 store 扫掉自家半成品 ===")
        leftover = os.path.join(
            root, TMP_PREFIX + "simulated-crashed-write.part"
        )
        with open(leftover, "wb") as fh:
            fh.write(b"half written bytes from a killed process")
        os.utime(leftover, (0, 0))  # 陈旧遗留，超过在途宽限
        foreign = os.path.join(root, "ops-notes.txt")
        with open(foreign, "w") as fh:
            fh.write("运维自己放的文件，绝不能被扫掉")
        revived = ObjectStore(root)
        print("  重开后半成品还在吗 -> %s" % os.path.exists(leftover))
        print("  目录里别的文件还在吗 -> %s" % os.path.exists(foreign))
        revived.put("after-restart", b"back in business")
        print("  重开后可正常写入读取 -> %r"
              % revived.get("after-restart"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
