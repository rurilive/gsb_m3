"""随机时间线：按固定种子生成丢包、延迟、分区、崩溃事件，供对拍用。

事件形如 (时刻, 类型, 参数)，用 apply_event 回放进 Cluster。生成器
在末尾留 quiet_tail 个周期的空白，保证所有分区都会愈合，第一个崩掉
的节点会重启，第二个一直躺到结束，给协议留出收敛的窗口。
"""

import random


def random_events(seed, node_ids, periods, period=1.0, quiet_tail=15):
    """生成一条随机时间线，返回按时刻排好序的事件列表。

    事件类型：("partition", (组一, 组二))、("heal", None)、
    ("crash", 节点)、("restart", 节点)。
    """
    ids = sorted(set(node_ids))
    if len(ids) < 2:
        raise ValueError("need at least two nodes")
    horizon = periods - quiet_tail
    if horizon < 8:
        raise ValueError("periods must exceed quiet_tail by at least 8")
    rng = random.Random(seed)
    events = []
    for _ in range(2):
        at = rng.randint(1, max(1, horizon - 6))
        shuffled = ids[:]
        rng.shuffle(shuffled)
        split = rng.randint(1, len(ids) - 1)
        group_a = tuple(sorted(shuffled[:split]))
        group_b = tuple(sorted(shuffled[split:]))
        events.append((at * period, "partition", (group_a, group_b)))
        events.append(((at + rng.randint(2, 4)) * period, "heal", None))
    targets = rng.sample(ids, min(2, len(ids)))
    for index, node_id in enumerate(targets):
        at = rng.randint(1, max(1, horizon - 7))
        events.append((at * period, "crash", node_id))
        if index == 0:
            events.append(((at + rng.randint(3, 6)) * period, "restart", node_id))
    events.sort(key=lambda ev: ev[0])
    return events


def apply_event(cluster, event):
    """把事件回放到簇上：先把时钟推到事件时刻，再动网络或时间线。"""
    at, kind, arg = event
    if at < cluster.clock.now:
        raise ValueError("event is in the past")
    while cluster.clock.now < at:
        cluster.step()
    if kind == "partition":
        cluster.network.partition(*arg)
    elif kind == "heal":
        cluster.network.heal()
    elif kind == "crash":
        cluster.schedule.crash(arg, at)
    elif kind == "restart":
        cluster.schedule.restart(arg, at)
    else:
        raise ValueError(f"unknown event kind: {kind!r}")


def is_quiet(events, at, span):
    """at 之前的 span 秒里没有任何事件就是静默的。"""
    return all(when <= at - span for when, _kind, _arg in events)
