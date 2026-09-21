"""slotledger 现状演示：账本记账、朴素站点、理想值对拍与断链误杀。

第一段：Ledger 划名额、归还、查账与流水。
第二段：配额充足的多线程脚本，朴素站点和纯算术理想值对拍。
第三段：专线断一轮的事故现场，朴素站点全程拒放，重现误杀。
文末留了预领批量版的演示位子。
"""

from slotledger import (
    BufferSite,
    Ledger,
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
    script = make_script(seed=11, quota=10 ** 6, rounds=4, partitions=2)
    ideal = ideal_admissions(script)
    released_so_far = {}
    continued = []

    def watch_buffer(index, rnd, ledger_, sites):
        for name in script.sites:
            before = released_so_far.get(name, 0)
            now = sites[name].released()
            released_so_far[name] = now
            if name in rnd.down:
                continued.append(
                    "  第 %d 轮 %s 专线断，到达 %d 个，凭手里的批续放 %d 个"
                    % (index, name, rnd.arrivals[name], now - before))

    result = playout(script, lambda ledger_, name: BufferSite(ledger_, name),
                     on_round=watch_buffer)
    print("  理想放行:", ideal.total)
    print("  实放:", result.admitted, " 合计:", sum(result.admitted.values()))
    for line in continued:
        print(line)

    print("=== 恢复对账与收工 ===")
    ledger_ = result.ledger
    reports = [entry for entry in ledger_.history() if entry.kind == "report"]
    print("  对账上报 %d 笔：" % len(reports),
          ["%s#%d" % (entry.site, entry.amount) for entry in reports])
    for name, site in result.sites.items():
        back = site.close()
        print("  %s 收工退回囤的 %d 个，账本确认已用 %d 个"
              % (name, back, ledger_.used(name)))
    books = ledger_.remaining() + ledger_.outstanding() + ledger_.used()
    print("  两边对得上:", books == ledger_.total(),
          " 在外:", ledger_.outstanding(), " 已用:", ledger_.used())

    print("=== 账本往返对比 ===")
    naive_result = playout(script, lambda ledger_, name: Site(ledger_, name))
    naive_trips = round_trips(naive_result.ledger)
    buffer_trips = round_trips(ledger_)
    buffer_total = sum(result.admitted.values())
    print("  朴素站点: %d 次往返（每放一个跑一趟）" % naive_trips)
    print("  预领批量: %d 次往返，平均每趟放行 %.0f 个（红线 8 个一趟）"
          % (buffer_trips, buffer_total / max(buffer_trips, 1)))


if __name__ == "__main__":
    main()
