"""对拍用的确定性压测计划与纯算术参考。

计划是一串 (key, delta) 的列表，按线程分段。make_plan 用 seed 生成，
同样的 seed 生成一模一样的计划；expected_totals 不碰任何计数器，纯算术
算出每个键的理论值，拿来跟任意实现的结果对拍；drive 把各段交给一个线程
去跑，跑完 join 干净。
"""

import random
import threading


def make_plan(seed, keys=("hot",), threads=4, per_thread=1000):
    """生成 threads 段、每段 per_thread 步的确定性压测计划。

    keys 的首个元素当热键，出得更密；delta 大多是正数，掺少量负数与零，
    专门用来卡总量守恒（清零或丢更新都藏不住）。
    """
    plan = []
    rng = random.Random(seed)
    hot = keys[0]
    for _ in range(threads):
        part = []
        for _ in range(per_thread):
            key = hot if rng.random() < 0.6 else rng.choice(keys)
            roll = rng.random()
            if roll < 0.05:
                delta = -1
            elif roll < 0.08:
                delta = 0
            else:
                delta = rng.randrange(1, 4)
            part.append((key, delta))
        plan.append(part)
    return plan


def expected_totals(plan):
    """纯算术参考：计划里每个键的 delta 之和，只算数学，不碰计数器。"""
    totals = {}
    for part in plan:
        for key, delta in part:
            totals[key] = totals.get(key, 0) + delta
    return totals


def drive(counter, plan, barrier=None):
    """计划的每一段交给一个线程跑，全部 join 完再返回线程列表。

    barrier 给一个 threading.Barrier 时，各线程先在栅栏上会合再开跑，
    压并发时起点更齐。
    """
    workers = [
        threading.Thread(target=_run_part, args=(counter, part, barrier))
        for part in plan
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    return workers


def _run_part(counter, part, barrier):
    if barrier is not None:
        barrier.wait()
    for key, delta in part:
        counter.incr(key, delta)
