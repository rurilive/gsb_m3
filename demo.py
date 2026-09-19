"""stackvm 现状演示：汇编 -> 反汇编 -> 执行 -> 调用帧。"""

from stackvm import VM, CallOverflow, assemble, disasm

SUM10 = """
# 求 1+2+...+10，结果存全局段 0 号槽
PUSH 0
STORE_G 0      # 累加器
PUSH 1
STORE_G 1      # i
loop:
LOAD_G 1
PUSH 10
GT             # i > 10 ?
JZ body        # 还没超过就继续循环
JMP done
body:
LOAD_G 0
LOAD_G 1
ADD
STORE_G 0
LOAD_G 1
PUSH 1
ADD
STORE_G 1
JMP loop
done:
LOAD_G 0
PRINT
HALT
"""

FIB = """
# 递归 fib：参数经操作数栈传入，结果留在栈顶；每帧局部段独立
fib:
STORE_LOCAL 0      # n
LOAD_LOCAL 0
PUSH 2
LT                 # n < 2 ?
JZ recurse
LOAD_LOCAL 0       # 基例：返回 n
RET
recurse:
LOAD_LOCAL 0
PUSH 1
SUB
CALL fib           # fib(n-1)
STORE_LOCAL 1
LOAD_LOCAL 0
PUSH 2
SUB
CALL fib           # fib(n-2)
LOAD_LOCAL 1
ADD
RET
"""

BOMB = """
# 无限递归：触发调用栈深度上限
bomb:
CALL bomb
RET
"""

ORDER = """
# 演示局部段：算 (20+22)*2
PUSH 20
STORE_LOCAL 0
PUSH 22
STORE_LOCAL 1
LOAD_LOCAL 0
LOAD_LOCAL 1
ADD
PUSH 2
MUL
PRINT
HALT
"""


def main():
    print("=== SUM10 反汇编（前 6 行） ===")
    code = assemble(SUM10)
    print("\n".join(disasm(code).splitlines()[:6]))

    print("\n=== 执行 SUM10 ===")
    vm = VM()
    print("  output:", vm.run(code), " globals[0]:", vm.globals[0])

    print("\n=== 执行 ORDER（局部段用法） ===")
    print("  output:", VM().run(assemble(ORDER)))

    print("\n=== 执行 FIB（递归调用帧，fib(10)） ===")
    print("  output:", VM().run(assemble("PUSH 10\nCALL fib\nPRINT\nHALT\n" + FIB)))

    print("\n=== 调用栈深度上限（max_call_depth=8 的无限递归） ===")
    try:
        VM(max_call_depth=8).run(assemble(BOMB))
    except CallOverflow as exc:
        print("  CallOverflow:", exc)


if __name__ == "__main__":
    main()
