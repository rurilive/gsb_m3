"""flowkit 现状演示。

第一段：注册状态与转移、按转移推进、看路径与非法转移的报错。
第二段：预留的守卫动作、子状态机、历史态与冲突检测演示位子（见文末注释）。
"""

from flowkit import InvalidTransition, Machine


def main():
    print("=== 流水线状态机 ===")
    m = Machine(
        initial="draft",
        states=["draft", "review", "published"],
        transitions=[("draft", "review"), ("review", "published")],
    )
    print("  状态集合:", m.states)
    print("  初始状态:", m.current)
    print("  从草稿可去:", m.targets())
    print("  推进到评审:", m.step("review"))
    print("  推进到发布:", m.step("published"))
    print("  推进路径:", m.trail)
    try:
        m.step("draft")
    except InvalidTransition as exc:
        print("  非法转移:", exc)

    # TODO(引擎扩展): 守卫与动作、子状态机嵌套、历史态与冲突检测补齐后，在这里加一段演示：
    # 给转移挂上守卫函数，条件不满足时推进被挡下、满足时才落动作；
    # 主流程里挂一个子状态机，进入子态后在其内部推进，退出再回到主流程；
    # 子态多次进出时用历史态记住上次所在的那一个子态；
    # 同一状态出发有多条守卫同时成立时检出冲突并报错；
    # 以及对未注册状态或无可用转移的推进，fail-fast 抛出带状态名的错误。


if __name__ == "__main__":
    main()