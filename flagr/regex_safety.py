"""正则安全检查：编译期拒绝可能引发灾难性回溯的模式。

运营后台配置的 pattern 不可信，不能等线上打满 CPU 才发现。这里在编译
（re.compile）之前做静态分析，只保守地拒绝确有指数级回溯风险的形态：

1. 嵌套的回溯型重复，内层无固定上限（如 ``(a+)+``、``(\\d+)*``）或
   内层可空而外层无界（如 ``(a?){10,}``）——二者都能让同一段文本在
   迭代边界上分裂出指数条路径。固定次数（``\\d{3}``）、有界且至少
   消费一个字符（``(x{2,3}){2,}``、``(ab?)*`` 中 b? 前面有固定的 a）
   等按整块消费的形态不拒；占有量词 / 原子组切断回溯，也不拒。
2. 无界重复体内部存在可空分支（公共前缀提升后的空分支也算），如
   ``(a|aa)*`` 等价 ``a(|a)*``。

只走 re 自带的解析器 AST，不执行任何匹配，检查本身不会触发 DoS；
无法解析的模式按非法正则处理。
"""

from re import _parser, _constants as C

try:
    _POSSESSIVE = C.POSSESSIVE_REPEAT
except AttributeError:  # pragma: no cover - 旧版本兜底
    _POSSESSIVE = -1

_BACKTRACK_REPEATS = (C.MAX_REPEAT, C.MIN_REPEAT)

# 内部不含子表达式、直接按原子处理的操作码
_ATOMIC_NO_CHILDREN = frozenset((
    C.LITERAL, C.NOT_LITERAL, C.IN, C.ANY, C.ANY_ALL, C.CATEGORY,
    C.AT, C.GROUPREF, C.GROUPREF_IGNORE,
))


class RegexSafetyError(ValueError):
    """模式包含灾难性回溯风险，消息供编译期转 RuleCompileError。"""


def check_pattern(pattern):
    """检查正则文本；有风险或非法时抛 RegexSafetyError。"""
    try:
        tree = _parser.parse(pattern, 0)
    except Exception as exc:  # re.error 等：非法模式一律编译期拒掉
        raise RegexSafetyError(f"非法正则 {pattern!r}：{exc}") from None
    _walk_sequence(tree, ())


def _repeat_unbounded(av):
    return av[1] is C.MAXREPEAT


def _contains_unbounded_repeat(seq):
    """序列中（占有量词 / 原子组 / 断言屏障之外）是否含无界回溯重复。"""
    for op, av in seq:
        if op in _BACKTRACK_REPEATS:
            if _repeat_unbounded(av):
                return True
            if _contains_unbounded_repeat(av[2]):
                return True
        elif op == _POSSESSIVE:
            continue  # 占有量词切断回溯，体内嵌套不可见
        elif op == C.ATOMIC_GROUP:
            continue
        elif op in (C.ASSERT, C.ASSERT_NOT):
            continue
        elif op == C.SUBPATTERN:
            if _contains_unbounded_repeat(av[-1]):
                return True
        elif op == C.BRANCH:
            if any(_contains_unbounded_repeat(alt) for alt in av[1]):
                return True
        elif op == C.GROUPREF_EXISTS:
            _, _, yes, no = av
            if _contains_unbounded_repeat(yes):
                return True
            if no and _contains_unbounded_repeat(no):
                return True
    return False


def _walk_sequence(seq, stack):
    """遍历一串子表达式。

    stack 为当前所处的“回溯型无界重复”的 av 栈：进入普通（非占有）
    无界重复体时压栈；原子组 / 断言 / 占有重复切断传播，重新置空。
    """
    for op, av in seq:
        if op in _ATOMIC_NO_CHILDREN:
            continue
        if op in _BACKTRACK_REPEATS:
            if _repeat_unbounded(av):
                body_nullable = _sequence_nullable(av[2])
                if body_nullable or _contains_unbounded_repeat(av[2]):
                    raise RegexSafetyError(
                        "正则存在嵌套可变宽重复或可空重复体（如 (a+)+、"
                        "(a?)*），可能引发灾难性回溯")
                _check_no_nullable_branch(av[2])
                _walk_sequence(av[2], stack + (av,))
            else:
                _walk_sequence(av[2], stack)
        elif op == _POSSESSIVE:
            # 占有量词不回溯，体内部再危险也无法跨迭代分裂
            _walk_sequence(av[2], ())
        elif op == C.SUBPATTERN:
            _walk_sequence(av[-1], stack)
        elif op == C.ATOMIC_GROUP:
            _walk_sequence(av, ())
        elif op in (C.ASSERT, C.ASSERT_NOT):
            _walk_sequence(av[-1], ())
        elif op == C.BRANCH:
            _walk_branch(av, stack)
        elif op == C.GROUPREF_EXISTS:
            # (?(id)yes|no)：两个分支都要查
            _, _, yes, no = av
            _walk_sequence(yes, stack)
            if no:
                _walk_sequence(no, stack)
        # MARK/INFO/JUMP 等是结构标记，无子表达式


def _walk_branch(av, stack):
    for alt in av[1]:
        _walk_sequence(alt, stack)


def _sequence_nullable(seq):
    """一串子表达式在回溯语义下是否整体可空。

    与通用首字符分析的区别：占有量词 / 原子组按“必然消费一次”处理
    （``a*+`` 永不回退，失败即失败），因此 ``(a*+)*`` 的体不空。
    """
    for op, av in seq:
        if not _atom_nullable(op, av):
            return False
    return True


