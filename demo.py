"""dagsched 现状演示。

第一段：建一张小图，看拓扑排序与就绪任务。
第二段：预留的迭代演示位子（见文末注释）。
"""

from dagsched.scheduler import Scheduler


def main():
    print("=== 拓扑排序（现有能力） ===")
    s = Scheduler()
    for name in ["fetch", "parse", "render", "publish"]:
        s.add_task(name)
    s.add_dependency("parse", "fetch")
    s.add_dependency("render", "parse")
    s.add_dependency("publish", "render")
    print(f"  topo_order()   -> {s.topo_order()}")
    print(f"  ready_tasks()  -> {s.ready_tasks()}")
    print(f"  successors(fetch) -> {sorted(s.successors('fetch'))}")

    # TODO(分层调度改造): 并行层级划分实现后，在这里加一段演示：
    # 把上面的图换成菱形依赖，打印 levels() 的逐层任务名，
    # 展示同一层可并发；再演示 set_priority 后同层内的排序，
    # 以及 mark_failed 触发的下游连坐与 run_order 剔除结果。

    # TODO(环检测改造): 可调度判断实现后，在这里加一段演示：
    # 构造一个环，捕获 ScheduleImpossible，打印它的 nodes 属性。


if __name__ == "__main__":
    main()