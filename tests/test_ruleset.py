"""fwkit 现有行为的锁定测试。"""

import unittest

from fwkit.matcher import MatchResult, RuleSet
from fwkit.rules import (ACTION_ALLOW, ACTION_DENY, DEFAULT_PRIORITY, Packet, Rule,
                         RuleSyntaxError, parse_rules)


class TestParsing(unittest.TestCase):
    def test_bare_rule_uses_default_priority(self):
        rule = Rule.parse("allow 10.0.0.0/8 any 443", line_no=7)
        self.assertEqual(rule.action, ACTION_ALLOW)
        self.assertEqual(rule.priority, DEFAULT_PRIORITY)
        self.assertEqual(rule.line_no, 7)
        self.assertEqual((rule.port_lo, rule.port_hi), (443, 443))
        self.assertEqual(str(rule.src), "10.0.0.0/8")
        self.assertIsNone(rule.dst)

    def test_priority_token_is_parsed(self):
        rule = Rule.parse("prio=20 deny 10.0.0.0/8 10.1.0.0/16 1-1024", 3)
        self.assertEqual(rule.priority, 20)
        self.assertEqual((rule.port_lo, rule.port_hi), (1, 1024))
        self.assertIsNotNone(rule.dst)

    def test_any_ports_cover_the_full_range(self):
        rule = Rule.parse("allow any any any")
        self.assertEqual((rule.port_lo, rule.port_hi), (0, 65535))

    def test_host_bits_in_network_are_masked_off(self):
        rule = Rule.parse("deny 10.1.2.3/8 any 80")
        self.assertEqual(str(rule.src), "10.0.0.0/8")

    def test_v6_rule_parses(self):
        rule = Rule.parse("allow 2001:db8::1/32 any 443")
        self.assertEqual(rule.src.version, 6)
        self.assertEqual(str(rule.src), "2001:db8::/32")

    def test_comments_and_blanks_keep_real_line_numbers(self):
        rules = parse_rules("  # 注释\n\nallow any any 80\n   \ndeny any any 81\n")
        self.assertEqual([rule.line_no for rule in rules], [3, 5])

    def test_bad_action_reports_line(self):
        with self.assertRaises(RuleSyntaxError) as ctx:
            Rule.parse("drop any any 80", 12)
        self.assertEqual(ctx.exception.line_no, 12)

    def test_reversed_port_range_reports_line(self):
        with self.assertRaises(RuleSyntaxError) as ctx:
            Rule.parse("allow any any 90-80", 4)
        self.assertEqual(ctx.exception.line_no, 4)

    def test_missing_columns_reports_line(self):
        with self.assertRaises(RuleSyntaxError) as ctx:
            Rule.parse("allow any 80", 1)
        self.assertEqual(ctx.exception.line_no, 1)

    def test_bad_priority_token_reports_line(self):
        with self.assertRaises(RuleSyntaxError) as ctx:
            Rule.parse("prio=high allow any any 80", 2)
        self.assertEqual(ctx.exception.line_no, 2)


class TestSelectorMatching(unittest.TestCase):
    def test_port_boundaries_are_inclusive(self):
        rule = Rule.parse("allow 10.0.0.0/8 any 8000-8080")
        self.assertTrue(rule.matches(Packet("10.1.1.1", "10.2.2.2", 8000)))
        self.assertTrue(rule.matches(Packet("10.1.1.1", "10.2.2.2", 8080)))
        self.assertFalse(rule.matches(Packet("10.1.1.1", "10.2.2.2", 7999)))
        self.assertFalse(rule.matches(Packet("10.1.1.1", "10.2.2.2", 8081)))

    def test_family_mismatch_never_matches(self):
        rule = Rule.parse("allow 10.0.0.0/8 any any")
        self.assertFalse(rule.matches(Packet("2001:db8::1", "2001:db8::2", 80)))

    def test_any_side_matches_both_families(self):
        rule = Rule.parse("deny any 2001:db8::/32 any")
        self.assertTrue(rule.matches(Packet("10.0.0.1", "2001:db8::5", 80)))
        self.assertFalse(rule.matches(Packet("10.0.0.1", "2001:db9::5", 80)))

    def test_src_and_dst_must_both_match(self):
        rule = Rule.parse("allow 10.0.0.0/8 10.1.0.0/16 any")
        self.assertFalse(rule.matches(Packet("10.0.0.1", "10.2.0.1", 80)))
        self.assertTrue(rule.matches(Packet("10.0.0.1", "10.1.0.1", 80)))

    def test_selector_is_canonical(self):
        first = Rule.parse("deny 10.1.2.3/8 any any")
        second = Rule.parse("deny 10.0.0.0/8 any 0-65535")
        self.assertEqual(first.selector(), second.selector())


