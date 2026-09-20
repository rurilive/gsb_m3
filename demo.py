"""coordx 现状演示。

第一段：协调者按注册顺序驱动两个账本参与者，提交后改动才可见。
第二段：预留的两阶段提交 / 崩溃恢复演示位子（见文末注释）。
"""

from coordx.coordinator import Coordinator, Ledger


def main():
    print("=== 顺序提交（当前行为） ===")
    left = Ledger("left", value=0)
    right = Ledger("right", value=0)
    coord = Coordinator([left, right])
    print("  participants:", coord.participants())

    coord.begin()
    left.write(10)
    right.write(20)
    print("  事务中 left=%r right=%r" % (left.value, right.value))

    coord.commit()
    print("  提交后 left=%r right=%r" % (left.value, right.value))
    print("  active=%r elapsed=%r" % (coord.active(), coord.elapsed()))

    # TODO(两阶段提交改造): 两阶段提交实现后，在这里加一段演示：
    # 让一个参与者准备时投反对（或超时），展示整体 rollback、拒绝原因；
    # 再演示协调者状态落盘、用同一个 store 重启推完未完成决议的过程。


if __name__ == "__main__":
    main()
