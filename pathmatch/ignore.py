""".gitignore 风格的忽略规则。

IgnoreRules 解析一个 .gitignore 文件的内容，matched 把若干层
IgnoreRules（rule_stack，按根到深排序）逐层评估，给出路径的
忽略状态与决定性规则。
"""

import re


class Rule:
    """一条解析后的忽略规则。"""

    __slots__ = ("text", "negated", "dir_only", "anchored", "base", "lineno", "regex")

    def __init__(self, text, negated, dir_only, anchored, base, lineno, regex):
        self.text = text            # 有效规则文本（去掉未转义尾随空格后）
        self.negated = negated      # 以 ! 开头
        self.dir_only = dir_only    # 以 / 结尾，仅匹配目录
        self.anchored = anchored    # 含 /，锚定到 base
        self.base = base            # 所属规则文件的目录前缀
        self.lineno = lineno        # 在规则文件中的行号
        self.regex = regex          # 编译后的匹配正则（对 base 相对路径 fullmatch）

    def __repr__(self):
        return "Rule({!r}, base={!r}, line={})".format(self.text, self.base, self.lineno)


def _strip_trailing_spaces(line):
    """去掉未转义的尾随空格；\\ 开头的空格（"\\ "）保留。"""
    end = len(line)
    while end > 0 and line[end - 1] == " " and (end < 2 or line[end - 2] != "\\"):
        end -= 1
    return line[:end]


def _translate_class(seg, i):
    """翻译 seg[i] 起的 [...] 字符类，返回 (正则片段, 下一个下标)。"""
    j = i + 1
    if j < len(seg) and seg[j] == "!":
        j += 1
    if j < len(seg) and seg[j] == "]":
        j += 1
    while j < len(seg) and seg[j] != "]":
        j += 1
    if j >= len(seg):  # 未闭合，按字面 [
        return re.escape("["), i + 1
    inner = seg[i + 1:j]
    if inner.startswith("!"):
        inner = "^" + inner[1:]
    inner = inner.replace("\\", "\\\\")
    return "[" + inner + "]", j + 1


def _segment_regex(seg):
    """单个 pattern 段 -> 正则：* 不跨段，? 单字符，[...] 字符类，\\ 转义下一字符。"""
    out = []
    i = 0
    while i < len(seg):
        ch = seg[i]
        if ch == "\\" and i + 1 < len(seg):
            out.append(re.escape(seg[i + 1]))
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            piece, i = _translate_class(seg, i)
            out.append(piece)
            continue
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out)


def _compile_anchored(pattern):
    """锚定 pattern（可含多段）-> 正则，处理整段的 **。"""
    parts = []
    pending_sep = False
    segs = pattern.split("/")
    for i, seg in enumerate(segs):
        last = i == len(segs) - 1
        if seg == "**":
            if pending_sep:
                parts.append("/")
            if last:
                parts.append(".*")            # 尾部 /**：其下全部
            else:
                parts.append("(?:[^/]+/)*")   # **/：零或多层目录
            pending_sep = False               # **/ 已自带分隔
        else:
            if pending_sep:
                parts.append("/")
            parts.append(_segment_regex(seg))
            pending_sep = True
    return "".join(parts)


def _parse_line(line, base, lineno):
    """解析一行规则文本，注释/空行/无效行返回 None。"""
    line = _strip_trailing_spaces(line)
    if not line or line.startswith("#"):
        return None
    negated = line.startswith("!")
    if negated:
        line = line[1:]
    dir_only = line.endswith("/")
    if dir_only:
        line = line[:-1]
    anchored = "/" in line
    if line.startswith("/"):
        line = line[1:]
    if not line:
        return None
    if anchored:
        regex = _compile_anchored(line)
    else:
        # 不含 /：匹配 base 下任意层级的同名路径
        regex = "(?:[^/]+/)*" + _segment_regex(line)
    return Rule(line, negated, dir_only, anchored, base, lineno, regex)


class IgnoreRules:
    """一个 .gitignore 文件解析出的规则集。

    text: 文件内容；base: 该文件所在目录相对根的前缀（根处为 ""）。
    """

    def __init__(self, text, base=""):
        self.base = base.strip("/")
        self.rules = []
        for lineno, raw in enumerate(text.splitlines(), 1):
            rule = _parse_line(raw, self.base, lineno)
            if rule is not None:
                self.rules.append(rule)

    def _relative(self, relpath):
        """relpath 相对本规则集 base 的子路径；不在 base 下返回 None。"""
        if not self.base:
            return relpath
        prefix = self.base + "/"
        if relpath.startswith(prefix):
            return relpath[len(prefix):]
        return None

    def _decide(self, relpath, is_dir):
        """本层规则对 relpath 的判定：后出现的规则优先，无命中返回 None。"""
        sub = self._relative(relpath)
        if not sub:
            return None
        for rule in reversed(self.rules):
            if rule.dir_only and not is_dir:
                continue
            if re.fullmatch(rule.regex, sub) is not None:
                return rule
        return None


def matched(relpath, is_dir, rule_stack):
    """逐层评估 relpath 的忽略状态。

    rule_stack 按根到深的顺序给出各层 IgnoreRules；深层优先，
    同一层内后出现的规则优先。父目录被忽略时子路径不可恢复
    （与 git 一致）。返回 ('ignored'|'allowed', 决定规则)，
    无命中为 ('allowed', None)。
    """
    relpath = relpath.strip("/")
    if not relpath:
        return ("allowed", None)
    parent, sep, _ = relpath.rpartition("/")
    if sep:
        status, rule = matched(parent, True, rule_stack)
        if status == "ignored":
            return ("ignored", rule)
    for rules in reversed(list(rule_stack)):
        rule = rules._decide(relpath, is_dir)
        if rule is not None:
            return ("allowed" if rule.negated else "ignored", rule)
    return ("allowed", None)
