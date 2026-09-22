"""quotatree 现状演示。

第一段：注册两个团队，走一遍申请、超额被拒、归还。
第二段：同一个 req_id 重复提交，账只动一次，流水里记成重放。
第三段：预留的组织树演示位子（见文末注释）。
"""

from quotatree import Ledger, QuotaManager


def main():
    ledger = Ledger()
    quota = QuotaManager(ledger)
    quota.register("web", 100)
    quota.register("db", 40)

    print("=== 平铺团队 ===")
    print("  团队           ->", quota.teams())
    for team, want in (("web", 60), ("web", 50), ("db", 40)):
        ok = quota.acquire(team, want)
        print("  %s 申请 %3d -> %-5s 占用 %d，余 %d"
              % (team, want, ok, quota.used(team), quota.available(team)))

    print("=== 归还与重放 ===")
    quota.release("web", 20)
    quota.release("web", 30, req_id="settle-1")
    quota.release("web", 30, req_id="settle-1")
    print("  web 归还后占用 ->", quota.used("web"))
    print("  web 可用额度   ->", quota.available("web"))
    print("  流水统计       ->", ledger.stats())
    for entry in ledger.by_team("web"):
        print("    #%d %s %d ok=%s req=%s"
              % (entry["seq"], entry["kind"], entry["amount"],
                 entry["ok"], entry["req_id"]))

    print("=== 组织树演示（待补） ===")
    # 演示位子：QuotaTree 落地后，在这里补三段：
    # 1) 挂一棵带两级子团队的组织树，打印各团队的可用额度
    # 2) 子团队份额不够时向上借闲置额度完成申请，归还后额度回到上级池子
    # 3) 缩容收走闲置份额，打印被压到没余量、新申请会被拒的团队清单


if __name__ == "__main__":
    main()
