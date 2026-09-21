"""fwkit 现状演示。

第一段:规则加载、逐条匹配命中与落默认策略、匹配统计、热更新增删。
第二段:留给改造后的演示位子(见文末注释)。
"""

from fwkit.matcher import RuleSet
from fwkit.rules import Packet, Rule

POLICY = """\
# 办公网入站策略
prio=30 deny 10.8.0.0/16 any 22
allow 10.0.0.0/8 10.1.0.0/16 443
prio=60 allow 10.0.0.0/8 10.2.0.0/16 8000-8080
deny any 2001:db8:1::/48 any
allow 192.168.0.0/16 10.3.0.0/16 53
"""

PROBES = [
    Packet("10.0.0.5", "10.1.0.9", 443),
    Packet("10.8.0.7", "10.1.0.9", 22),
    Packet("10.0.0.5", "10.2.0.4", 8080),
    Packet("2001:db8:1::5", "2001:db8:1::9", 443),
    Packet("2001:db8:2::5", "10.1.0.9", 443),
    Packet("172.16.0.5", "10.1.0.9", 443),
]


def main():
    ruleset = RuleSet(POLICY)

    print("=== 规则集 ===")
    for rule in ruleset.rules():
        print("  {}".format(rule))

    print("=== 逐条匹配 ===")
    for packet in PROBES:
        result = ruleset.match(packet)
        where = "line {}".format(result.rule.line_no) if result.matched else "默认策略"
        print("  {:<40} -> {:<5} ({})".format(str(packet), result.action, where))

    print("=== 匹配统计 ===")
    print("  {}".format(ruleset.stats().summary()))

    print("=== 热更新 ===")
    ruleset.add_rule(Rule.parse("prio=5 allow 172.16.0.0/12 10.1.0.0/16 443", line_no=101))
    result = ruleset.match(Packet("172.16.0.5", "10.1.0.9", 443))
    print("  加一条后 172.16.0.5 -> 10.1.0.9:443 : {} (line {})".format(
        result.action, result.rule.line_no))
    ruleset.remove_rule(101)
    result = ruleset.match(Packet("172.16.0.5", "10.1.0.9", 443))
    print("  删掉后同一查询: {} ({})".format(
        result.action, "line {}".format(result.rule.line_no) if result.matched else "默认策略"))

    # TODO(本轮改造): 优先级排序与可配默认策略、diagnose() 的遮蔽与不可达清单、
    # 十万条规则下的比较次数、热更新与整体重载,实现后在这里补第二段演示。


if __name__ == "__main__":
    main()
