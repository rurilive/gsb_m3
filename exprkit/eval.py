"""表达式求值：在解析器产出的语法树上做递归求值。

当前只覆盖四则运算、取模、一元正负与括号。eval 每次调用都重新分词与解析，
不缓存语法树，相同表达式重复求值每次都从头再编一遍。
"""

from .ast import Binary, Number, Unary, Variable
from .errors import EvalError, EvalRuntimeError, error_at
from .parser import parse


def evaluate_node(node, env):
    """按节点类型分派求值。env 暂未使用，留给变量绑定接入。"""
    if isinstance(node, Number):
        return node.value
    if isinstance(node, Variable):
        raise error_at(
            EvalRuntimeError, "当前不支持变量 %s" % node.name, "", node.token,
        )
    if isinstance(node, Unary):
        value = evaluate_node(node.operand, env)
        if node.op == "-":
            return -value
        if node.op == "+":
            return value
        raise error_at(
            EvalRuntimeError, "不支持的一元运算符 %s" % node.op, "", node.token,
        )
    if isinstance(node, Binary):
        return _eval_binary(node, env)
    raise EvalRuntimeError("未知的语法树节点 %r" % (node,))


def _eval_binary(node, env):
    left = evaluate_node(node.left, env)
    right = evaluate_node(node.right, env)
    op = node.op
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise error_at(EvalRuntimeError, "除数不能为零", "", node.token)
        return left / right
    if op == "%":
        if right == 0:
            raise error_at(EvalRuntimeError, "取模的除数不能为零", "", node.token)
        return left % right
    raise error_at(EvalRuntimeError, "不支持的运算符 %s" % op, "", node.token)


def eval(src):
    """求表达式字符串的值，返回 int 或 float。"""
    node = parse(src)
    try:
        return evaluate_node(node, None)
    except EvalError as exc:
        # 语法树不记原文，求值层报出的错误在这里补回表达式以定位。
        if not exc.src:
            exc.src = src
        raise


# 显式别名，避免调用方写 exprkit.eval 时误以为是在调内建函数。
evaluate = eval
