"""diffcons 现状演示。

第一段：登记一批差分约束，用朴素反复松弛求一组可行解，
再看两个变量差的最大值与一组赋值的校验结果。
第二段：预留的迭代演示位子（见文末注释）。
"""

from diffcons.system import DifferenceSystem, Infeasible


def main():
    print("=== 差分约束求解（现有能力） ===")
    s = DifferenceSystem()
    s.add_le("b", "a", 3)
    s.add_le("c", "b", 2)
    s.add_le("c", "a", 10)
    s.add_eq("d", "a", 1)
    print(f"  variables()          -> {s.variables()}")
    value = s.solve()
    print(f"  solve()              -> {value}")
    print(f"  check_assignment()   -> {s.check_assignment(value)}")
    print(f"  diff_max(c, a)       -> {s.diff_max('c', 'a')}")
    print(f"  has_solution()       -> {s.has_solution()}")

    print("=== 无解判定（负环） ===")
    bad = DifferenceSystem()
    bad.add_le("x", "y", -1)
    bad.add_le("y", "x", -1)
    try:
        bad.solve()
    except Infeasible as exc:
        print(f"  Infeasible           -> {exc}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
