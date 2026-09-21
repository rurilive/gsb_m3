"""本轮改造的验收测试:排序、默认策略、遮蔽诊断、性能死线、原子热更新。

所有判决都对拍一份朴素逐条实现,遮蔽结论对拍 O(n^2) 朴素判定。
"""

import ipaddress
import random
import threading
import time
import unittest

from fwkit.matcher import DEFAULT_ACTION, Diagnosis, MatchResult, RuleSet, ShadowFinding
from fwkit.rules import ACTION_ALLOW, ACTION_DENY, Packet, Rule, RuleSyntaxError


# ---------------------------------------------------------------------------
# 朴素参考实现
# ---------------------------------------------------------------------------


def naive_order(rules):
    """规则的匹配顺序:prio 升序、同 prio 按加入先后。"""
    return sorted(enumerate(rules), key=lambda item: (item[1].priority, item[0]))


def naive_match(rules, packet, default_action):
    for _index, rule in naive_order(rules):
        if rule.matches(packet):
            return MatchResult(rule.action, rule)
    return MatchResult(default_action, None)


def naive_covers(coverer, rule):
    """任何匹配 rule 的包都匹配 coverer。"""
    if coverer.src is not None:
        if rule.src is None or rule.src.version != coverer.src.version:
            return False
        if not rule.src.subnet_of(coverer.src):
            return False
    if coverer.dst is not None:
        if rule.dst is None or rule.dst.version != coverer.dst.version:
            return False
        if not rule.dst.subnet_of(coverer.dst):
            return False
    return coverer.port_lo <= rule.port_lo and rule.port_hi <= coverer.port_hi


def naive_diagnose(rules):
    """O(n^2):每条规则找最早盖住它的规则,按动作分冗余/不可达。"""
    ordered = [rule for _index, rule in naive_order(rules)]
    redundant = []
    unreachable = []
    for index, rule in enumerate(ordered):
        for coverer in ordered[:index]:
            if naive_covers(coverer, rule):
                finding = ShadowFinding(
                    "redundant" if coverer.action == rule.action
                    else "unreachable", coverer, rule)
                (redundant if coverer.action == rule.action
                 else unreachable).append(finding)
                break
    return Diagnosis(redundant, unreachable)


# ---------------------------------------------------------------------------
# 随机策略与包生成
# ---------------------------------------------------------------------------


PORT_CHOICES = ("any", "single", "range")


def random_port_text(rng):
    kind = rng.choice(PORT_CHOICES)
    if kind == "any":
        return "any"
    if kind == "single":
        return str(rng.randrange(0, 65536))
    lo = rng.randrange(0, 60000)
    hi = min(lo + rng.randrange(1, 4000), 65535)
    return "{}-{}".format(lo, hi)


def random_network_text(rng, version, plen_choices):
    bits = 32 if version == 4 else 128
    plen = rng.choice(plen_choices)
    value = rng.getrandbits(bits) & (((1 << bits) - 1) << (bits - plen))
    cls = ipaddress.IPv4Network if version == 4 else ipaddress.IPv6Network
    return str(cls((value, plen)))


V4_PLENS = (16, 20, 24)
V6_PLENS = (32, 48, 64)


def random_rule_text(rng, line_no, any_prob=0.25, family_bias=None):
    version = family_bias or rng.choice((4, 6))
    if rng.random() < any_prob:
        src = "any"
    else:
        src = random_network_text(rng, version, V4_PLENS if version == 4 else V6_PLENS)
    if rng.random() < any_prob:
        dst = "any"
    else:
        dst = random_network_text(rng, version, V4_PLENS if version == 4 else V6_PLENS)
    action = rng.choice((ACTION_ALLOW, ACTION_DENY))
    return "prio={} {} {} {} {}".format(
        rng.randrange(0, 100), action, src, dst, random_port_text(rng))


