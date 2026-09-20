""".gitignore 风格的忽略规则。

IgnoreRules 解析一份 .gitignore 文本，matched 在嵌套规则栈上
逐层评估某个相对路径，深者优先，返回决定性规则。
"""

import re


def _segment_regex(segment):
    """把单个 pattern 段翻译成正则：* 不跨段，? 单字符，[...] 字符类。"""
    parts = []
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if ch == "*":
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        elif ch == "\\" and i + 1 < n:
            parts.append(re.escape(segment[i + 1]))
            i += 1
        elif ch == "[":
            j = i + 1
            if j < n and segment[j] == "!":
                j += 1
            if j < n and segment[j] == "]":
                j += 1
            while j < n and segment[j] != "]":
                j += 1
            if j >= n:
                parts.append(re.escape("["))
            else:
                inner = segment[i + 1:j]
                if inner.startswith("!"):
                    inner = "^" + inner[1:]
                inner = inner.replace("\\", "\\\\")
                parts.append("[" + inner + "]")
                i = j
        else:
            parts.append(re.escape(ch))
        i += 1
    return "".join(parts)


def _segments_match(p_segs, t_segs):
    """逐段匹配，整段 ** 跨零或多层目录（结尾的 ** 要求至少一层）。"""
    if not p_segs:
        return not t_segs
    head = p_segs[0]
    if head == "**":
        if len(p_segs) == 1:
            return bool(t_segs)
        return any(
            _segments_match(p_segs[1:], t_segs[k:])
            for k in range(len(t_segs) + 1)
        )
    if not t_segs:
        return False
    if re.fullmatch(_segment_regex(head), t_segs[0]) is None:
        return False
    return _segments_match(p_segs[1:], t_segs[1:])


def _strip_trailing_spaces(line):
    """去掉未转义的尾随空格，反斜杠转义的空格保留。"""
    end = len(line)
    while end > 0 and line[end - 1] == " ":
        backslashes = 0
        k = end - 2
        while k >= 0 and line[k] == "\\":
            backslashes += 1
            k -= 1
        if backslashes % 2 == 1:
            break
        end -= 1
    return line[:end]


class Rule:
    """一条解析后的忽略规则。"""

    __slots__ = (
        "text",
        "pattern",
        "negated",
        "dir_only",
        "anchored",
        "base",
        "lineno",
    )

    def __init__(self, text, pattern, negated, dir_only, anchored, base, lineno):
        self.text = text
        self.pattern = pattern
        self.negated = negated
        self.dir_only = dir_only
        self.anchored = anchored
        self.base = base
        self.lineno = lineno

    def matches(self, rel):
        """rel 是相对于 base 的路径。"""
        if self.anchored:
            return _segments_match(self.pattern.split("/"), rel.split("/"))
        name = rel.rsplit("/", 1)[-1]
        return re.fullmatch(_segment_regex(self.pattern), name) is not None

    def __repr__(self):
        location = self.base if self.base else "."
        return f"Rule({self.text!r} @{location}:{self.lineno})"


def _parse_line(raw, base, lineno):
    line = _strip_trailing_spaces(raw)
    if not line or line.startswith("#"):
        return None
    negated = line.startswith("!")
    if negated:
        line = line[1:]
    line = (
        line.replace("\\#", "#")
        .replace("\\!", "!")
        .replace("\\ ", " ")
    )
    dir_only = line.endswith("/")
    if dir_only:
        line = line[:-1]
    leading_slash = line.startswith("/")
    if leading_slash:
        line = line[1:]
    if not line:
        return None
    anchored = leading_slash or "/" in line
    return Rule(raw.strip(), line, negated, dir_only, anchored, base, lineno)


class IgnoreRules:
    """一份 .gitignore 文本解析出的规则集，base 是所在目录相对根的前缀。"""

    def __init__(self, text, base=""):
        self.base = base.strip("/")
        self.rules = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            rule = _parse_line(raw, self.base, lineno)
            if rule is not None:
                self.rules.append(rule)

    def _rel(self, relpath):
        """relpath 相对根；落在 base 之外返回 None，否则返回相对 base 的路径。"""
        relpath = relpath.strip("/")
        if not self.base:
            return relpath
        if relpath == self.base:
            return ""
        prefix = self.base + "/"
        if relpath.startswith(prefix):
            return relpath[len(prefix):]
        return None

    def decide(self, relpath, is_dir):
        """返回本文件内决定该路径的规则（后写者优先），无命中返回 None。"""
        rel = self._rel(relpath)
        if not rel:
            return None
        for rule in reversed(self.rules):
            if rule.dir_only and not is_dir:
                continue
            if rule.matches(rel):
                return rule
        return None


def matched(relpath, is_dir, rule_stack):
    """在规则栈（根到深排列）上逐层评估，深者优先。

    返回 ('ignored'|'allowed', 决定规则)，无命中为 ('allowed', None)。
    """
    for rules in reversed(list(rule_stack)):
        rule = rules.decide(relpath, is_dir)
        if rule is not None:
            return ("allowed" if rule.negated else "ignored", rule)
    return ("allowed", None)
