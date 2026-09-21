"""fwkit 演示。

第一段:规则加载、prio 匹配与默认策略、匹配统计、热更新增删。
第二段:prio 排序、可配默认策略、diagnose() 遮蔽清单、十万条规则性能、
        reload 的原子性。
"""

import random

import ipaddress

from fwkit.matcher import RuleSet
from fwkit.rules import ACTION_ALLOW, Packet, Rule, RuleSyntaxError

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

    print("=== prio 匹配(先命中先算,落空走默认 deny) ===")
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

    show_priority_order()
    show_default_policy()
    show_diagnose()
    show_performance()
    show_atomic_reload()


def show_priority_order():
    print("=== prio 排序 ===")
    ruleset = RuleSet("\n".join([
        "deny 10.0.0.0/8 any 443",
        "prio=10 allow 10.1.0.0/16 any 443",
        "prio=10 allow 10.2.0.0/16 any 443",
        "prio=90 allow any any 443",
    ]))
    print("  匹配顺序行号: {}".format(ruleset.line_numbers()))
    result = ruleset.match(Packet("10.1.0.5", "8.8.8.8", 443))
    print("  10.1.0.5:443 -> {} (line {},低 prio 的规则先算)".format(
        result.action, result.rule.line_no))


def show_default_policy():
    print("=== 可配默认策略 ===")
    ruleset = RuleSet("allow 10.0.0.0/8 any any\n", default_action=ACTION_ALLOW)
    packet = Packet("1.2.3.4", "8.8.8.8", 80)
    print("  default_action=allow,未命中包 -> {}".format(
          ruleset.match(packet).action))
    ruleset.default_action("deny")
    print("  运行时切回 deny,同一包 -> {}".format(
          ruleset.match(packet).action))


def show_diagnose():
    print("=== diagnose():遮蔽与不可达 ===")
    ruleset = RuleSet("\n".join([
        "allow 10.0.0.0/8 any any",              # line 1 src 伞
        "deny 10.1.0.0/16 any 443",              # line 2 不可达
        "allow 10.2.0.0/16 any 80",              # line 3 冗余
        "deny any 10.3.0.0/16 any",              # line 4 dst 伞
        "allow 192.168.0.0/16 10.3.0.0/16 80",   # line 5 不可达
    ]))
    diagnosis = ruleset.diagnose()
    for finding in diagnosis.unreachable:
        print("  不可达: line {} 被 line {} 挡住(动作 {} 对 {})".format(
            finding.rule.line_no, finding.coverer.line_no,
            finding.coverer.action, finding.rule.action))
    for finding in diagnosis.redundant:
        print("  冗余:   line {} 已被 line {} 整个包住,动作相同".format(
            finding.rule.line_no, finding.coverer.line_no))


def _random_policy(rng, count):
    lines = []
    for index in range(count):
        version = rng.choice((4, 6))
        bits = 32 if version == 4 else 128
        plens = (16, 20, 24) if version == 4 else (32, 48, 64)

        def side():
            if rng.random() < 0.05:
                return "any"
            plen = rng.choice(plens)
            value = rng.getrandbits(bits) & (((1 << bits) - 1) << (bits - plen))
            cls = ipaddress.IPv4Network if version == 4 else ipaddress.IPv6Network
            return str(cls((value, plen)))

        roll = rng.random()
        if roll < 0.4:
            ports = "any"
        elif roll < 0.7:
            ports = str(rng.randrange(0, 65536))
        else:
            lo = rng.randrange(0, 60000)
            ports = "{}-{}".format(lo, min(lo + rng.randrange(1, 5000), 65535))
        lines.append("prio={} {} {} {} {}".format(
            rng.randrange(0, 200), rng.choice(("allow", "deny")),
            side(), side(), ports))
    return "\n".join(lines)


def show_performance():
    print("=== 十万条 v4/v6 混排规则的性能 ===")
    rng = random.Random(42)
    policy = _random_policy(rng, 100_000)
    ruleset = RuleSet(policy)
    probe_rng = random.Random(99)
    probes = 2000
    for _ in range(probes):
        version = probe_rng.choice((4, 6))
        bits = 32 if version == 4 else 128
        packet = Packet(
            str(ipaddress.ip_address(probe_rng.getrandbits(bits))),
            str(ipaddress.ip_address(probe_rng.getrandbits(bits))),
            probe_rng.randrange(0, 65536))
        ruleset.match(packet)
    print("  规则数={},随机包 {} 个,平均试规则 {:.2f} 条/次(死线 64)".format(
        len(ruleset), probes, ruleset.stats().average_comparisons()))


def show_atomic_reload():
    print("=== reload 原子性 ===")
    ruleset = RuleSet("deny any any any\n")
    packet = Packet("10.0.0.1", "8.8.8.8", 80)
    print("  失败前判决: {}".format(ruleset.match(packet).action))
    try:
        ruleset.reload("allow any any 80\n\nbogus three tokens\n")
    except RuleSyntaxError as error:
        print("  reload 报错: {}".format(error))
    print("  失败后仍是原表,判决: {} (无半装、无放行空窗)".format(
        ruleset.match(packet).action))



if __name__ == "__main__":
    main()
