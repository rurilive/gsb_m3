"""对拍用的确定性事故脚本与纯算术参考。

make_script 用 seed 生成一串"到达 + 断链"的时间线，同样的 seed 生成一模
一样的脚本；ideal_admissions 不碰任何账本，纯算术算出上帝视角的放行上界，
拿来跟任意站点实现的结果对拍；playout 把脚本交给多线程跑完，每轮先按脚本
切链路，再让各站点的到达量并发进场，跑完 join 干净。纯标准库。
"""

import random
import threading
from dataclasses import dataclass

from slotledger.ledger import Ledger


@dataclass(frozen=True)
class Round:
    """一轮时间线：各站点到达量，以及这一轮里断着专线的站点集合。"""

    arrivals: dict
    down: tuple = ()


@dataclass(frozen=True)
class Script:
    """完整事故脚本：总配额、站点名与逐轮时间线。"""

    quota: int
    sites: tuple
    rounds: tuple


@dataclass(frozen=True)
class Ideal:
    """理想放行上界：总量、各站点分量与没放出去的量。"""

    total: int
    per_site: dict
    unserved: int


@dataclass
class PlayoutResult:
    """跑完一份脚本后的收成：账本、站点对象与各站点累计放行。"""

    ledger: Ledger
    sites: dict
    admitted: dict


def make_script(seed, sites=("alpha", "beta"), quota=200, rounds=6,
                low=20, high=160, partitions=1):
    """生成 rounds 轮的确定性事故脚本。

    每轮各站点的到达量在 low 与 high 之间随机，另抽 partitions 轮各断掉
    一个随机站点的专线（第 0 轮不动）。同样的 seed 生成一模一样的脚本。
    """
    rng = random.Random(seed)
    rs = []
    for _ in range(rounds):
        arrivals = {name: rng.randrange(low, high + 1) for name in sites}
        rs.append(Round(arrivals=arrivals))
    if rounds > 1:
        for idx in rng.sample(range(1, rounds), min(partitions, rounds - 1)):
            name = rng.choice(sites)
            rs[idx] = Round(arrivals=rs[idx].arrivals, down=(name,))
    return Script(quota=quota, sites=tuple(sites), rounds=tuple(rs))


def ideal_admissions(script):
    """纯算术参考：上帝视角的放行上界。

    假设全局即时同步、不受专线影响，按脚本顺序把各站点到达量往总池上扣，
    扣干为止。partition 只影响真实站点，不影响这条天花板。
    """
    remaining = script.quota
    per_site = {name: 0 for name in script.sites}
    arrivals_sum = 0
    for rnd in script.rounds:
        for name in script.sites:
            want = rnd.arrivals.get(name, 0)
            arrivals_sum += want
            take = min(want, remaining)
            per_site[name] += take
            remaining -= take
    served = script.quota - remaining
    return Ideal(total=served, per_site=per_site,
                 unserved=arrivals_sum - served)


def playout(script, make_site, on_round=None):
    """把脚本跑成真实的多线程放行。

    make_site(ledger, name) 建各站点；每轮先按 down 切链路，各站点的到达
    量交给独立线程并发 admit，join 完再恢复链路，on_round(index, round,
    ledger, sites) 可在每轮收尾时观察现场。返回各站点累计放行。
    """
    ledger = Ledger(script.quota)
    sites = {name: make_site(ledger, name) for name in script.sites}
    admitted = {name: 0 for name in script.sites}
    for index, rnd in enumerate(script.rounds):
        for name in rnd.down:
            ledger.set_link(name, False)
        boxes = {}
        workers = []
        for name in script.sites:
            n = rnd.arrivals.get(name, 0)
            box = []
            boxes[name] = box
            workers.append(
                threading.Thread(target=_run_arrivals, args=(sites[name], n, box))
            )
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        for name in rnd.down:
            ledger.set_link(name, True)
        for name, box in boxes.items():
            if box:
                admitted[name] += box[0]
        if on_round is not None:
            on_round(index, rnd, ledger, sites)
    return PlayoutResult(ledger=ledger, sites=sites, admitted=admitted)


def _run_arrivals(site, n, box):
    box.append(site.admit(n))
