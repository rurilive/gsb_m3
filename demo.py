"""quolease 现状演示。

第一段：多数派选主与 leader 续租，看成员表变化如何影响 leader。
第二段：租约多数派协商、扩容重算、分区退位与归来 resync。
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

    print("=== 租约协商：回执里最短的到期点生效 ===")
    for n in "cde":
        voters[n] = True
    now[0] = 2000.0
    acks = {"a": 2010.0, "b": 2006.0, "c": 2008.0}
    print(f"  acks:        {acks}")
    print(f"  renew('a') -> {q.renew('a', acks)!r}  expires_at={q.lease_expires_at()}")
    stale_gen = q.generation()
    print(f"  write_permit(generation={stale_gen}) -> {q.write_permit(stale_gen)!r}")

    print("=== 扩容：多数派按新配置重算 ===")
    voters["f"] = True
    voters["g"] = True
    print(f"  members: {q.members()}  quorum_size: {q.quorum_size()}")
    acks3 = {"a": 2010.0, "b": 2010.0, "c": 2010.0}
    print(f"  3 票回执续租 -> {q.renew('a', acks3)!r}  (凑不齐新多数派)")
    acks4 = {"a": 2010.0, "b": 2007.0, "c": 2010.0, "d": 2009.0}
    print(f"  4 票回执续租 -> {q.renew('a', acks4)!r}  expires_at={q.lease_expires_at()}")

    print("=== 分区：凑不齐多数派主动退位 ===")
    for n in "cdefg":
        voters[n] = False
    print(f"  alive: {q.alive_members()}  has_quorum: {q.has_quorum()}")
    print(f"  renew('a') -> {q.renew('a')!r}  (少数派续不上租)")
    print(f"  write_permit -> {q.write_permit(q.generation())!r}")
    q.abdicate()
    print(f"  abdicate() 后 leader={q.leader()!r}  expires_at={q.lease_expires_at()!r}"
          f"  generation={q.generation()}")

    print("=== 分区归来：resync 对齐代数 ===")
    for n in "cdefg":
        voters[n] = True
    peer = QuorumLease(voters, clock=lambda: now[0], lease_seconds=10.0)
    print(f"  归来节点本地代数 {peer.generation()}，集群代数 {q.generation()}")
    peer.resync(q.generation())
    print(f"  resync 后归来节点代数: {peer.generation()}")
    print(f"  elect() -> {q.elect()!r}  (generation={q.generation()})")
    q.renew("a")
    print(f"  旧代数写许可 write_permit({stale_gen}) -> {q.write_permit(stale_gen)!r}")
    print(f"  当代写许可 write_permit({q.generation()}) -> {q.write_permit(q.generation())!r}")


if __name__ == "__main__":
    main()
