"""规则编译：DSL 文本 -> matcher 树 -> FlagEngine。

管线：tokenize -> 逐行解析语句 -> 查 OP_TABLE / COMBINATOR_TABLE 构建
matcher。所有校验（语法、未知操作符/组合器、参数个数、类型、重复定义）
都在编译期完成，报错带行列位置；编译通过后求值阶段不再报错。

DSL 语法（一行一条语句）：

    # 注释
    flag 开关名
    when 表达式 -> on|off
    default on|off

    表达式 := and(表达式, 表达式, ...) | or(表达式, 表达式, ...)
            | not(表达式) | 子句
    子句   := 字段 操作符 取值 | 字段 in [取值, 取值, ...]
            | 字段 regex "正则模式"
    操作符 := eq ne contains gt ge lt le in regex
    取值   := 带引号字符串 | 数字 | true | false | 裸词（按字符串处理）
"""

import re

from .engine import FlagEngine, FlagSpec, Rule
from .errors import RuleCompileError
from .lexer import tokenize
from .matchers import (
    All, Any, Compare, Contains, Equals, InSet, Not, NotEquals, Regex,
)

OP_TABLE = {
    "eq": Equals,
    "ne": NotEquals,
    "contains": Contains,
    "in": InSet,
    # regex 的取值需带行列位置做编译期校验，在 parse_clause 里特判构建
    "regex": Regex,
    "gt": lambda f, v: Compare("gt", f, v),
    "ge": lambda f, v: Compare("ge", f, v),
    "lt": lambda f, v: Compare("lt", f, v),
    "le": lambda f, v: Compare("le", f, v),
}

NUMERIC_OPS = ("gt", "ge", "lt", "le")

COMBINATOR_TABLE = {
    "and": All,
    "or": Any,
    "not": lambda children: Not(children[0]),
}

# 组合器元数：(最少参数, 最多参数)，None 表示不限
COMBINATOR_ARITY = {
    "and": (2, None),
    "or": (2, None),
    "not": (1, 1),
}

_REPEAT_BRACE_RE = re.compile(r"\{(\d+)(,(\d*))?\}")


def check_pattern_safety(pattern, line, col):
    """拒绝可能灾难性回溯的正则：无界量词（* + {m,}）嵌套作用在
    本身已含量词的分组上，如 (a+)+、(\\d|x)*。编译期调用，O(模式长)。"""
    stack = []  # 每个未闭合分组一项：组内（含子组）是否已出现量词
    prev_group_quantified = False
    in_class = False
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            prev_group_quantified = False
            continue
        if in_class:
            if ch == "]":
                in_class = False
            i += 1
            continue
        if ch == "[":
            in_class = True
        elif ch == "(":
            stack.append(False)
            if pattern.startswith("?", i + 1):
                i += 1  # (?: (?= 等组前缀里的 ? 不是量词
        elif ch == ")":
            has_quant = stack.pop() if stack else False
            if stack:
                stack[-1] = stack[-1] or has_quant
            prev_group_quantified = has_quant
            i += 1
            continue
        elif ch in "*+?":
            if prev_group_quantified and ch in "*+":
                raise RuleCompileError(
                    f"正则含嵌套量词，可能灾难性回溯：{pattern!r}", line, col)
            if stack:
                stack[-1] = True
        elif ch == "{":
            m = _REPEAT_BRACE_RE.match(pattern, i)
            if m is None:
                pass  # 非法重复写法按字面量处理，交给 re.compile 裁决
            else:
                unbounded = m.group(2) is not None and m.group(3) == ""
                if prev_group_quantified and unbounded:
                    raise RuleCompileError(
                        f"正则含嵌套量词，可能灾难性回溯：{pattern!r}",
                        line, col)
                if stack:
                    stack[-1] = True
                i += m.end() - 1
        prev_group_quantified = False
        i += 1


