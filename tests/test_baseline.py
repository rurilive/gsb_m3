"""stablematch 现有行为的锁定测试。

这里只描述改造前的事实：两拨人、穷举方案、返回对男方最有利的那个稳定配对。
"""
import unittest

from stablematch.core import (
    Erro,
    InvalidInput,
    UnstableMatching,
    all_stable,
    enumerate_pairings,
    first_unstable,
    instabilities,
    normalise,
    stable_pairing,
)


MEN = ["ann", "bob", "cid"]
WOMEN = ["dee", "eve", "fay"]
MEN_PREFS = {
    "ann": ["eve", "dee"],
    "bob": ["fay", "eve"],
    "cid": ["dee", "fay"],
}
WOMEN_PREFS = {
    "dee": ["bob", "cid"],
    "eve": ["cid", "ann"],
    "fay": ["ann", "bob"],
}


def prepared():
    """返回补齐过偏好的四元组。"""
    return normalise(MEN, WOMEN, MEN_PREFS, WOMEN_PREFS)


class TestErrors(unittest.TestCase):
    def test_exceptions_share_one_base(self):
        self.assertTrue(issubclass(InvalidInput, Erro))
        self.assertTrue(issubclass(UnstableMatching, Erro))

    def test_bad_input_is_an_erro(self):
        with self.assertRaises(Erro):
            normalise(None, ["dee"], {}, {"dee": []})


class TestNormalise(unittest.TestCase):
    def test_pads_missing_members_by_name_order(self):
        men = ["ann", "bob"]
        women = ["dee", "eve", "fay"]
        _, _, mprefs, wprefs = normalise(
            men, women,
            {"ann": ["dee"], "bob": ["eve"]},
            {"dee": [], "eve": [], "fay": []})
        self.assertEqual(mprefs["ann"], ["dee", "eve", "fay"])
        self.assertEqual(wprefs["dee"], ["ann", "bob"])

    def test_accepts_full_orders(self):
        _, _, mprefs, wprefs = prepared()
        self.assertEqual(mprefs["ann"], ["eve", "dee", "fay"])
        self.assertEqual(wprefs["dee"], ["bob", "cid", "ann"])

    def test_rejects_duplicate_name(self):
        with self.assertRaises(InvalidInput):
            normalise(["ann", "ann"], ["dee"],
                      {"ann": ["dee"]}, {"dee": ["ann"]})

    def test_rejects_unknown_preference(self):
        with self.assertRaises(InvalidInput):
            normalise(["ann"], ["dee"],
                      {"ann": ["ghost"]}, {"dee": ["ann"]})

    def test_rejects_missing_preference_key(self):
        with self.assertRaises(InvalidInput):
            normalise(["ann", "bob"], ["dee"],
                      {"ann": ["dee"]}, {"dee": ["ann"]})

    def test_rejects_self_reference(self):
        with self.assertRaises(InvalidInput):
            normalise(["ann"], ["dee"],
                      {"ann": ["ann"]}, {"dee": ["ann"]})

    def test_rejects_repeated_entry(self):
        with self.assertRaises(InvalidInput):
            normalise(["ann"], ["dee", "eve"],
                      {"ann": ["dee", "dee"]},
                      {"dee": ["ann"], "eve": ["ann"]})


class TestInstabilities(unittest.TestCase):
    def test_stable_pairing_has_none(self):
        pairing = stable_pairing(MEN, WOMEN, MEN_PREFS, WOMEN_PREFS)
        _, _, mprefs, wprefs = prepared()
        self.assertEqual(instabilities(pairing, mprefs, wprefs), [])
        self.assertIsNone(first_unstable(pairing, mprefs, wprefs))

    def test_enumerates_every_blocking_pair(self):
        _, _, mprefs, wprefs = prepared()
        bad = {"ann": "dee", "dee": "ann", "bob": "eve", "eve": "bob",
               "cid": "fay", "fay": "cid"}
        self.assertEqual(instabilities(bad, mprefs, wprefs),
                         [("ann", "eve"), ("bob", "fay"), ("cid", "dee")])
        self.assertEqual(first_unstable(bad, mprefs, wprefs), ("ann", "eve"))


class TestEnumerate(unittest.TestCase):
    def test_count_is_permutations_of_the_smaller_side(self):
        self.assertEqual(len(enumerate_pairings(MEN, WOMEN)), 6)

    def test_every_plan_covers_everybody(self):
        for plan in enumerate_pairings(MEN, WOMEN):
            self.assertEqual(set(plan), set(MEN) | set(WOMEN))

    def test_unequal_sides_leave_exactly_one_unpaired(self):
        plans = enumerate_pairings(["ann", "bob"], ["dee", "eve", "fay"])
        self.assertEqual(len(plans), 6)
        for plan in plans:
            loose = [w for w in ("dee", "eve", "fay") if plan[w] is None]
            self.assertEqual(len(loose), 1)


class TestAllStable(unittest.TestCase):
    def test_returns_every_stable_matching_in_men_vector_order(self):
        _, _, mprefs, wprefs = prepared()
        stable = all_stable(MEN, WOMEN, mprefs, wprefs)
        self.assertEqual(len(stable), 2)
        self.assertEqual(stable[0]["ann"], "eve")
        self.assertEqual(stable[0]["bob"], "fay")
        self.assertEqual(stable[0]["cid"], "dee")
        self.assertEqual(stable[1]["ann"], "fay")
        self.assertEqual(stable[1]["bob"], "dee")
        self.assertEqual(stable[1]["cid"], "eve")

    def test_first_plan_matches_stable_pairing(self):
        men, women, mprefs, wprefs = prepared()
        stable = all_stable(men, women, mprefs, wprefs)
        self.assertEqual(stable[0], stable_pairing(MEN, WOMEN, MEN_PREFS, WOMEN_PREFS))


class TestStablePairing(unittest.TestCase):
    def test_symmetric_result(self):
        pairing = stable_pairing(MEN, WOMEN, MEN_PREFS, WOMEN_PREFS)
        for man in MEN:
            woman = pairing[man]
            self.assertEqual(pairing[woman], man)

    def test_single_pair(self):
        pairing = stable_pairing(["ann"], ["dee"],
                                 {"ann": ["dee"]}, {"dee": ["ann"]})
        self.assertEqual(pairing, {"ann": "dee", "dee": "ann"})

    def test_one_woman_picks_her_favourite(self):
        pairing = stable_pairing(
            ["ann", "bob"], ["dee"],
            {"ann": ["dee"], "bob": ["dee"]},
            {"dee": ["bob", "ann"]})
        self.assertEqual(pairing["dee"], "bob")
        self.assertIsNone(pairing["ann"])

    def test_men_may_go_unmatched(self):
        pairing = stable_pairing(
            ["ann", "bob", "cid"], ["dee", "eve"],
            {"ann": ["dee"], "bob": ["dee", "eve"], "cid": ["eve"]},
            {"dee": ["ann", "bob", "cid"], "eve": ["bob", "cid", "ann"]})
        unpaired = [m for m in ("ann", "bob", "cid")
                    if pairing[m] is None]
        self.assertEqual(len(unpaired), 1)

    def test_raises_when_no_stable_plan(self):
        with self.assertRaises(UnstableMatching):
            stable_pairing([], ["dee"], {}, {"dee": []})


if __name__ == "__main__":
    unittest.main()
