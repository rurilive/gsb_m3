"""quolease 现状演示。

第一段：多数派选主与 leader 续租，看成员表变化如何影响 leader。
第二段：预留的租约协商与少数派退位演示位子（见文末注释）。
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

    # TODO(租约改造): 多数派协商租约与少数派退位实现后，在这里加一段过期演示：
    # 各成员回执里最短到期点决定本次租约、成员扩充后多数派变大导致续租失败、
    # 凑不齐多数派时 abdicate() 退位并让 write_permit 失效、
    # 分区归来 resync 对齐代数后旧代数写许可被拒。


if __name__ == "__main__":
    main()
