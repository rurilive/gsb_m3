"""gitignore 风格的忽略规则。

IgnoreRules 解析一段 .gitignore 文本；matched 按 git 的优先级
（深层规则文件优先、同文件内后写优先、路径本身先于其父目录）
对相对根的路径给出 ignored/allowed 判定。
"""

import re

_ESCAPE_CHARS = "#! "


class Rule:
    """一条解析后的忽略规则。"""

    __slots__ = ("line", "pattern", "negated", "dir_only", "base", "_regex")

    def __init__(self, line, pattern, negated, dir_only, base, regex):
        self.line = line  # 原始行文本
        self.pattern = pattern  # 去掉 ! 和尾 / 后的模式
        self.negated = negated
        self.dir_only = dir_only
        self.base = base
        self._regex = regex

    def __repr__(self):
        where = self.base or "."
        return f"Rule({self.line!r}, base={where!r})"

    def matches(self, relpath, is_dir):
        """relpath 相对仓库根；判断本规则是否命中。"""
        if self.dir_only and not is_dir:
            return False
        if self.base:
            prefix = self.base + "/"
            if not relpath.startswith(prefix):
                return False
            relpath = relpath[len(prefix):]
        return self._regex.fullmatch(relpath) is not None


def _parse_rule(raw_line, base):
    """解析一行；注释与空行返回 None。"""
    chars = []
    escaped = []
    i = 0
    while i < len(raw_line):
        ch = raw_line[i]
        if ch == "\\" and i + 1 < len(raw_line) and raw_line[i + 1] in _ESCAPE_CHARS:
            chars.append(raw_line[i + 1])
            escaped.append(True)
            i += 2
        else:
            chars.append(ch)
            escaped.append(False)
            i += 1
    while chars and chars[-1] == " " and not escaped[-1]:
        chars.pop()
        escaped.pop()
    if not chars:
        return None
    if chars[0] == "#" and not escaped[0]:
        return None
    negated = False
    if chars[0] == "!" and not escaped[0]:
        negated = True
        del chars[0]
        del escaped[0]
    pattern = "".join(chars)
    dir_only = pattern.endswith("/")
    if dir_only:
        pattern = pattern[:-1]
    anchored = "/" in pattern
    if pattern.startswith("/"):
        pattern = pattern[1:]
    if not pattern:
        return None
    return Rule(raw_line, pattern, negated, dir_only, base, _compile(pattern, anchored))


def _segment_regex(seg):
    """单段翻译：* 不跨段，? 匹配单字符，[...] 为字符类。"""
    out = []
    i = 0
    while i < len(seg):
        ch = seg[i]
        if ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            j = i + 1
            if j < len(seg) and seg[j] == "!":
                j += 1
            if j < len(seg) and seg[j] == "]":
                j += 1
            while j < len(seg) and seg[j] != "]":
                j += 1
            if j >= len(seg):
                out.append(re.escape(ch))
                i += 1
            else:
                inner = seg[i + 1:j]
                if inner.startswith("!"):
                    inner = "^" + inner[1:]
                out.append("[" + inner.replace("\\", "\\\\") + "]")
                i = j + 1
        else:
            out.append(re.escape(ch))
            i += 1
    return "".join(out)


def _compile(pattern, anchored):
    """把模式翻成正则；** 仅作为完整段时跨段。"""
    segs = pattern.split("/")
    regex = ""
    for i, seg in enumerate(segs):
        if seg == "**":
            if i == len(segs) - 1:
                # 结尾 /**：其下全部；** 单独成模式时匹配一切
                regex += ".+" if not regex else "/.+"
            else:
                # 开头 **/ 或中间 /**/：零或多层目录
                regex += "(?:[^/]+/)*" if not regex else "/(?:[^/]+/)*"
            continue
        seg_re = _segment_regex(seg)
        if not regex:
            regex = seg_re
        elif regex.endswith(")*"):
            regex += seg_re
        else:
            regex += "/" + seg_re
    if not anchored:
        # 不含 / 的模式匹配任意层级的同名路径
        regex = "(?:[^/]+/)*" + regex
    return re.compile(regex)


class IgnoreRules:
    """一个 .gitignore 文件的规则集合。

    text 为文件内容；base 为该文件所在目录相对根的前缀（根处为空串）。
    """

    def __init__(self, text, base=""):
        self.base = base.strip("/")
        self.rules = []
        for raw in text.splitlines():
            rule = _parse_rule(raw, self.base)
            if rule is not None:
                self.rules.append(rule)

    def __len__(self):
        return len(self.rules)


def matched(relpath, is_dir, rule_stack):
    """逐层评估 rule_stack（按根到深排列），深层规则优先。

    返回 ('ignored'|'allowed', 决定规则)；无命中返回 ('allowed', None)。
    路径本身无命中时，按 git 语义继续检查各级父目录（视为目录），
    因此被忽略目录下的所有内容同样判定为 ignored。
    """
    path = relpath.strip("/")
    dir_flag = is_dir
    while True:
        for rules in reversed(list(rule_stack)):
            for rule in reversed(rules.rules):
                if rule.matches(path, dir_flag):
                    return ("allowed" if rule.negated else "ignored", rule)
        if "/" not in path:
            return ("allowed", None)
        path = path.rsplit("/", 1)[0]
        dir_flag = True
