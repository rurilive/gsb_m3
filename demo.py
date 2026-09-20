"""mvstore 演示。

第一段：内存模式的基本读写。
第二段：落盘模式与重启恢复。
第三段：两事务并发读-改-写的冲突演示。
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

    print("\n=== 事务冲突（first-committer-wins）===")
    # 同一版本开启两个事务做读-改-写：先提交者生效，
    # 后提交者抛 ConflictError，缓冲整体作废，用新事务重试即可。
    mvcc = Store()
    mvcc.put("counter", 10)
    t1 = mvcc.begin()
    t2 = mvcc.begin()
    t1.put("counter", t1.get("counter") + 1)
    t2.put("counter", t2.get("counter") + 1)
    t1.commit()
    print(f"  t1 提交成功，get('counter') -> {mvcc.get('counter')}")
    try:
        t2.commit()
    except ConflictError as exc:
        print(f"  t2 提交被拒：{exc}")
    print(f"  t2 作废后 get('counter') 仍是 -> {mvcc.get('counter')}")
    retry = mvcc.begin()
    retry.put("counter", retry.get("counter") + 1)
    retry.commit()
    print(f"  用新事务重试提交后 get('counter') -> {mvcc.get('counter')}")


if __name__ == "__main__":
    main()
