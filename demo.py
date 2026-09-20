"""txnkit 事务隔离现状演示。

五段场景分别看：事务内先写后读、提交后与调用方是否共享可变结构、
回滚能否恢复被删的键、两个事务先后提交的合并结果、
以及事务开始后被别人改过的键是否按约定判冲突。
"""

from txnkit.store import ConflictError, KVStore


def section(title):
    print(f"=== {title} ===")


def main():
    section("事务内先写后读")
    s = KVStore({"counter": 0})
    t = s.begin()
    t.set("counter", 1)
    print(f"  事务内 set 成 1 后再 get -> {t.get('counter')!r}（期望 1）")
    t.commit()

    section("提交后与调用方是否共享嵌套结构")
    s = KVStore()
    t = s.begin()
    cfg = {"tags": ["a"]}
    t.set("cfg", cfg)
    t.commit()
    cfg["tags"].append("b")          # 调用方提交后继续改自己手里的那个对象
    print(f"  调用方追加后 store.get('cfg') -> {s.get('cfg')!r}（期望 {{'tags': ['a']}}）")

    section("回滚能否恢复被删的键")
    s = KVStore({"a": 1, "b": 2})
    t = s.begin()
    t.delete("a")
    t.rollback()
    print(f"  rollback 后 store.get('a') -> {s.get('a')!r}（期望 1）")

    section("两个事务先后提交")
    s = KVStore()
    t1 = s.begin()
    t1.set("a", 1)
    t1.commit()
    t2 = s.begin()
    t2.set("b", 2)
    t2.commit()
    print(f"  两次提交后 store.keys() -> {sorted(s.keys())}（期望 ['a', 'b']）")

    section("事务开始后被别人改过的键")
    s = KVStore({"a": 0})
    t1 = s.begin()
    t2 = s.begin()
    t1.set("a", 1)
    t1.commit()
    t2.set("a", 2)
    try:
        t2.commit()
        print(f"  后提交的事务没报冲突，store.get('a') -> {s.get('a')!r}（期望抛 ConflictError）")
    except ConflictError as exc:
        print(f"  冲突已按约定抛出：{exc}")


if __name__ == "__main__":
    main()
