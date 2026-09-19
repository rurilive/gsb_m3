"""CALL / RET 调用帧行为测试。"""

import unittest

from stackvm import VM, VmError, assemble, disasm
from stackvm.errors import CallOverflow


# 约定：参数在 CALL 前压栈，被调方 STORE_LOCAL 收下；返回值留在栈顶。
FIB = """
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


class TestCallRet(unittest.TestCase):
    def run_src(self, src, **vm_kwargs):
        return VM(**vm_kwargs).run(assemble(src))

    def test_nested_calls_and_recursion(self):
        # main: fib(10) = 55，递归内部是层层嵌套调用
        src = "PUSH 10\nCALL fib\nPRINT\nHALT\n" + FIB
        self.assertEqual(self.run_src(src), ["55"])

    def test_call_returns_to_next_instruction(self):
        # RET 落点：CALL 返回后从 CALL 的下一条指令继续
        src = ("PUSH 40\nCALL add2\nPRINT\nHALT\n"
               "add2:\nPUSH 2\nADD\nRET\n")
        self.assertEqual(self.run_src(src), ["42"])

    def test_double_nested_return_order(self):
        # a 调 b，b 调 c，逐级返回到各自 CALL 的下一条
        src = ("CALL a\nPUSH 1\nPRINT\nHALT\n"
               "a:\nCALL b\nPUSH 2\nPRINT\nRET\n"
               "b:\nCALL c\nPUSH 3\nPRINT\nRET\n"
               "c:\nPUSH 4\nPRINT\nRET\n")
        self.assertEqual(self.run_src(src), ["4", "3", "2", "1"])

    def test_locals_isolated_between_frames(self):
        # 被调方写 LOCAL 0 不污染调用方的 LOCAL 0
        src = ("PUSH 7\nSTORE_LOCAL 0\n"
               "CALL sub\n"
               "LOAD_LOCAL 0\nPRINT\nHALT\n"
               "sub:\nPUSH 99\nSTORE_LOCAL 0\nRET\n")
        self.assertEqual(self.run_src(src), ["7"])

    def test_callee_locals_start_empty(self):
        # 新帧局部段全新：被调方读未初始化编号抛 VmError
        src = "PUSH 1\nSTORE_LOCAL 0\nCALL sub\nHALT\nsub:\nLOAD_LOCAL 0\nRET\n"
        with self.assertRaises(VmError):
            self.run_src(src)

    def test_frames_cleared_between_runs(self):
        vm = VM()
        vm.run(assemble("CALL f\nHALT\nf:\nRET\n"))
        with self.assertRaises(VmError):
            vm.run(assemble("RET"))

    def test_ret_in_main_raises(self):
        with self.assertRaises(VmError):
            self.run_src("RET")

    def test_depth_boundary(self):
        # 恰好 max_call_depth 层嵌套可以跑，再深一层抛 CallOverflow
        chain = "CALL f1\nHALT\n"
        for i in range(1, 3):
            chain += "f%d:\nCALL f%d\nRET\n" % (i, i + 1)
        chain += "f3:\nRET\n"
        self.assertEqual(self.run_src(chain, max_call_depth=3), [])
        with self.assertRaises(CallOverflow):
            self.run_src(chain, max_call_depth=2)

    def test_depth_overflow_is_vm_error(self):
        src = "bomb:\nCALL bomb\nRET\n"
        with self.assertRaises(VmError):
            self.run_src(src, max_call_depth=8)
        with self.assertRaises(CallOverflow):
            self.run_src(src, max_call_depth=8)

    def test_assemble_disasm_roundtrip(self):
        src = "CALL f\nHALT\nf:\nRET\n"
        code = assemble(src)
        self.assertEqual(assemble(disasm(code)), code)
        text = disasm(code)
        self.assertIn("CALL 4", text)
        self.assertTrue(text.rstrip().endswith("RET"))


if __name__ == "__main__":
    unittest.main()
