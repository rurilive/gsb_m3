"""匹配统计。

lookups       match() 被调用的次数
comparisons   match() 里拿包去试规则的累计条数
matched       有规则命中的次数
fell_through  没命中任何规则、落到默认策略的次数
reloads       reload() 被调用的次数
"""


class MatchStats:
    """RuleSet 上的计数器,归 RuleSet 所有,调用方只读。"""

    __slots__ = ("lookups", "comparisons", "matched", "fell_through", "reloads")

    def __init__(self):
        self.reset()

    def reset(self):
        self.lookups = 0
        self.comparisons = 0
        self.matched = 0
        self.fell_through = 0
        self.reloads = 0

    def average_comparisons(self):
        """平均每次匹配试了多少条规则。"""
        if not self.lookups:
            return 0.0
        return self.comparisons / self.lookups

    def as_dict(self):
        return {
            "lookups": self.lookups,
            "comparisons": self.comparisons,
            "matched": self.matched,
            "fell_through": self.fell_through,
            "reloads": self.reloads,
        }

    def summary(self):
        return "lookups={} comparisons={} avg={:.2f} matched={} fell_through={} reloads={}".format(
            self.lookups, self.comparisons, self.average_comparisons(),
            self.matched, self.fell_through, self.reloads)

    def __repr__(self):
        return "MatchStats({})".format(self.summary())
