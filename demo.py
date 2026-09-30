"""evalx 现状演示。

第一段：用朴素反复扫描的实现给中缀表达式求值、转后缀记号序列、批量求值取最大值下标，
并打出字符串扫描次数，看括号一多扫描量怎么涨；
第二段：预留的调度场算法与递归下降解析演示位子，见文末注释。
"""

from evalx.expr import (
    ExprError,
    Expression,
)


def main():
    print("=== 朴素反复扫描 ===")
    ev = Expression()
    samples = [
        "1+2*3",
        "(1+2)*3",
        "-5+10",
        "2-3-4",
        "10/3",
        "-(3+4)",
        "2*-3",
    ]
    for text in samples:
        value = ev.evaluate(text)
        print("  中缀 %s 求值 %d，扫描 %d" % (text, value, ev.scan_count()))

    print("  中缀 (1+2)*3 的后缀记号 %s" % (ev.to_rpn("(1+2)*3"),))
    print("  中缀 1+2*3 的后缀记号 %s" % (ev.to_rpn("1+2*3"),))

    print("=== 变量与批量 ===")
    variables = {"a": 2, "b": 5, "c": 1}
    print("  a*b+c 求值 %d" % (ev.evaluate("a*b+c", variables),))
    results, best = ev.batch_evaluate(["1+1", "3*3", "10-4"], variables)
    print("  批量结果 %s，最大值下标 %d" % (results, best))

    print("=== 规模对照 ===")
    for depth in (1, 2, 4, 8, 16):
        text = "(" * depth + "7" + ")" * depth
        ev.evaluate(text)
        print("  括号层数 %d，扫描 %d" % (depth, ev.scan_count()))
    many = "+".join(["1"] * 40)
    ev.evaluate(many)
    print("  四十项连加，扫描 %d" % (ev.scan_count(),))

    print("=== 错误口径 ===")
    for bad in ["", "(1+2", "1+2)", "1/0", "x+1", "1+*2"]:
        try:
            ev.evaluate(bad)
        except ExprError as exc:
            print("  %s 抛 %s" % (bad, type(exc).__name__))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
