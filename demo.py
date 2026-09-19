"""mvstore 演示。

第一段：内存模式的基本读写。
第二段：落盘模式与重启恢复。
第三段：两事务写冲突演示（MVCC）。
"""

import os
import tempfile

from mvstore.store import ConflictError, Store


def main():
    print("=== 内存模式 ===")
    kv = Store()
    kv.put("feature.flag", {"enabled": True, "rollout": 30})
    kv.put("feature.name", "mvcc")
    print(f"  get('feature.flag') -> {kv.get('feature.flag')}")
    kv.delete("feature.name")
    print(f"  get('feature.name') -> {kv.get('feature.name')}")

    print("\n=== 落盘与恢复 ===")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "store.log")
        s1 = Store(path)
        s1.put("owner", "cache-team")
        s1.put("quota", 128)
        s1.delete("quota")
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                print(f"  log: {line.strip()}")
        s2 = Store(path)
        print(f"  重启后 get('owner') -> {s2.get('owner')}")
        print(f"  重启后 get('quota') -> {s2.get('quota')}")

    print("\n=== MVCC 写冲突 ===")
    kv2 = Store()
    kv2.put("quota", 128)
    t1 = kv2.begin()
    t2 = kv2.begin()
    print(f"  t1 读 quota -> {t1.get('quota')}, t2 读 quota -> {t2.get('quota')}")
    t1.put("quota", 256)
    t2.put("quota", 512)
    t1.commit()
    print("  t1 提交成功，quota -> 256")
    try:
        t2.commit()
    except ConflictError as e:
        print(f"  t2 提交被拒：ConflictError({e})")
    print(f"  最终 get('quota') -> {kv2.get('quota')}")


if __name__ == "__main__":
    main()
