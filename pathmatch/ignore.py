""".gitignore 风格的忽略规则。

语法（对齐 gitignore 官方语义）：

- 空行与 ``#`` 开头的行为注释；``\\#``、``\\!`` 转义特殊字符，
  行尾未转义的空白被裁掉，``\\ `` 保留字面空格。
- 行首 ``!`` 表示否定（重新纳入），同一层级后出现的规则覆盖先出现的。
- 行尾 ``/`` 表示仅目录生效：目录本身命中，其下内容随目录状态。
- 模式体含 ``/``（去掉行首 ``/`` 后）即相对规则所在目录锚定；
  不含 ``/`` 的模式可匹配任意层级的同名路径。
- ``**`` 跨任意层级：开头 ``/`` 任意层（``**/foo``）、
  结尾 ``/**`` 全部内容（不含目录自身）、中间 ``/**/`` 零或多层。
- 其余沿用段级 glob：``*`` / ``?`` 不跨段，``[abc]`` 为字符类。
"""

import re


def _strip_trailing_spaces(line):
    """裁掉行尾未被反斜杠转义的空格。"""
    end = len(line)
    while end > 0 and line[end - 1] == " ":
        slashes = 0
        i = end - 2
        while i >= 0 and line[i] == "\\":
            slashes += 1
            i -= 1
        if slashes % 2 == 1:
            break
        end -= 1
    return line[:end]


def _unescape(body):
    """去掉用于转义的反斜杠；未参与转义的 ``\\`` 原样保留。"""
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            out.append(body[i + 1])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _segment_regex(segment):
    """把单个 pattern 段翻译成正则。

    ``*``/``?`` 不跨段，``[abc]`` 为字符类，``\\x`` 为字面字符。
    """
    parts = []
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if ch == "\\" and i + 1 < n:
            parts.append(re.escape(segment[i + 1]))
            i += 2
        elif ch == "[":
            j = i + 1
            if j < n and segment[j] in ("!", "^"):
                j += 1
            if j < n and segment[j] == "]":
                j += 1
            while j < n and segment[j] != "]":
                j += 1
            if j >= n:
                parts.append(re.escape("["))
                i += 1
            else:
                cls = segment[i + 1:j]
                if cls[:1] in ("!", "^"):
                    cls = "^" + cls[1:]
                parts.append("[" + cls + "]")
                i = j + 1
        elif ch == "*":
            parts.append("[^/]*")
            i += 1
        elif ch == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(ch))
            i += 1
    return "".join(parts)


def _compile_body(body):
    """编译模式体为锚定到规则基目录的正则（已不含首尾的 ``/``）。

    ``**`` 跨段：开头零或多层、结尾一或多层（不含目录自身）、
    中间零或多层；连续多个 ``**`` 折叠为一个。
    """
    segs = []
    for seg in body.split("/"):
        if seg == "**" and segs and segs[-1] == "**":
            continue
        segs.append(seg)

    # 单独的 ** 匹配全部非空路径。
    if segs == ["**"]:
        return re.compile(r"[^/]+(?:/[^/]+)*\Z")

    # 逐段翻译后再拼装，** 翻译成“层片段”，普通段翻译成字面片段；
    # 层片段自带可选斜杠，普通段之间补固定斜杠。
    tokens = []
    for index, seg in enumerate(segs):
        if seg == "**":
            if index == 0:
                tokens.append(("lead",))          # 零或多层前缀
            elif index == len(segs) - 1:
                tokens.append(("tail",))          # 一或多层内容
            else:
                tokens.append(("mid",))           # 零或多层
        else:
            tokens.append(("seg", _segment_regex(seg)))

    out = []
    for index, token in enumerate(tokens):
        kind = token[0]
        if kind == "lead":
            # 匹配 x/、x/y/ 或空前缀；斜杠随层一起可选。
            out.append("(?:(?:[^/]+/)*)?")
        elif kind == "tail":
            out.append("(?:/[^/]+(?:/[^/]+)*)")
        elif kind == "mid":
            out.append("(?:/[^/]+(?:/[^/]+)*)?")
        else:
            prev = tokens[index - 1][0] if index else None
            if out and prev != "lead":
                out.append("/")
            out.append(token[1])
    return re.compile("".join(out) + r"\Z")


def _body_has_slash(body):
    i = 0
    while i < len(body):
        if body[i] == "/":
            return True
        if body[i] == "\\":
            i += 1
        i += 1
    return False


def _parse_line(line):
    """解析一行规则；返回 :class:`Rule` 或 ``None``（空行/注释）。"""
    line = line.rstrip("\n").rstrip("\r")
    line = _strip_trailing_spaces(line)
    if not line or line[0] == "#":
        return None

    negated = False
    if line[0] == "!":
        negated = True
        line = line[1:]

    dir_only = False
    if line.endswith("/"):
        slashes = 0
        i = len(line) - 2
        while i >= 0 and line[i] == "\\":
            slashes += 1
            i -= 1
        if slashes % 2 == 0:
            dir_only = True
            line = line[:-1]

    anchored = False
    if line.startswith("/"):
        anchored = True
        line = line[1:]
    elif _body_has_slash(line) and line.split("/", 1)[0] != "**":
        anchored = True

    pattern = _unescape(line)
    if not pattern:
        return None

    body_regex = _compile_body(line)
    if anchored:
        # 含 / 的锚定模式只精确命中自己的相对路径，不向子树延伸。
        exact = subtree = body_regex
    elif line.split("/", 1)[0] == "**":
        # 以 ** 开头的模式（**/foo、**/x/**）已允许零或多层前缀。
        exact = subtree = body_regex
    else:
        # 不含 / 的模式可在任意层级匹配同名路径；命中目录后覆盖
        # 其整棵子树（祖先层以子树正则评估）。
        exact = re.compile(r"(?:.*/)?" + body_regex.pattern)
        subtree = re.compile(exact.pattern + r"(?:/.*)?")
    return Rule(pattern, negated, dir_only, exact, subtree)


