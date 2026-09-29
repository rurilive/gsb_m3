"""histkit 现状演示。

第一段：建一个 HistRecorder，push 两个状态再 undo 一步，看到当前状态
退回上一份。
第二段：预留的命令历史改造演示位子（见文末注释）。
"""

from histkit import HistRecorder


def main():
    print("=== 朴素线性撤销记录器 ===")
    rec = HistRecorder("v0")
    rec.push("v1")
    rec.push("v2")
    print("  push 两个状态，当前 state -> %s" % rec.state)
    print("  记录深度 depth -> %d" % rec.depth)
    back = rec.undo()
    print("  undo 一步，当前 state -> %s，depth -> %d" % (back, rec.depth))

    # TODO(命令历史改造): 在 histkit 里把 Recorder 扩成完整的命令历史系统
    # 之后，在这里加一段演示：先注册若干可撤销命令并执行，打印可撤销与可
    # 重做的步数，undo 再 redo，确认 redo 栈在被新命令打断后清空；再构造
    # 连续同类命令，打印合并前后的历史长度，确认合并后可整段回放；接着起
    # 一个事务，提交前故意让组内一条命令失败，打印整组回滚后的状态；最后把
    # 历史跑过上限，打印被淘汰的最旧记录以及淘汰后还能 undo 与 redo 的边界，
    # 并演示跳到历史某一点重放后的状态。


if __name__ == "__main__":
    main()
