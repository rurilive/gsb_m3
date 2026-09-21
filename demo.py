"""blobvault 现状演示。

第一段：按名字存取、列目录、看磁盘占用。
第二段：内容寻址与回收的演示位子（见文末注释）。
"""

import os
import shutil
import tempfile

from blobvault import ObjectStore
from blobvault.maint import disk_usage

PAYLOAD = b"cost center 7 quarterly contract, approved by legal. " * 400


def main():
    root = tempfile.mkdtemp(prefix="blobvault-demo-")
    try:
        store = ObjectStore(root)

        print("=== 按名字存取 ===")
        rel = store.put("contract-a", PAYLOAD)
        print("  put(contract-a, %d bytes) -> %s" % (len(PAYLOAD), rel))
        print("  get(contract-a) -> %d bytes" % len(store.get("contract-a")))

        # 同一份内容换个名字再存一次
        rel2 = store.put("contract-b", PAYLOAD)
        print("  put(contract-b, 同一份内容) -> %s" % rel2)
        print("  list -> %s" % store.list())
        print("  磁盘占用 -> %d bytes" % disk_usage(root))

        store.delete("contract-b")
        print("  delete(contract-b) 后 list -> %s" % store.list())
        print("  磁盘占用 -> %d bytes" % disk_usage(root))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # TODO(内容寻址与回收): 实现后在这里补一段演示，覆盖：
    # 同一份内容灌很多名字后占用只跟内容份数走、删除全部名字后跑回收并打印
    # 释放的对象数与字节数、以及在留有半成品临时文件的目录上重开store的恢复效果。


if __name__ == "__main__":
    main()
