"""blobvault 演示：内容寻址、引用删除、垃圾回收与崩溃恢复。

直接 python3 demo.py 运行；临时目录跑完自动清掉。
"""

import os
import shutil
import tempfile

from blobvault import ObjectStore
from blobvault.keys import TMP_SUFFIX

PAYLOAD = b"cost center 7 quarterly contract, approved by legal. " * 1600


def walk_usage(root):
    total = 0
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            total += os.path.getsize(os.path.join(dirpath, fn))
    return total


def main():
    root = tempfile.mkdtemp(prefix="blobvault-demo-")
    try:
        store = ObjectStore(root)

        print("=== 按名字存取：同一份合同转多人只存一份 ===")
        rel = store.put("contract-a", PAYLOAD)
        print("  put(contract-a, %d bytes) -> %s" % (len(PAYLOAD), rel))
        for name in ("contract-b", "contract-c", "contract-d"):
            same = store.put(name, PAYLOAD)
            print("  put(%s, 同一份内容) -> %s" % (name, same))
        print("  get(contract-a) -> %d bytes" % len(store.get("contract-a")))
        print("  list -> %s" % store.list())
        print("  stats -> %s" % store.stats())
        print("  目录占用 -> %d bytes（合同本体 %d 字节）"
              % (walk_usage(root), len(PAYLOAD)))

        print("=== 删名字只减引用，对象等 gc 回收 ===")
        for name in ("contract-b", "contract-c", "contract-d"):
            store.delete(name)
        print("  删光其余名字后 stats -> %s" % (store.stats(),))
        print("  gc（contract-a 还指着，不收）-> %s" % store.gc())
        print("  gc 后 stats -> %s" % (store.stats(),))
        print("  get(contract-a) -> %d bytes" % len(store.get("contract-a")))

        print("=== 回收失败记账，下次重试 ===")
        digest = os.path.basename(rel)
        store.delete("contract-a")
        real_remove = os.remove

        def failing_remove(path, *args, **kwargs):
            if os.path.basename(path) == digest:
                raise PermissionError("模拟删不掉（被占用/权限问题）")
            return real_remove(path, *args, **kwargs)

        os.remove = failing_remove
        try:
            print("  gc（删 contract-a 时失败）-> %s" % store.gc())
        finally:
            os.remove = real_remove
        ledger = os.path.join(root, "gc", "pending")
        with open(ledger) as fh:
            print("  gc/pending 欠账 ->", fh.read().strip())
        print("  故障恢复后 gc -> %s（retry 勾销欠账）" % store.gc())

        print("=== 进程被杀：重启扫掉自己的半成品 ===")
        tmp_dir = os.path.join(root, "objects", digest[:2])
        leftover = os.path.join(tmp_dir, ".%s.deadbeef%s" % (digest, TMP_SUFFIX))
        with open(leftover, "wb") as fh:
            fh.write(b"half-written from killed process")
        foreign = os.path.join(root, "objects", "zz", "README.txt")
        os.makedirs(os.path.dirname(foreign), exist_ok=True)
        with open(foreign, "w") as fh:
            fh.write("别人的东西不动")
        print("  残留半成品存在 ->", os.path.exists(leftover))
        reopened = ObjectStore(root)
        print("  重开后半成品已扫掉 ->", not os.path.exists(leftover))
        print("  外来文件原样保留 ->", os.path.exists(foreign))
        print("  stats -> %s" % reopened.stats())
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