def random_packet(rng, version=None):
    version = version or rng.choice((4, 6))
    src_version = version
    dst_version = version if rng.random() < 0.8 else (10 - version)
    bits_src = 32 if src_version == 4 else 128
    bits_dst = 32 if dst_version == 4 else 128
    src = ipaddress.ip_address(rng.getrandbits(bits_src))
    dst = ipaddress.ip_address(rng.getrandbits(bits_dst))
    return Packet(str(src), str(dst), rng.randrange(0, 65536))


def build_ruleset(rng, count, default_action=DEFAULT_ACTION, any_prob=0.25):
    lines = [random_rule_text(rng, i + 1, any_prob=any_prob)
             for i in range(count)]
    return RuleSet("\n".join(lines), default_action=default_action), lines


# ---------------------------------------------------------------------------
# 优先级排序与默认策略
# ---------------------------------------------------------------------------


class TestPriorityOrder(unittest.TestCase):
    def test_rules_are_sorted_by_priority_then_insertion(self):
        ruleset = RuleSet("\n".join([
            "prio=50 allow 10.0.0.0/8 any 443",
            "prio=10 deny 10.1.0.0/16 any 443",
            "prio=10 deny 10.2.0.0/16 any 443",
            "prio=90 allow any any 443",
        ]))
        self.assertEqual(ruleset.line_numbers(), [2, 3, 1, 4])

    def test_first_priority_match_wins_over_text_order(self):
        ruleset = RuleSet(
            "deny 10.1.0.0/16 any 443\nprio=1 allow any any 443\n")
        result = ruleset.match(Packet("10.1.0.5", "8.8.8.8", 443))
        self.assertEqual(result.action, ACTION_ALLOW)
        self.assertEqual(result.rule.line_no, 2)

    def test_same_priority_keeps_insertion_order(self):
        ruleset = RuleSet("\n".join([
            "prio=5 allow any any 443",
            "prio=5 deny 10.0.0.0/8 any 443",
        ]))
        result = ruleset.match(Packet("10.0.0.1", "8.8.8.8", 443))
        self.assertEqual(result.action, ACTION_ALLOW)
        self.assertEqual(result.rule.line_no, 1)

    def test_add_rule_inserts_by_priority(self):
        ruleset = RuleSet("prio=10 allow any any 80\nprio=30 deny any any 80\n")
        ruleset.add_rule(Rule.parse("prio=20 deny 10.0.0.0/8 any 80", line_no=50))
        self.assertEqual(ruleset.line_numbers(), [1, 50, 2])


class TestDefaultPolicy(unittest.TestCase):
    def test_default_is_deny(self):
        ruleset = RuleSet("allow 10.0.0.0/8 any any\n")
        self.assertEqual(ruleset.default_action(), ACTION_DENY)
        result = ruleset.match(Packet("1.2.3.4", "8.8.8.8", 80))
        self.assertEqual(result, MatchResult(ACTION_DENY, None))

    def test_default_allow_is_accepted(self):
        ruleset = RuleSet("allow 10.0.0.0/8 any any\n",
                          default_action=ACTION_ALLOW)
        self.assertEqual(ruleset.default_action(), ACTION_ALLOW)
        result = ruleset.match(Packet("1.2.3.4", "8.8.8.8", 80))
        self.assertEqual(result, MatchResult(ACTION_ALLOW, None))
        self.assertFalse(result.matched)

    def test_default_action_can_be_switched_at_runtime(self):
        ruleset = RuleSet("allow 10.0.0.0/8 any any\n")
        packet = Packet("1.2.3.4", "8.8.8.8", 80)
        self.assertEqual(ruleset.match(packet).action, ACTION_DENY)
        ruleset.default_action(ACTION_ALLOW)
        self.assertEqual(ruleset.match(packet).action, ACTION_ALLOW)
        ruleset.default_action(ACTION_DENY)
        self.assertEqual(ruleset.match(packet).action, ACTION_DENY)

    def test_bad_default_action_rejected(self):
        with self.assertRaises(ValueError):
            RuleSet("", default_action="drop")
        ruleset = RuleSet("")
        with self.assertRaises(ValueError):
            ruleset.default_action("drop")


