""".gitignore 风格的忽略规则。

IgnoreRules 解析一份 .gitignore 文本（配合所在目录的相对前缀 base），
matched 在规则栈（根到深）上评估某个相对路径，返回忽略判定与决定规则。
"""

import re

from .match import _segment_regex


class Rule:
    """一条解析后的忽略规则。"""

    __slots__ = ("raw", "pattern", "negated", "dir_only", "anchored", "base", "lineno", "_regex")

    def __init__(self, raw, pattern, negated, dir_only, anchored, base, lineno):
        self.raw = raw
        self.pattern = pattern
        self.negated = negated
        self.dir_only = dir_only
        self.anchored = anchored
        self.base = base
        self.lineno = lineno
        self._regex = _translate_anchored(pattern) if anchored else _segment_regex(pattern)

    def matches(self, rel, is_dir):
        """rel 为相对 base 的路径；判断本规则是否命中。"""
        if self.dir_only and not is_dir:
            return False
        if self.anchored:
            return re.fullmatch(self._regex, rel) is not None
        basename = rel.rsplit("/", 1)[-1]
        return re.fullmatch(self._regex, basename) is not None

    def __repr__(self):
        prefix = "!" if self.negated else ""
        suffix = "/" if self.dir_only else ""
        return f"Rule({prefix}{self.pattern}{suffix} @ {self.base or '.'}:{self.lineno})"


def _translate_anchored(pattern):
    """锚定模式转正则：* / ? 不跨段，** 跨段。"""
    segs = pattern.split("/")
    n = len(segs)
    out = []
    for i, seg in enumerate(segs):
        if seg == "**":
            if n == 1:
                out.append(".*")
            elif i == n - 1:
                out.append("/.*")
            elif i == 0:
                out.append("(?:[^/]+/)*")
            else:
                out.append("/(?:[^/]+/)*")
        else:
            if i > 0 and segs[i - 1] != "**":
                out.append("/")
            out.append(_segment_regex(seg))
    return "".join(out)


def _parse_line(line):
    """解析一行，返回 (pattern, negated, dir_only, anchored)；注释/空行返回 None。"""
    line = re.sub(r"(?<!\\) +$", "", line)
    if not line or line.startswith("#"):
        return None
    negated = line.startswith("!")
    if negated:
        line = line[1:]
    dir_only = line.endswith("/")
    if dir_only:
        line = line.rstrip("/")
    for esc, ch in (("\\#", "#"), ("\\!", "!"), ("\\ ", " "), ("\\\\", "\\")):
        line = line.replace(esc, ch)
    if not line:
        return None
    if line.startswith("/"):
        anchored = True
        line = line.lstrip("/")
    else:
        anchored = "/" in line
    if not line:
        return None
    return line, negated, dir_only, anchored


class IgnoreRules:
    """一份 .gitignore 的规则集；base 是该文件所在目录相对根的前缀。"""

    def __init__(self, text, base=""):
        self.base = base.strip("/")
        self.rules = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            parsed = _parse_line(raw)
            if parsed is None:
                continue
            pattern, negated, dir_only, anchored = parsed
            self.rules.append(
                Rule(raw.strip(), pattern, negated, dir_only, anchored, self.base, lineno)
            )

    def decide(self, relpath, is_dir):
        """本文件范围内的决定规则（后写优先）；不适用或无命中返回 None。"""
        if self.base:
            if not relpath.startswith(self.base + "/"):
                return None
            rel = relpath[len(self.base) + 1:]
        else:
            rel = relpath
        hit = None
        for rule in self.rules:
            if rule.matches(rel, is_dir):
                hit = rule
        return hit


def matched(relpath, is_dir, rule_stack):
    """逐层评估 relpath，返回 ('ignored'|'allowed', 决定规则)。

    rule_stack 为 IgnoreRules 组成的序列，按根到深排序，深者优先。
    自根向深走查路径的每一层前缀：某层被忽略即终止（父目录被排除时
    无法重新包含其下路径）；同层内深层规则文件优先，文件内后写优先。
    无任何命中返回 ('allowed', None)。
    """
    parts = relpath.strip("/").split("/")
    for depth in range(1, len(parts) + 1):
        prefix = "/".join(parts[:depth])
        prefix_is_dir = True if depth < len(parts) else is_dir
        for rules in reversed(list(rule_stack)):
            rule = rules.decide(prefix, prefix_is_dir)
            if rule is None:
                continue
            if depth < len(parts):
                if not rule.negated:
                    return ("ignored", rule)
                break
            return ("allowed" if rule.negated else "ignored", rule)
    return ("allowed", None)