def _atom_nullable(op, av):
    if op in _BACKTRACK_REPEATS:
        return av[0] == 0 or _sequence_nullable(av[2])
    if op == _POSSESSIVE:
        # 占有重复可空的情形（a*+）一旦匹配就锁死，不产生跨迭代分裂
        return False
    if op == C.SUBPATTERN:
        return _sequence_nullable(av[-1])
    if op == C.BRANCH:
        return any(_sequence_nullable(alt) for alt in av[1])
    if op == C.ATOMIC_GROUP:
        return _sequence_nullable(av)
    if op in (C.ASSERT, C.ASSERT_NOT, C.AT):
        return True
    nullable, _ = _atom_first(op, av)
    return nullable


def _check_no_nullable_branch(seq):
    """无界重复体内部（屏障外）不得含可空分支。

    解析器的公共前缀提升会把 ``(a|aa)*`` 改写成 ``a(|a)*`` 形态，
    空分支不在顶层，需要按结构深入查找。
    """
    for op, av in seq:
        if op == C.BRANCH:
            for alt in av[1]:
                nullable, _ = _first_chars(alt)
                if nullable:
                    raise RegexSafetyError(
                        "正则的重复体内存在可空分支（如 (a|aa)*），"
                        "可能引发灾难性回溯")
            for alt in av[1]:
                _check_no_nullable_branch(alt)
        elif op in _BACKTRACK_REPEATS:
            _check_no_nullable_branch(av[2])
        elif op == C.SUBPATTERN:
            _check_no_nullable_branch(av[-1])
        # 占有量词 / 原子组 / 断言内的分支无法跨迭代分裂，不查


# --- 首字符探测：用一组探针字符直接问每个原子“你能否以它开头” ---

_PROBE_CHARS = "".join(chr(cp) for cp in (
    list(range(0x00, 0x80))
    + [0xA0, 0xA9, 0xC0, 0xD8, 0xDF, 0xE0, 0xF8, 0xFF]
    + [0x100, 0x152, 0x370, 0x400, 0x4E00, 0x4E2D, 0x3000, 0x3042,
       0x1F600, 0x2014, 0x2028]
))

_CATEGORY_TESTS = {
    C.CATEGORY_DIGIT: str.isdigit,
    C.CATEGORY_NOT_DIGIT: lambda c: not c.isdigit(),
    C.CATEGORY_SPACE: str.isspace,
    C.CATEGORY_NOT_SPACE: lambda c: not c.isspace(),
    C.CATEGORY_WORD: lambda c: c.isalnum() or c == "_",
    C.CATEGORY_NOT_WORD: lambda c: not (c.isalnum() or c == "_"),
    C.CATEGORY_LINEBREAK: lambda c: c in "\n\r\v\f",
    C.CATEGORY_NOT_LINEBREAK: lambda c: c not in "\n\r\v\f",
}


def _first_chars(seq):
    """返回 (是否可空, 可能首字符集合)。集合为 None 表示无法精确刻画。"""
    union = set()
    for op, av in seq:
        nullable, chars = _atom_first(op, av)
        if chars is None:
            return nullable, None
        union |= chars
        if not nullable:
            return False, union
    return True, union


def _atom_first(op, av):
    if op == C.LITERAL:
        return False, {chr(av)}
    if op == C.NOT_LITERAL:
        return False, {c for c in _PROBE_CHARS if ord(c) != av}
    if op == C.ANY:
        return False, {c for c in _PROBE_CHARS if c != "\n"}
    if op == C.ANY_ALL:
        return False, set(_PROBE_CHARS)
    if op == C.IN:
        return False, _in_class_first(av)
    if op == C.CATEGORY:
        test = _CATEGORY_TESTS.get(av)
        if test is None:  # LOCALE/UNICODE 专有类别：无法精确刻画
            return False, None
        return False, {c for c in _PROBE_CHARS if test(c)}
    if op in _BACKTRACK_REPEATS or op == _POSSESSIVE:
        nullable, chars = _first_chars(av[2])
        return (nullable or av[0] == 0), chars
    if op == C.SUBPATTERN:
        return _first_chars(av[-1])
    if op == C.BRANCH:
        nullable = False
        union = set()
        for alt in av[1]:
            n, chars = _first_chars(alt)
            nullable = nullable or n
            if chars is None:
                return nullable, None
            union |= chars
        return nullable, union
    if op == C.ATOMIC_GROUP:
        return _first_chars(av)
    if op in (C.ASSERT, C.ASSERT_NOT, C.AT):
        # 断言与锚点不消耗字符，序列中视为可空且不带首字符
        return True, set()
    # GROUPREF / GROUPREF_EXISTS 等引用历史文本，首字符不可静态确定
    return False, None


def _in_class_first(members):
    negated = False
    out = set()
    for mop, mav in members:
        if mop == C.LITERAL:
            out.add(chr(mav))
        elif mop == C.NOT_LITERAL:
            negated = True
            out.update(c for c in _PROBE_CHARS if ord(c) != mav)
        elif mop == C.RANGE:
            lo, hi = mav
            out.update(c for c in _PROBE_CHARS if lo <= ord(c) <= hi)
        elif mop == C.CATEGORY:
            test = _CATEGORY_TESTS.get(mav)
            if test is None:
                return None
            out.update(c for c in _PROBE_CHARS if test(c))
        elif mop == C.IN:
            out.update(_in_class_first(mav))
        elif mop == C.NEGATE:
            negated = not negated
    if negated:
        out = set(_PROBE_CHARS) - out
    return out
