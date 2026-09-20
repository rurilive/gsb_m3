"""quolease 现状演示。

第一段：多数派选主与 leader 续租，看成员表变化如何影响 leader。
第二段：租约多数派协商、少数派退位与代数对齐演示。
"""

from quolease.core import QuorumLease


def main():
    voters = {n: True for n in "abcde"}
    now = [1000.0]
    q = QuorumLease(voters, clock=lambda: now[0], lease_seconds=10.0)

    print("=== 成员表视图 ===")
    print(f"  members:     {q.members()}")
    print(f"  alive:       {q.alive_members()}")
    print(f"  quorum_size: {q.quorum_size()}")

    print("=== 多数派选主 ===")
    print(f"  elect() ->   {q.elect()!r}  (term={q.term()})")

    print("=== 续租 ===")
    print(f"  renew('a') -> {q.renew('a')!r}  expires_at={q.lease_expires_at()}")
    print(f"  renew('b') -> {q.renew('b')!r}  (非 leader 续不上)")

    print("=== 成员表变化 ===")
    for n in "cde":
        voters[n] = False
    print(f"  alive:       {q.alive_members()}")
    print(f"  has_quorum:  {q.has_quorum()}")
    print(f"  elect() ->   {q.elect()!r}  (少数派选不出主)")

    print("=== 租约协商 ===")
    for n in "cde":
        voters[n] = True
    now[0] = 2000.0
    receipts = {"a": 2010.0, "b": 2004.0, "c": 2007.0}
    print(f"  renew('a', {receipts})")
    print(f"    -> {q.renew('a', receipts)}  expires_at={q.lease_expires_at()}  (只认回执最短到期点)")

    print("=== 扩容后按新多数派重算 ===")
    voters["f"] = True
    voters["g"] = True
    print(f"  quorum_size: {q.quorum_size()}  (7 成员，多数派变 4)")
    small = {"a": 2010.0, "b": 2010.0, "c": 2010.0}
    print(f"  renew 3 张回执 -> {q.renew('a', small)}  (凑不齐新多数派，拒绝)")

    print("=== 分区与退位 ===")
    for n in "bcdefg":
        voters[n] = False
    stale = q.generation()
    print(f"  has_quorum: {q.has_quorum()}  (a 被隔离成少数派)")
    print(f"  renew('a') -> {q.renew('a')}  (少数派续不上租)")
    print(f"  abdicate() -> {q.abdicate()}  leader={q.leader()!r} expires={q.lease_expires_at()}")
    print(f"  write_permit('a', gen={stale}) -> {q.write_permit('a', stale)}  (退位后不发写许可)")

    print("=== 分区恢复与代数对齐 ===")
    for n in "bcdefg":
        voters[n] = True
    print(f"  elect() -> {q.elect()!r}  generation={q.generation()}")
    full = {n: 2010.0 for n in "abcd"}
    q.renew("a", full)
    print(f"  resync() -> {q.resync()}  (归来节点对齐代数)")
    print(f"  write_permit 旧代数 -> {q.write_permit('a', stale)}  (旧代数被拒)")
    print(f"  write_permit 新代数 -> {q.write_permit('a', q.resync())}")


if __name__ == "__main__":
    main()
