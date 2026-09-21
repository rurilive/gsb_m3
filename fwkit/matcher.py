"""规则集与匹配入口。"""

from fwkit.rules import ACTION_DENY, parse_rules
from fwkit.stats import MatchStats

# 目前没命中任何规则时固定落到这个动作。
DEFAULT_ACTION = ACTION_DENY


class MatchResult:
    """一次匹配的结论:动作和命中的规则。

    没有规则命中时 rule 为 None,动作是默认策略。
    """

    __slots__ = ("action", "rule")

    def __init__(self, action, rule=None):
        self.action = action
        self.rule = rule

    @property
    def matched(self):
        return self.rule is not None

    def __eq__(self, other):
        if not isinstance(other, MatchResult):
            return NotImplemented
        return (self.action, self.rule) == (other.action, other.rule)

    def __repr__(self):
        return "MatchResult(action={!r}, rule={!r})".format(self.action, self.rule)


class RuleSet:
    """一组规则,按加入顺序排列。

    match 从前往后逐条试,第一条 src、dst、端口都匹配的规则说了算。
    规则的 priority 会被解析和保存,但暂时不参与匹配。
    """

    def __init__(self, lines=None):
        self._rules = []
        self._stats = MatchStats()
        if lines is not None:
            self.reload(lines)

    # ---- 规则集视图 ----

    def rules(self):
        """当前规则列表的副本,顺序即加入顺序。"""
        return list(self._rules)

    def line_numbers(self):
        """当前规则在文本里对应的行号,按加入顺序。"""
        return [rule.line_no for rule in self._rules]

    def stats(self):
        """匹配统计,口径见 fwkit.stats。"""
        return self._stats

    def __len__(self):
        return len(self._rules)

    # ---- 加载与热更新 ----

    def _install_rule(self, rule):
        """把一条规则装进当前视图。子类可以覆写这个方法来观察安装过程。"""
        self._rules.append(rule)

    def add_rule(self, rule):
        """加一条规则,立即生效。"""
        self._install_rule(rule)
        return rule

    def remove_rule(self, line_no):
        """按行号删掉第一条对得上的规则,删到了返回 True,否则 False。"""
        for index, rule in enumerate(self._rules):
            if rule.line_no == line_no:
                del self._rules[index]
                return True
        return False

    def reload(self, lines):
        """整体重载:先把规则清空,再按文本顺序逐条装。

        lines 是规则文本或行的列表。文本里有语法错误时抛
        RuleSyntaxError,已经装进去的规则不回退。
        """
        if isinstance(lines, str):
            lines = lines.splitlines()
        self._rules = []
        self._stats.reloads += 1
        for rule in parse_rules(lines):
            self._install_rule(rule)
        return self

    # ---- 匹配 ----

    def match(self, packet):
        """给一个包判动作:按加入顺序逐条试,第一条命中的规则说了算。"""
        self._stats.lookups += 1
        for rule in self._rules:
            self._stats.comparisons += 1
            if rule.matches(packet):
                self._stats.matched += 1
                return MatchResult(rule.action, rule)
        self._stats.fell_through += 1
        return MatchResult(DEFAULT_ACTION, None)
