"""tickbase 现状演示。

第一段：间隔任务按网格触发，每日任务在当天固定时刻触发。
第二段：预留的恢复与 misfire 演示位子（见文末注释）。
"""

from tickbase import DailyTrigger, IntervalTrigger, ManualClock, Scheduler


def main():
    clock = ManualClock(start=1_700_000_000.0)
    sched = Scheduler(clock=clock)

    def beat(t):
        print(f"    beat 触发 @ {t:.0f}")

    def report(t):
        print(f"    report 触发 @ {t:.0f}")

    sched.add_task("beat", IntervalTrigger(10), beat)
    sched.add_task("report", DailyTrigger(9, 30), report)

    print("=== 注册 ===")
    for task in sched.tasks():
        print(f"  {task.name}: 下次触发 @ {sched.next_fire(task.name):.0f}")

    print("=== 时钟每 5 秒走一步，poll 三次 ===")
    for _ in range(3):
        clock.advance(5)
        print(f"  当前 {clock.now():.0f}，接下来 poll")
        fired = sched.poll()
        print(f"    本次派发 {fired}")

    print("=== 快进到 report 的下一次触发点 ===")
    clock.set(sched.next_fire("report"))
    print(f"  当前 {clock.now():.0f}，接下来 poll")
    print(f"    本次派发 {sched.poll()}")
    for task in sched.tasks():
        print(f"  {task.name}: 下次触发 @ {sched.next_fire(task.name):.0f}")

    print("=== 计数 ===")
    print(f"  {sched.stats()}")

    # TODO(恢复改造): state_path 与 misfire 策略落地后，在这里补演示：
    # 1) 注册并推进一段之后，用同一个 state 文件起第二个 Scheduler，
    #    同名任务重新注册，看它接着上次的计划时间算，而不是从当前时刻重排
    # 2) 停机期间错过多次触发时，skip 与 coalesce 两种策略的差别，
    #    以及 coalesce 只补一次、之后回到原来的节奏
    # 3) 长任务还没跑完又到触发点的时候，skipped 与 coalesced 怎么记


if __name__ == "__main__":
    main()
