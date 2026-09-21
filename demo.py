"""slotledger 演示：账本记账、朴素站点、理想值对拍与断链事故、预领批量。

第一段：Ledger 划名额、归还、查账与流水。
第二段：配额充足的多线程脚本，朴素站点和纯算术理想值对拍。
第三段：专线断一轮的事故现场，朴素站点全程拒放，重现误杀。
第四段：预领批量站点断链续放、恢复对账（重发只记一次）与往返倍数。
"""

from slotledger import (
    BufferedSite,
    Ledger,
    Reconciler,
    Site,
    ideal_admissions,
    make_script,
    playout,
    round_trips,
)


def main():
    print("=== 账本基本盘 ===")
    ledger = Ledger(total=1000)
    first = ledger.grant("alpha", 300)
    second = ledger.grant("beta", 250)
    back = ledger.retire("beta", 50)
    print("  alpha 划到:", first, " beta 划到:", second, " beta 退回:", back)
    print("  剩余:", ledger.remaining(), " alpha 在外:", ledger.outstanding("alpha"))
    print("  守恒:", ledger.remaining() + ledger.outstanding() == ledger.total())
    print("  流水笔数:", len(ledger.history()))

    print("=== 朴素站点与理想值对拍（配额充足） ===")
    script = make_script(seed=7, quota=10 ** 6, rounds=4, partitions=0)
    ideal = ideal_admissions(script)
    result = playout(script, lambda ledger_, name: Site(ledger_, name))
    total = sum(result.admitted.values())
    print("  到达:", ideal.total + ideal.unserved, " 理想放行:", ideal.total)
    print("  实放:", result.admitted, " 合计:", total)
    print("  对拍一致:", total == ideal.total)
    print("  账本往返:", round_trips(result.ledger), "次，每放一个名额跑一趟")

    print("=== 断链误杀事故 ===")
    script = make_script(seed=11, quota=10 ** 6, rounds=4, partitions=2)
    ideal = ideal_admissions(script)
    log = []

    def watch(index, rnd, ledger_, sites):
        for name in rnd.down:
            log.append("  第 %d 轮 %s 专线断，到达 %d 个全被拒，原因: %s"
                       % (index, name, rnd.arrivals[name], sites[name].blocked_last()))

    result = playout(script, lambda ledger_, name: Site(ledger_, name), on_round=watch)
    print("  理想放行:", ideal.total)
    print("  实放:", result.admitted, " 合计:", sum(result.admitted.values()))
    for line in log:
        print(line)

    print("=== 预领批量：断链续放 ===")
    ledger = Ledger(total=100)
    reconciler = Reconciler(ledger)
    buffered = BufferedSite(ledger, "alpha", batch=8, reconciler=reconciler)
    print("  平时到达 3 个，放:", buffered.admit(3),
          " 一次划 8 个，手里囤:", buffered.in_hand())
    ledger.set_link("alpha", False)
    print("  专线断，到达 5 个，凭手里这批续放:", buffered.admit(5))
    print("  再到达 4 个，花完了如实拒:", buffered.admit(4),
          " 原因:", buffered.blocked_last())
    ledger.set_link("alpha", True)
    print("  恢复后到达 2 个，先对账再放行:", buffered.admit(2))
    report = reconciler.last_report("alpha")
    print("  对账上报: 累计已放", report.used, " 手里剩", report.remaining,
          " 对平:", buffered.last_reconcile_matched())
    print("  账本往返:", round_trips(ledger, "alpha"),
          "次（断链轮里零次动账）")

    print("=== 预领批量：恢复对账，重发只记一次 ===")
    ledger = Ledger(total=100)
    reconciler = Reconciler(ledger)
    buffered = BufferedSite(ledger, "alpha", batch=8, reconciler=reconciler)
    buffered.admit(3)
    ledger.set_link("alpha", False)
    buffered.admit(5)   # 手里 5 个续放完
    buffered.admit(2)   # 花完挨拒
    ledger.set_link("alpha", True)
    buffered.admit(1)   # 恢复后先对账再放行
    report = reconciler.last_report("alpha")
    print("  上报内容: 已放", report.used, " 手里剩", report.remaining,
          " 请求号:", report.req_id)
    ack = reconciler.submit(report)  # 专线重发，同一个请求号
    print("  再报一遍回执 duplicate:", ack.duplicate,
          " 账本实记:", len(reconciler.reports("alpha")), "笔")

    print("=== 预领批量：往返倍数 ===")
    quota = 640
    naive_ledger = Ledger(total=quota)
    naive = Site(naive_ledger, "alpha")
    print("  放", quota, "个名额：朴素版跑账本",
          naive.admit(quota), "趟")
    batch_ledger = Ledger(total=quota)
    batch_site = BufferedSite(batch_ledger, "alpha", batch=8)
    served = batch_site.admit(quota)
    trips = round_trips(batch_ledger)
    print("  批量版放", served, "个只跑", trips, "趟，平均每放",
          served / trips, "个一趟账本")
    print("  倍数:", round_trips(naive_ledger) / trips,
          "倍，平稳期每放 8 个最多一趟")


if __name__ == "__main__":
    main()
