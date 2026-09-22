"""quotatree 现状演示。

第一段：注册两个团队，走一遍申请、超额被拒、归还。
第二段：同一个 req_id 重复提交，账只动一次，流水里记成重放。
第三段：组织树演示，挂树、向上借还、缩容压零。
"""

from quotatree import Ledger, QuotaManager, QuotaTree


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

    print("=== 组织树：挂树 ===")
    tree = QuotaTree(1000)
    tree.add_node("eng", "root", 600)
    tree.add_node("ops", "root", 300)
    tree.add_node("web", "eng", 250)
    tree.add_node("db", "eng", 250)
    for name in tree.nodes():
        print("  %-4s 份额 %4d  可用 %4d"
              % (name, tree.limit(name), tree.available(name)))

    print("=== 组织树：向上借与归还 ===")
    print("  eng 借出前闲置 ->", tree.free("eng"))
    tree.acquire("web", 350, req_id="w1")
    print("  web 申请 350 -> 占用 %d，其中借入 %d"
          % (tree.used("web"), tree.borrowed("web")))
    print("  eng 借出后闲置 ->", tree.free("eng"))
    tree.release("web", 350, req_id="w2")
    print("  web 归还 350 -> 借入 %d，eng 闲置回到 %d"
          % (tree.borrowed("web"), tree.free("eng")))

    print("=== 组织树：缩容压零 ===")
    tree.acquire("web", 250, req_id="w3")
    tree.acquire("db", 250, req_id="d1")
    tree.acquire("ops", 300, req_id="o1")
    tree.acquire("eng", 100, req_id="e1")
    print("  总预算 1000 砍到 900，被压到没余量的团队 ->",
          tree.shrink("root", 900))
    print("  web 再申请 1 ->", tree.acquire("web", 1))
    print("  web 可用额   ->", tree.available("web"))


if __name__ == "__main__":
    main()
