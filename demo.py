"""exprkit 现状演示。

第一段：四则运算的表达式的分词、解析与求值，看一遍优先级、括号与除零定位。
第二段：预留的变量绑定、比较逻辑、错误定位与缓存演示位子（见文末注释）。
"""

from exprkit import EvalRuntimeError, ParseError, eval, parse, tokenize


def main():
    print("=== 算术表达式求值 ===")
    src = "1 + 2 * (3 - 1)"
    print("  原文:", src)
    print("  token:", [(t.kind, t.text) for t in tokenize(src)])
    print("  语法树根类型:", type(parse(src)).__name__)
    print("  求值结果:", eval(src))
    print("  左结合 10 - 3 - 2 ->", eval("10 - 3 - 2"))
    print("  浮点除法 7 / 2 ->", eval("7 / 2"))
    print("  取模 17 % 5 ->", eval("17 % 5"))
    print("  一元负号 -(2 + 3) ->", eval("-(2 + 3)"))
    try:
        eval("1 / 0")
    except EvalRuntimeError as exc:
        print("  除零定位所在下标:", exc.index, "消息:", exc.message)
    try:
        eval("1 +")
    except ParseError as exc:
        print("  残缺表达式定位所在下标:", exc.index)

    # TODO(变量与缓存): VarEnv、赋值表达式、比较与逻辑运算符、带行列定位的错误诊断
    # 与表达式缓存在此基础上补齐后，在这里加一段演示：
    # 绑定变量后求值、赋值表达式把值写回绑定、带默认值取用与未定义报错、
    # && 与 || 的短路（右侧含除零也不触发）、比较链、除零或未定义变量报出行号列号、
    # 以及相同表达式与相同绑定第二次求值命中缓存（cache_stats 里 hits 增长）。


if __name__ == "__main__":
    main()
