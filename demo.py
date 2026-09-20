"""tickbase 现状演示。

第一段：间隔任务按网格触发，每日任务在当天固定时刻触发。
第二段：状态落盘 + 重启恢复，以及 coalesce / skip 两种 misfire 策略。
第三段：长任务不带偏节奏、不叠跑；时钟回拨不重跑。
"""

import os
import tempfile

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

    # -- 恢复与 misfire ------------------------------------------------

    state_path = os.path.join(tempfile.gettempdir(), "tickbase-demo-state.json")
    if os.path.exists(state_path):
        os.remove(state_path)

    print("=== 第一段进程：注册并跑 30 秒，触发点落盘 ===")
    clock_a = ManualClock(start=1_700_000_000.0)
    up = Scheduler(clock=clock_a, state_path=state_path)
    up.add_task("beat", IntervalTrigger(10), lambda t: None, misfire="coalesce")
    up.add_task("pulse", IntervalTrigger(30), lambda t: None, misfire="skip")
    for _ in range(3):
        clock_a.advance(10)
        up.poll()
    print(f"  停机前 beat 下次触发 @ {up.next_fire('beat'):.0f}")
    print(f"  停机前 pulse 下次触发 @ {up.next_fire('pulse'):.0f}")

    print("=== 重启：同一 state 文件，时钟已是停机 70 秒后 ===")
    clock_b = ManualClock(start=1_700_000_100.0)
    back = Scheduler(clock=clock_b, state_path=state_path)
    seen = []
    back.add_task("beat", IntervalTrigger(10), lambda t: seen.append(("beat", t)),
                  misfire="coalesce")
    back.add_task("pulse", IntervalTrigger(30), lambda t: seen.append(("pulse", t)),
                  misfire="skip")
    print(f"  恢复后 beat 下次触发 @ {back.next_fire('beat'):.0f}（接上次的计划，不重排）")
    print(f"  恢复后 pulse 下次触发 @ {back.next_fire('pulse'):.0f}")
    print(f"  第一次 poll 派发 {back.poll()}")
    print(f"  beat 补跑的计划点: {[t for n, t in seen if n == 'beat']}")
    print(f"  补完后 beat 下次触发 @ {back.next_fire('beat'):.0f}（回到原节奏）")
    print(f"  pulse 下次触发 @ {back.next_fire('pulse'):.0f}（错过的点直接丢）")
    print(f"  计数 {back.stats()}")

    print("=== 长任务：跑得比间隔长，节奏不偏、不叠跑 ===")
    clock_c = ManualClock(start=1_700_000_000.0)
    busy = Scheduler(clock=clock_c)

    def slow(t):
        print(f"    slow 触发 @ {t:.0f}，跑 25 秒")
        clock_c.advance(25)

    busy.add_task("slow", IntervalTrigger(10), slow)
    clock_c.advance(10)
    busy.poll()
    print(f"  跑完时钟到 {clock_c.now():.0f}，下次触发仍按计划网格 @ "
          f"{busy.next_fire('slow'):.0f}")
    busy.poll()
    print(f"  错过的点合并补一次后，下次触发 @ {busy.next_fire('slow'):.0f}")
    print(f"  计数 {busy.stats()}")

    print("=== 时钟回拨：跑过的点不重跑 ===")
    clock_c.set(1_700_000_015.0)
    print(f"  回拨到 {clock_c.now():.0f}，poll 派发 {busy.poll()}")
    os.remove(state_path)


if __name__ == "__main__":
    main()