# ---------------------------------------------------------------------------
# diagnose():遮蔽、冗余与不可达
# ---------------------------------------------------------------------------


class TestDiagnose(unittest.TestCase):
    POLICY = "\n".join([
        "allow 10.0.0.0/8 any any",             # line 1 src 伞
        "deny 10.1.0.0/16 any 443",             # line 2 矛盾,被 1 盖
        "allow 10.2.0.0/16 any 80",             # line 3 冗余,被 1 盖
        "deny any 10.3.0.0/16 any",             # line 4 dst 伞,独立
        "allow 192.168.0.0/16 10.3.0.0/16 80",  # line 5 矛盾,被 4 盖
        "prio=5 deny 9.0.0.0/8 any any",        # line 6 高优先级伞
        "allow 9.9.0.0/16 any any",             # line 7 矛盾,被 6 盖
    ])

    def test_redundant_and_unreachable_with_line_numbers(self):
        ruleset = RuleSet(self.POLICY)
        diagnosis = ruleset.diagnose()
        redundant = [(f.rule.line_no, f.coverer.line_no)
                     for f in diagnosis.redundant]
        unreachable = [(f.rule.line_no, f.coverer.line_no)
                       for f in diagnosis.unreachable]
        self.assertEqual(redundant, [(3, 1)])
        # 结果按匹配顺序排列:6 最先,其后 1..7。
        self.assertEqual(unreachable, [(2, 1), (5, 4), (7, 6)])

    def test_findings_carry_both_rules_and_kind(self):
        ruleset = RuleSet("deny any any any\nallow 10.0.0.0/8 any 80-90\n")
        finding = ruleset.diagnose().unreachable[0]
        self.assertEqual(finding.kind, "unreachable")
        self.assertEqual(finding.coverer.line_no, 1)
        self.assertEqual(finding.rule.line_no, 2)

    def test_partial_overlap_is_not_shadowing(self):
        # 网段交叉但不包含、端口只盖住一半,都不能算遮蔽。
        ruleset = RuleSet("\n".join([
            "deny 10.0.0.0/8 any 0-1024",
            "allow 10.0.0.0/8 any 2000-3000",
            "deny 10.1.0.0/16 10.2.0.0/16 8080",
        ]))
        diagnosis = ruleset.diagnose()
        self.assertEqual(diagnosis.redundant, [])
        self.assertEqual(diagnosis.unreachable, [])

    def test_wider_selector_either_side_shadows(self):
        ruleset = RuleSet("\n".join([
            "deny 10.0.0.0/8 any any",
            "allow 10.1.0.0/16 any any",       # src 被盖
            "deny any 10.2.0.0/16 any",
            "allow any 10.2.3.0/24 any",       # dst 被盖
        ]))
        diagnosis = ruleset.diagnose()
        self.assertEqual(
            [(f.rule.line_no, f.coverer.line_no) for f in diagnosis.unreachable],
            [(2, 1), (4, 3)])

    def test_cross_family_never_shadows(self):
        # v4 伞盖不到 v6 规则;单边 any 也只在同一族内成立;
        # src、dst 族不一致的规则只可能被跨族/单边 any/both-any 规则盖。
        ruleset = RuleSet("\n".join([
            "deny 10.0.0.0/8 any any",
            "allow 10.1.0.0/16 any any",           # v4 被盖
            "deny 2001:db8::/32 any any",
            "allow 2001:db8:1::/48 any any",       # v6 被 v6 盖,不被 v4 盖
            "deny any any any",                    # both-any 大伞,无遮蔽
            "allow 10.1.0.0/16 2001:db8::/32 any",  # 跨族,最早被 line 1 盖
        ]))
        diagnosis = ruleset.diagnose()
        self.assertEqual(
            [(f.rule.line_no, f.coverer.line_no) for f in diagnosis.unreachable],
            [(2, 1), (4, 3), (6, 1)])
        self.assertEqual(diagnosis.redundant, [])

    def test_cross_family_exact_rules_shadow_each_other(self):
        ruleset = RuleSet("\n".join([
            "deny 0.0.0.0/0 ::/0 any",                  # 跨族大伞
            "allow 10.0.0.0/8 2001:db8::/32 80",        # 被 line 1 盖
            "allow 10.0.0.0/8 10.2.0.0/16 80",         # dst 是 v4,不被跨族盖
            "deny 10.0.0.0/8 2001:db8::/32 80-90",      # 端口更宽但在 1 之后
        ]))
        diagnosis = ruleset.diagnose()
        self.assertEqual(
            [(f.rule.line_no, f.coverer.line_no) for f in diagnosis.unreachable],
            [(2, 1)])
        self.assertEqual(
            [(f.rule.line_no, f.coverer.line_no) for f in diagnosis.redundant],
            [(4, 1)])

    def test_diagnosis_refreshes_after_mutations(self):
        ruleset = RuleSet("allow 10.0.0.0/8 any any\n")
        self.assertFalse(ruleset.diagnose())
        ruleset.add_rule(Rule.parse("allow 10.1.0.0/16 any any", line_no=9))
        redundant = ruleset.diagnose().redundant
        self.assertEqual([(f.rule.line_no, f.coverer.line_no) for f in redundant],
                         [(9, 1)])
        ruleset.remove_rule(1)
        self.assertFalse(ruleset.diagnose())

    def test_random_policies_match_naive_diagnosis(self):
        rng = random.Random(20260922)
        for trial in range(60):
            ruleset, lines = build_ruleset(rng, rng.randrange(1, 80),
                                           any_prob=rng.choice((0.0, 0.3, 0.6)))
            rules = [Rule.parse(line, index + 1)
                     for index, line in enumerate(lines)]
            expected = naive_diagnose(rules)
            actual = ruleset.diagnose()
            expected_pairs = (
                [(f.rule.line_no, f.coverer.line_no) for f in expected.redundant],
                [(f.rule.line_no, f.coverer.line_no) for f in expected.unreachable])
            actual_pairs = (
                [(f.rule.line_no, f.coverer.line_no) for f in actual.redundant],
                [(f.rule.line_no, f.coverer.line_no) for f in actual.unreachable])
            self.assertEqual(actual_pairs, expected_pairs,
                             "diagnose mismatch on trial {}".format(trial))


