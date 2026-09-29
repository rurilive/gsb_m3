"""exprkit：一个纯标准库的算术表达式求值器。

当前对外能力是 eval：对四则运算、取模、一元正负与括号组成的表达式求值。
变量绑定、赋值、比较与逻辑、错误定位与缓存都留待在这个基础上补齐。
"""

from .eval import eval, evaluate
from .errors import EvalError, EvalRuntimeError, ParseError
from .lexer import tokenize
from .parser import parse

__all__ = [
    "EvalError",
    "EvalRuntimeError",
    "ParseError",
    "eval",
    "evaluate",
    "parse",
    "tokenize",
]