class Rule:
    """一条解析后的忽略规则。"""

    __slots__ = ("pattern", "negated", "dir_only", "regex",
                 "subtree_regex", "source")

    def __init__(self, pattern, negated, dir_only, regex,
                 subtree_regex=None, source=None):
        self.pattern = pattern
        self.negated = negated
        self.dir_only = dir_only
        self.regex = regex
        self.subtree_regex = subtree_regex if subtree_regex is not None else regex
        self.source = source

    def __repr__(self):
        prefix = "!" if self.negated else ""
        suffix = "/" if self.dir_only else ""
        return f"<Rule {prefix}{self.pattern}{suffix}>"


def _normalize_base(base):
    base = (base or "").replace("\\", "/").strip()
    while base.startswith("./"):
        base = base[2:]
    return base.strip("/")


def _normalize_relpath(relpath):
    path = relpath.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.strip("/")


class IgnoreRules:
    """某一目录下一份 ignore 文件解析出的规则集合。

    ``text`` 为规则文件全文，``base`` 为该文件所在目录相对根的前缀
    （根目录传 ``""``）。
    """

    def __init__(self, text, base=""):
        self.base = _normalize_base(base)
        self.rules = [
            rule
            for rule in (_parse_line(line) for line in text.splitlines())
            if rule is not None
        ]

    def _last_match(self, rel, prefix_is_dir, prefix_level=False):
        """返回本集合中最后一条命中 ``rel`` 的规则，无命中为 ``None``。

        ``prefix_is_dir`` 表示当前层级是不是目录层（最终层取调用方给出的
        类型，祖先层恒为目录）；``prefix_level`` 为祖先层时允许无斜杠
        模式以“命中目录、覆盖子树”的方式命中。
        """
        last = None
        for rule in self.rules:
            if rule.dir_only and not prefix_is_dir:
                continue
            regex = rule.subtree_regex if prefix_level else rule.regex
            if regex.fullmatch(rel):
                last = rule
        return last


def matched(relpath, is_dir, rule_stack):
    """逐层评估 ``relpath`` 的忽略状态。

    ``rule_stack`` 为从根向外、沿途各目录的 :class:`IgnoreRules`
       （顺序不限，内部按 ``base`` 深度排序）。评估沿路径的每一级前缀
    逐层进行：目录在某一层被判忽略后，更深的规则集合不再参与其子路径
       的判定（与 git 的“父目录被排除则不可再包含”一致）；同一层级
    以更深的规则集合优先，同一集合内以后出现的规则优先。

    返回 ``('ignored'|'allowed', 决定规则)``，全程无命中为
    ``('allowed', None)``。
    """
    path = _normalize_relpath(relpath)
    if not path:
        return "allowed", None
    segments = path.split("/")
    levels = len(segments)
    stack = list(enumerate(rule_stack))

    def depth_of(ruleset):
        return ruleset.base.count("/") + 1 if ruleset.base else 0

    def rel_of(ruleset, prefix):
        if not ruleset.base:
            return prefix
        if prefix == ruleset.base or prefix.startswith(ruleset.base + "/"):
            return prefix[len(ruleset.base) + 1:]
        return None

    # 先判定每个规则集合是否生效：其 base 目录若被更外层（base 更浅）
    # 的规则忽略，该集合不参与（git 不遍历被排除的目录）。
    def base_ignored(ruleset):
        if not ruleset.base:
            return False
        base_level = ruleset.base.count("/") + 1
        best = None
        for order, outer in stack:
            if outer is ruleset or depth_of(outer) >= base_level:
                continue
            rel = rel_of(outer, ruleset.base)
            if rel is None or rel == "":
                continue
            rule = outer._last_match(rel, True, prefix_level=True)
            if rule is not None:
                best = (depth_of(outer), rule)
        return best is not None and not best[1].negated

    active_sets = [r for r in rule_stack if not base_ignored(r)]

    # 收集目标及其全部祖先目录上的命中（无 / 模式在祖先层覆盖子树）。
    hits = []
    for level in range(1, levels + 1):
        prefix = "/".join(segments[:level])
        prefix_is_dir = level < levels or is_dir
        for ruleset in active_sets:
            rel = rel_of(ruleset, prefix)
            if rel is None or rel == "":
                continue
            for rule_index, rule in enumerate(ruleset.rules):
                if rule.dir_only and not prefix_is_dir:
                    continue
                regex = rule.subtree_regex if level < levels else rule.regex
                if regex.fullmatch(rel):
                    hits.append((level, depth_of(ruleset), rule_index, rule))

    # 逐层决定每个祖先目录的最终判定（同层取更深集合、同集合取后行）。
    # 第一个被非否定规则判 ignored 的祖先目录即“父目录被排除”：
    # 其下层的任何命中（含否定）都不能重新纳入。
    blocked_at = None
    for level in range(1, levels):
        level_hits = [h for h in hits if h[0] == level]
        if level_hits:
            winner = max(level_hits, key=lambda h: (h[1], h[2]))
            if not winner[3].negated:
                blocked_at = level
                break
    if blocked_at is not None:
        hits = [h for h in hits if h[0] <= blocked_at]

    if not hits:
        return "allowed", None
    rule = max(hits, key=lambda h: h[:3])[3]
    return ("allowed" if rule.negated else "ignored"), rule


IgnoreRules.matched = staticmethod(matched)
