"""quotatree 演示。

第一段：注册两个团队，走一遍申请、超额被拒、归还。
第二段：同一个 req_id 重复提交，账只动一次，流水里记成重放。
第三段起：组织树。挂树看可用额、子团队向上借与归还、缩容挤压清单。
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
    tree = QuotaTree(1000, ledger=Ledger())
    tree.add_node("eng", "root", 600)
    tree.add_node("ops", "root", 400)
    tree.add_node("web", "eng", 150)
    tree.add_node("api", "eng", 100)
    for name in tree.teams():
        print("  %-4s 份额 %4d 可用 %4d"
              % (name, tree.limit(name), tree.available(name)))

    print("=== 组织树：向上借与归还 ===")
    print("  eng 闲置（借出前）->", tree.idle("eng"))
    tree.acquire("web", 200, req_id="web-big-1")
    print("  web 申请 200     -> 自有 150 + 向 eng 借 50，借入", tree.borrowed("web"))
    print("  eng 闲置（借出后）->", tree.idle("eng"))
    tree.release("web", 200, req_id="web-big-1-back")
    print("  web 归还 200     -> 先还借的，eng 闲置回到", tree.idle("eng"))

    print("=== 组织树：缩容 ===")
    tree.acquire("web", 200, req_id="web-big-2")
    squeezed = tree.shrink("eng", 100)
    print("  eng 缩到 100     -> 占用压不住，实际缩到", tree.limit("eng"))
    print("  被压到没余量     ->", squeezed)
    print("  web 再申请 1     ->", tree.acquire("web", 1))
    tree.release("web", 200)
    print("  web 归还后       -> eng 闲置", tree.idle("eng"),
          "，web 可用", tree.available("web"))


if __name__ == "__main__":
    main()
