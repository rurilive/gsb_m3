"""gitignore 风格的忽略规则。

IgnoreRules 解析一段 .gitignore 文本；matched 在一叠嵌套规则上
（浅层在前、深层在后）判定某个相对根目录的路径是 ignored 还是 allowed。
"""

import re


class Rule:
    """一条解析后的规则。"""

    __slots__ = (
        "pattern",
        "negated",
        "dir_only",
        "anchored",
        "base",
        "lineno",
        "source",
        "_regex",
    )

    def __init__(self, pattern, negated, dir_only, anchored, base, lineno, source):
        self.pattern = pattern
        self.negated = negated
        self.dir_only = dir_only
        self.anchored = anchored
        self.base = base
        self.lineno = lineno
        self.source = source
        self._regex = re.compile(_translate(pattern))

    def matches(self, local_path, is_dir):
        """local_path 为相对本规则 base 的路径。"""
        if self.dir_only and not is_dir:
            return False
        if self.anchored:
            return self._regex.fullmatch(local_path) is not None
        name = local_path.rsplit("/", 1)[-1]
        return self._regex.fullmatch(name) is not None

    def __repr__(self):
        return "Rule(%r, base=%r, line=%d)" % (self.source, self.base, self.lineno)


def _segment_regex(segment):
    """单个 pattern 段 -> 正则：* 不跨段，? 单字符，[...] 字符类。"""
    out = []
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            j = i + 1
            if j < n and segment[j] in "!^":
                j += 1
            if j < n and segment[j] == "]":
                j += 1
            while j < n and segment[j] != "]":
                j += 1
            if j >= n:
                out.append(re.escape(ch))
            else:
                stuff = segment[i + 1 : j]
                if stuff.startswith("!"):
                    stuff = "^" + stuff[1:]
                elif stuff.startswith("^"):
                    stuff = "\\" + stuff
                out.append("[" + stuff.replace("\\", "\\\\") + "]")
                i = j
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def _translate(pattern):
    """整个 pattern -> 正则。** 作为独立段时跨段匹配。"""
    segs = pattern.split("/")
    n = len(segs)
    out = []
    for idx, seg in enumerate(segs):
        if seg == "**":
            if n == 1:
                out.append(".*")
            elif idx == 0:
                out.append("(?:[^/]+/)*")
            elif idx == n - 1:
                out.append("/.*")
            else:
                out.append("(?:/[^/]+)*")
            continue
        if idx > 0 and segs[idx - 1] != "**":
            out.append("/")
        elif idx > 0 and idx - 1 != 0:
            out.append("/")
        out.append(_segment_regex(seg))
    return "".join(out)


def _strip_trailing_spaces(line):
    """去掉行尾未被反斜杠转义的空白。"""
    while line and line[-1] in " \t":
        backslashes = 0
        i = len(line) - 2
        while i >= 0 and line[i] == "\\":
            backslashes += 1
            i -= 1
        if backslashes % 2 == 1:
            break
        line = line[:-1]
    return line


def _unescape(line):
    return re.sub(r"\\([#! \\])", r"\1", line)


def _parse_line(line, base, lineno):
    """解析一行，返回 Rule；注释与空行返回 None。"""
    line = _strip_trailing_spaces(line)
    if not line or line.startswith("#"):
        return None
    negated = line.startswith("!")
    if negated:
        line = line[1:]
    line = _unescape(line)
    dir_only = line.endswith("/")
    if dir_only:
        line = line.rstrip("/")
    if not line:
        return None
    anchored = line.startswith("/")
    if anchored:
        line = line.lstrip("/")
    if "/" in line:
        anchored = True
    if not line:
        return None
    return Rule(line, negated, dir_only, anchored, base, lineno, line)


class IgnoreRules:
    """一个 .gitignore 文件：text 为内容，base 为它所在目录相对根的前缀。"""

    def __init__(self, text, base=""):
        self.base = base.strip("/")
        self.rules = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            rule = _parse_line(raw, self.base, lineno)
            if rule is not None:
                rule.source = raw
                self.rules.append(rule)

    def _decide(self, relpath, is_dir):
        """只在本文件内判定：后面的规则优先。无命中返回 None。"""
        if self.base:
            if not relpath.startswith(self.base + "/"):
                return None
            local = relpath[len(self.base) + 1 :]
        else:
            local = relpath
        for rule in reversed(self.rules):
            if rule.matches(local, is_dir):
                return rule
        return None


def _decide(relpath, is_dir, rule_stack):
    """深层规则文件优先；同文件内后面的规则优先。"""
    for rules in reversed(list(rule_stack)):
        rule = rules._decide(relpath, is_dir)
        if rule is not None:
            return ("allowed" if rule.negated else "ignored"), rule
    return None


def matched(relpath, is_dir, rule_stack):
    """判定 relpath（相对根）在 rule_stack（浅->深）下的结果。

    返回 ('ignored'|'allowed', 决定规则)；无命中为 ('allowed', None)。
    若任一祖先目录被忽略，则路径直接 ignored（与 git 一致：
    被排除目录下的内容无法通过否定规则重新包含）。
    """
    relpath = relpath.strip("/")
    parts = relpath.split("/")
    for depth in range(1, len(parts)):
        prefix = "/".join(parts[:depth])
        result = _decide(prefix, True, rule_stack)
        if result is not None and result[0] == "ignored":
            return result
    result = _decide(relpath, is_dir, rule_stack)
    if result is None:
        return ("allowed", None)
    return result