class TestRuleSetBasics(unittest.TestCase):
    POLICY = "\n".join([
        "deny 10.8.0.0/16 any 22",
        "allow 10.0.0.0/8 10.1.0.0/16 443",
        "allow 10.0.0.0/8 10.1.0.0/16 8000-8080",
    ])

    def test_reload_keeps_order_and_line_numbers(self):
        ruleset = RuleSet(self.POLICY)
        self.assertEqual(len(ruleset), 3)
        self.assertEqual(ruleset.line_numbers(), [1, 2, 3])

    def test_first_match_wins(self):
        ruleset = RuleSet("allow any any 443\ndeny 10.0.0.0/8 any 443\n")
        result = ruleset.match(Packet("10.0.0.5", "10.1.0.9", 443))
        self.assertEqual(result.action, ACTION_ALLOW)
        self.assertEqual(result.rule.line_no, 1)

    def test_miss_falls_to_default_deny(self):
        ruleset = RuleSet("allow 10.0.0.0/8 10.1.0.0/16 443\n")
        result = ruleset.match(Packet("172.16.0.1", "10.1.0.9", 443))
        self.assertEqual(result, MatchResult(ACTION_DENY, None))
        self.assertFalse(result.matched)

    def test_rules_returns_a_copy(self):
        ruleset = RuleSet(self.POLICY)
        snapshot = ruleset.rules()
        snapshot.clear()
        self.assertEqual(len(ruleset), 3)

    def test_add_and_remove_take_effect_immediately(self):
        ruleset = RuleSet("allow any any 80\n")
        self.assertEqual(ruleset.match(Packet("10.0.0.1", "10.0.0.2", 80)).action, ACTION_ALLOW)
        self.assertTrue(ruleset.remove_rule(1))
        self.assertFalse(ruleset.remove_rule(99))
        self.assertEqual(len(ruleset), 0)
        self.assertEqual(ruleset.match(Packet("10.0.0.1", "10.0.0.2", 80)), MatchResult(ACTION_DENY, None))
        ruleset.add_rule(Rule.parse("deny any any 80", 7))
        self.assertEqual(ruleset.match(Packet("10.0.0.1", "10.0.0.2", 80)).action, ACTION_DENY)

    def test_reload_replaces_previous_rules(self):
        ruleset = RuleSet("deny any any any\n")
        ruleset.reload("allow any any 80\n")
        self.assertEqual(len(ruleset), 1)
        self.assertEqual(ruleset.match(Packet("10.0.0.1", "10.0.0.2", 80)).action, ACTION_ALLOW)

    def test_reload_syntax_error_reports_line(self):
        ruleset = RuleSet("allow any any 80\n")
        with self.assertRaises(RuleSyntaxError) as ctx:
            ruleset.reload("allow any any 80\n\nbogus three tokens\n")
        self.assertEqual(ctx.exception.line_no, 3)

    def test_stats_are_kept_per_lookup(self):
        ruleset = RuleSet("deny 10.8.0.0/16 any 22\nallow 10.0.0.0/8 10.1.0.0/16 443\n")
        ruleset.match(Packet("10.0.0.5", "10.1.0.9", 443))
        ruleset.match(Packet("172.16.0.5", "10.1.0.9", 443))
        stats = ruleset.stats()
        self.assertEqual(stats.lookups, 2)
        self.assertEqual(stats.matched, 1)
        self.assertEqual(stats.fell_through, 1)
        self.assertGreaterEqual(stats.comparisons, 1)
        self.assertLessEqual(stats.comparisons, 4)
        self.assertEqual(stats.reloads, 1)

    def test_stats_reset(self):
        ruleset = RuleSet("allow any any 80\n")
        ruleset.match(Packet("10.0.0.1", "10.0.0.2", 80))
        ruleset.stats().reset()
        self.assertEqual(ruleset.stats().as_dict(),
                         {"lookups": 0, "comparisons": 0, "matched": 0,
                          "fell_through": 0, "reloads": 0})


if __name__ == "__main__":
    unittest.main()