def compile_regex_matcher(field, value, line, col):
    """编译期校验正则取值并构建 Regex 匹配器。"""
    check_pattern_safety(value, line, col)
    try:
        return Regex(field, value)
    except re.error as exc:
        raise RuleCompileError(
            f"非法正则 {value!r}: {exc}", line, col) from exc


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self):
        tok = self.peek()
        if tok is not None:
            self.pos += 1
        return tok

    def expect(self, kind, what):
        tok = self.next()
        if tok is not None and tok.kind == kind:
            return tok
        if tok is not None:
            raise RuleCompileError(f"{what}，得到 {tok.kind}", tok.line, tok.col)
        if self.tokens:
            last = self.tokens[-1]
            raise RuleCompileError(
                f"{what}，已到文末", last.line, last.col + len(str(last.value)))
        raise RuleCompileError(f"{what}，已到文末", 1, 1)

    def expect_newline(self, what="语句后应为换行"):
        tok = self.peek()
        if tok is None:
            return
        if tok.kind != "NL":
            raise RuleCompileError(f"{what}", tok.line, tok.col)
        self.next()

    def parse_program(self):
        specs = []
        seen = set()
        while True:
            tok = self.peek()
            if tok is None:
                break
            if tok.kind == "NL":
                self.next()
                continue
            if tok.kind != "WORD" or tok.value != "flag":
                raise RuleCompileError(
                    f"无法识别的行首记号 {tok.value!r}", tok.line, tok.col)
            specs.append(self.parse_flag(seen))
        return specs

    def parse_flag(self, seen):
        kw = self.next()
        name_tok = self.expect("WORD", "flag 后应有开关名")
        self.expect_newline("flag 行上有多余内容")
        if name_tok.value in seen:
            raise RuleCompileError(
                f"重复定义开关 {name_tok.value!r}", kw.line, kw.col)
        seen.add(name_tok.value)
        spec = FlagSpec(name_tok.value, kw.line)

        while True:
            tok = self.peek()
            if tok is None or (tok.kind == "WORD" and tok.value == "flag"):
                return spec
            if tok.kind == "NL":
                self.next()
                continue
            if tok.kind != "WORD" or tok.value not in ("when", "default"):
                raise RuleCompileError(
                    f"开关体内无法识别的语句 {tok.value!r}", tok.line, tok.col)
            self.next()
            if tok.value == "when":
                expr = self.parse_expr()
                self.expect("ARROW", "when 表达式后应有 ->")
                spec.rules.append(
                    Rule(len(spec.rules) + 1, expr,
                         self.parse_onoff().value == "on", tok.line))
                self.expect_newline("when 行上有多余内容")
            else:
                if spec.has_default:
                    raise RuleCompileError(
                        "default 重复", tok.line, tok.col)
                spec.default = self.parse_onoff().value == "on"
                spec.has_default = True
                self.expect_newline("default 行上有多余内容")

    def parse_onoff(self):
        tok = self.expect("WORD", "应为 on 或 off")
        if tok.value not in ("on", "off"):
            raise RuleCompileError(
                f"决策只能是 on 或 off，得到 {tok.value!r}", tok.line, tok.col)
        return tok

    def parse_expr(self):
        tok = self.expect("WORD", "应为表达式")
        if tok.value in COMBINATOR_TABLE:
            return self.parse_combinator(tok)
        return self.parse_clause(tok)

    def parse_combinator(self, kw):
        combinator = COMBINATOR_TABLE[kw.value]
        min_args, max_args = COMBINATOR_ARITY[kw.value]
        self.expect("LPAREN", f"{kw.value}( 后应有表达式")
        children = [self.parse_expr()]
        while True:
            tok = self.peek()
            if tok is None or tok.kind != "COMMA":
                break
            self.next()
            children.append(self.parse_expr())
        self.expect("RPAREN", f"{kw.value}(...) 缺少右括号")
        if len(children) < min_args:
            raise RuleCompileError(
                f"{kw.value} 至少需要 {min_args} 个参数", kw.line, kw.col)
        if max_args is not None and len(children) > max_args:
            raise RuleCompileError(
                f"{kw.value} 只接受 {max_args} 个参数", kw.line, kw.col)
        return combinator(children)

    def parse_clause(self, field_tok):
        op_tok = self.expect("WORD", f"字段 {field_tok.value!r} 后应有操作符")
        if op_tok.value not in OP_TABLE:
            raise RuleCompileError(
                f"未知的匹配操作符 {op_tok.value!r}", op_tok.line, op_tok.col)
        if op_tok.value == "in":
            values = self.parse_value_list()
            return InSet(field_tok.value, values)
        value_tok = self.parse_value_token()
        value = self.token_value(value_tok)
        if op_tok.value == "regex":
            if value_tok.kind != "STR":
                raise RuleCompileError(
                    f"regex 需要带引号的正则模式，得到 {value_tok.value!r}",
                    value_tok.line, value_tok.col)
            return compile_regex_matcher(
                field_tok.value, value, value_tok.line, value_tok.col)
        if op_tok.value in NUMERIC_OPS and value_tok.kind != "NUM":
            raise RuleCompileError(
                f"{op_tok.value} 需要数字取值，得到 {value_tok.value!r}",
                value_tok.line, value_tok.col)
        builder = OP_TABLE[op_tok.value]
        return builder(field_tok.value, value)

    def parse_value_list(self):
        self.expect("LBRACK", "in 后应有 [")
        values = []
        while True:
            tok = self.parse_value_token()
            values.append(self.token_value(tok))
            sep = self.peek()
            if sep is not None and sep.kind == "COMMA":
                self.next()
                continue
            break
        self.expect("RBRACK", "in 列表缺少 ]")
        return values

    def parse_value_token(self):
        tok = self.next()
        if tok is None or tok.kind not in ("STR", "NUM", "WORD"):
            at = (tok.line, tok.col) if tok else (1, 1)
            raise RuleCompileError("缺少取值", *at)
        if tok.kind == "WORD" and tok.value not in ("true", "false"):
            # 裸词按字符串取值处理
            return tok._replace(kind="STR")
        return tok

    @staticmethod
    def token_value(tok):
        if tok.kind == "NUM":
            return float(tok.value) if "." in tok.value else int(tok.value)
        if tok.kind == "WORD":
            return tok.value == "true"
        return tok.value


def compile_rules(text):
    """编译规则文本。任何非法之处抛带位置的 RuleCompileError。"""
    specs = _Parser(tokenize(text)).parse_program()
    return FlagEngine(specs)