# ---------------------------------------------------------------------------
# 匹配判决对拍朴素实现
# ---------------------------------------------------------------------------


class TestMatchingDifferential(unittest.TestCase):
    def assertSameAsNaive(self, ruleset, rules, packet, default_action):
        expected = naive_match(rules, packet, default_action)
        actual = ruleset.match(packet)
        self.assertEqual(actual.action, expected.action)
        if expected.rule is None:
            self.assertIsNone(actual.rule)
        else:
            self.assertEqual(actual.rule.line_no, expected.rule.line_no)

    def test_random_policies_and_packets(self):
        rng = random.Random(77)
        for trial in range(40):
            default_action = rng.choice((ACTION_ALLOW, ACTION_DENY))
            ruleset, lines = build_ruleset(
                rng, rng.randrange(1, 120), default_action=default_action,
                any_prob=rng.choice((0.0, 0.2, 0.5)))
            rules = [Rule.parse(line, index + 1)
                     for index, line in enumerate(lines)]
            for _ in range(300):
                packet = random_packet(rng)
                self.assertSameAsNaive(ruleset, rules, packet, default_action)

    def test_any_side_still_respects_families(self):
        rules_text = "\n".join([
            "allow any any any",
            "deny 10.0.0.0/8 any any",
            "deny any 10.0.0.0/8 any",
            "allow 2001:db8::/32 2001:db9::/32 any",
            "deny 10.0.0.0/8 2001:db8::/32 any",
        ])
        ruleset = RuleSet(rules_text)
        rules = [Rule.parse(line, i + 1)
                 for i, line in enumerate(rules_text.splitlines())]
        rng = random.Random(5)
        probes = [
            Packet("10.0.0.1", "8.8.8.8", 80),
            Packet("8.8.8.8", "10.0.0.1", 80),
            Packet("2001:db8::1", "2001:db9::1", 80),
            Packet("10.0.0.1", "2001:db8::1", 80),
            Packet("2001:db8::1", "10.0.0.1", 80),
        ]
        for packet in probes:
            self.assertSameAsNaive(ruleset, rules, packet, ACTION_DENY)
        for _ in range(500):
            self.assertSameAsNaive(ruleset, rules, random_packet(rng),
                                   ACTION_DENY)

    def test_mixed_family_packets(self):
        # src v4、dst v6 这类包:v4-only、v6-only、族不一致规则都不许命中,
        # 只有单边 any 或 both-any 的规则可能命中。
        rules_text = "\n".join([
            "deny any 2001:db8::/32 22",
            "allow 10.0.0.0/8 any 22",
            "deny 10.0.0.0/8 2001:db8::/32 22",
            "allow any any 22",
        ])
        ruleset = RuleSet(rules_text)
        rules = [Rule.parse(line, i + 1)
                 for i, line in enumerate(rules_text.splitlines())]
        packet = Packet("10.0.0.1", "2001:db8::9", 22)
        self.assertSameAsNaive(ruleset, rules, packet, ACTION_DENY)
        self.assertEqual(ruleset.match(packet).rule.line_no, 1)

    def test_stats_caliber_preserved(self):
        ruleset, lines = build_ruleset(random.Random(9), 200)
        for _ in range(1000):
            ruleset.match(random_packet(random.Random(11)))
        stats = ruleset.stats()
        self.assertEqual(stats.lookups, 1000)
        self.assertEqual(stats.matched + stats.fell_through, 1000)
        self.assertGreaterEqual(stats.comparisons, stats.matched)


