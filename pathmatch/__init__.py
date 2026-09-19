"""pathmatch: 路径 glob 匹配。"""

from pathmatch.ignore import IgnoreRules, Rule, matched
from pathmatch.match import match

__all__ = ["IgnoreRules", "Rule", "matched", "match"]