# ---------------------------------------------------------------------------
# 热更新与原子重载
# ---------------------------------------------------------------------------


class TestAtomicReload(unittest.TestCase):
    def test_failed_reload_keeps_old_ruleset_intact(self):
        ruleset = RuleSet("deny any any any\n")
        packet = Packet("10.0.0.1", "8.8.8.8", 80)
        before = ruleset.match(packet)
        reloads_before = ruleset.stats().reloads
        with self.assertRaises(RuleSyntaxError):
            ruleset.reload("allow any any 80\n\nbogus three tokens\n")
        self.assertEqual(len(ruleset), 1)
        self.assertEqual(ruleset.match(packet), before)
        self.assertEqual(ruleset.stats().reloads, reloads_before)

    def test_failed_reload_never_allows_half_loaded_rules(self):
        ruleset = RuleSet("deny any any any\n")
        packet = Packet("10.0.0.1", "8.8.8.8", 80)
        with self.assertRaises(RuleSyntaxError):
            ruleset.reload(
                "allow any any any\nallow any any 81\nnope\n")
        # 失败后旧 deny 伞仍在,不会因为“只装了前两条 allow”而放行。
        self.assertEqual(ruleset.match(packet).action, ACTION_DENY)

    def test_successful_reload_replaces_everything(self):
        ruleset = RuleSet("deny any any any\n")
        ruleset.reload("allow any any 80\n")
        self.assertEqual(
            ruleset.match(Packet("10.0.0.1", "8.8.8.8", 80)).action,
            ACTION_ALLOW)
        self.assertEqual(
            ruleset.match(Packet("10.0.0.1", "8.8.8.8", 81)).action,
            ACTION_DENY)
        self.assertEqual(ruleset.stats().reloads, 2)

    def test_concurrent_matches_always_see_consistent_view(self):
        ruleset = RuleSet("deny any any any\n")
        stop = threading.Event()
        errors = []

        def worker():
            rng = random.Random(1)
            while not stop.is_set():
                try:
                    result = ruleset.match(random_packet(rng))
                    if result.action not in (ACTION_ALLOW, ACTION_DENY):
                        errors.append("bad action")
                    if result.matched and result.rule is None:
                        errors.append("inconsistent result")
                except Exception as exc:  # pragma: no cover - 并发不应抛错
                    errors.append(repr(exc))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for index in range(200):
            if index % 2:
                ruleset.reload("allow any any {}\n".format(index % 5))
            else:
                ruleset.add_rule(Rule.parse(
                    "prio={} deny 10.0.0.0/8 any any".format(index % 3),
                    line_no=100 + index))
        stop.set()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# 性能死线:十万条 v4/v6 混排,单次匹配试的规则条数不随规则数线性涨
# ---------------------------------------------------------------------------


class TestPerformance(unittest.TestCase):
    SCALES = (1_000, 10_000, 100_000)
    PROBES = 2000

    def _build(self, rng, count):
        return build_ruleset(rng, count, any_prob=0.05)

    def _probe(self, ruleset, seed, count=PROBES):
        rng = random.Random(seed)
        for _ in range(count):
            ruleset.match(random_packet(rng))

    def test_average_comparisons_under_budget_and_sublinear(self):
        averages = {}
        for count in self.SCALES:
            rng = random.Random(1000 + count)
            started = time.time()
            ruleset, _lines = self._build(rng, count)
            load_seconds = time.time() - started
            stats = ruleset.stats()
            before = stats.lookups
            self._probe(ruleset, 9000 + count)
            self.assertEqual(stats.lookups - before, self.PROBES)
            average = (stats.comparisons / stats.lookups)
            averages[count] = average
            # 死线:平均试的规则条数不超过 64,且远小于规则总数。
            self.assertLessEqual(
                average, 64.0,
                "avg comparisons {:.2f} exceeds 64 at {} rules".format(
                    average, count))
            # 装载本身也不能退化成 O(n^2)。
            self.assertLess(load_seconds, 30.0)
        # 不随规则数线性涨:100k 的均值不得超过 10k 均值的 3 倍。
        self.assertLessEqual(averages[100_000], averages[10_000] * 3.0)

    def test_large_scale_judgments_still_match_naive(self):
        rng = random.Random(4242)
        ruleset, lines = self._build(rng, 100_000)
        rules = [Rule.parse(line, i + 1) for i, line in enumerate(lines)]
        probe_rng = random.Random(777)
        for _ in range(32):
            packet = random_packet(probe_rng)
            expected = naive_match(rules, packet, DEFAULT_ACTION)
            actual = ruleset.match(packet)
            self.assertEqual(actual.action, expected.action)
            if expected.rule is None:
                self.assertIsNone(actual.rule)
            else:
                self.assertEqual(actual.rule.line_no, expected.rule.line_no)

    def test_large_scale_diagnose_agrees_with_naive_sample(self):
        rng = random.Random(5151)
        # 随机规则下自然遮蔽很少,这里 2 千条规模朴素对拍仍足够快,
        # 用来给 diagnose 的精确性兜底。
        ruleset, lines = build_ruleset(rng, 2_000, any_prob=0.15)
        rules = [Rule.parse(line, i + 1) for i, line in enumerate(lines)]
        expected = naive_diagnose(rules)
        actual = ruleset.diagnose()
        for label, expected_list, actual_list in (
                ("redundant", expected.redundant, actual.redundant),
                ("unreachable", expected.unreachable, actual.unreachable)):
            expected_pairs = [(f.rule.line_no, f.coverer.line_no)
                              for f in expected_list]
            actual_pairs = [(f.rule.line_no, f.coverer.line_no)
                            for f in actual_list]
            self.assertEqual(actual_pairs, expected_pairs, label)


if __name__ == "__main__":
    unittest.main()
