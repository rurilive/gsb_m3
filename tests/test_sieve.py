"""primesieve 现有逐数试除行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from primesieve.sieve import Erro, NumberRangeError, Sieve, ValueTypeError


def build_sieve(upper=60):
    return Sieve(upper)


class TestConstruction(unittest.TestCase):
    def test_upper_kept(self):
        s = Sieve(97)
        self.assertEqual(s.upper(), 97)

    def test_zero_upper_allowed(self):
        s = Sieve(0)
        self.assertEqual(s.upper(), 0)

    def test_negative_upper_rejected(self):
        with self.assertRaises(NumberRangeError):
            Sieve(-1)

    def test_bool_upper_rejected(self):
        with self.assertRaises(ValueTypeError):
            Sieve(True)

    def test_non_int_upper_rejected(self):
        with self.assertRaises(ValueTypeError):
            Sieve(2.5)

    def test_range_error_is_erro(self):
        self.assertTrue(issubclass(NumberRangeError, Erro))

    def test_type_error_is_erro(self):
        self.assertTrue(issubclass(ValueTypeError, Erro))


class TestPrimes(unittest.TestCase):
    def test_small_upper_values(self):
        self.assertEqual(Sieve(0).primes(), ())
        self.assertEqual(Sieve(1).primes(), ())
        self.assertEqual(Sieve(2).primes(), (2,))
        self.assertEqual(Sieve(3).primes(), (2, 3))

    def test_primes_up_to_thirty(self):
        self.assertEqual(Sieve(30).primes(),
                         (2, 3, 5, 7, 11, 13, 17, 19, 23, 29))

    def test_prime_upper_included(self):
        self.assertEqual(Sieve(37).primes()[-1], 37)

    def test_is_prime(self):
        s = build_sieve()
        for x in (-5, 0, 1, 4, 9, 100):
            self.assertFalse(s.is_prime(x))
        for x in (2, 3, 17, 37, 59):
            self.assertTrue(s.is_prime(x))

    def test_primes_ascending_no_duplicates(self):
        result = Sieve(120).primes()
        self.assertEqual(list(result), sorted(set(result)))


class TestFactorize(unittest.TestCase):
    def test_factor_one(self):
        self.assertEqual(Sieve(10).factorize(1), ())

    def test_factor_prime(self):
        self.assertEqual(Sieve(10).factorize(97), (97,))

    def test_factor_prime_power(self):
        self.assertEqual(Sieve(10).factorize(128), (2, 2, 2, 2, 2, 2, 2))

    def test_factor_composite(self):
        self.assertEqual(Sieve(10).factorize(720), (2, 2, 2, 2, 3, 3, 5))

    def test_factor_with_large_prime_factor(self):
        self.assertEqual(Sieve(10).factorize(2 * 97), (2, 97))

    def test_factor_zero_rejected(self):
        with self.assertRaises(NumberRangeError):
            Sieve(10).factorize(0)

    def test_factor_negative_rejected(self):
        with self.assertRaises(NumberRangeError):
            Sieve(10).factorize(-6)

    def test_factor_non_int_rejected(self):
        with self.assertRaises(ValueTypeError):
            Sieve(10).factorize(None)

    def test_factorize_all_keeps_order(self):
        s = build_sieve()
        self.assertEqual(s.factorize_all([12, 1, 49]),
                         ((2, 2, 3), (), (7, 7)))

    def test_factorize_all_non_sequence_rejected(self):
        with self.assertRaises(ValueTypeError):
            build_sieve().factorize_all(7)


class TestArithmetic(unittest.TestCase):
    def test_euler_phi_one(self):
        self.assertEqual(Sieve(10).euler_phi(1), 1)

    def test_euler_phi_prime(self):
        self.assertEqual(Sieve(10).euler_phi(97), 96)

    def test_euler_phi_composite(self):
        s = build_sieve()
        self.assertEqual(s.euler_phi(12), 4)
        self.assertEqual(s.euler_phi(36), 12)

    def test_euler_phi_zero_rejected(self):
        with self.assertRaises(NumberRangeError):
            Sieve(10).euler_phi(0)

    def test_count_primes_interval(self):
        s = build_sieve()
        self.assertEqual(s.count_primes(2, 30), 10)
        self.assertEqual(s.count_primes(10, 10), 0)
        self.assertEqual(s.count_primes(0, 1), 0)

    def test_count_primes_degenerate_range(self):
        self.assertEqual(Sieve(10).count_primes(7, 7), 1)

    def test_count_primes_bad_range_rejected(self):
        with self.assertRaises(NumberRangeError):
            build_sieve().count_primes(30, 2)


class TestDeterminism(unittest.TestCase):
    def test_repeated_primes_same_result(self):
        s = build_sieve(80)
        first = s.primes()
        for _ in range(3):
            self.assertEqual(s.primes(), first)

    def test_repeated_factorize_same_result(self):
        s = build_sieve()
        first = s.factorize(360)
        for _ in range(3):
            self.assertEqual(s.factorize(360), first)

    def test_counters_reset_and_grow(self):
        s = build_sieve()
        s.reset_counts()
        self.assertEqual(s.trial_divisions(), 0)
        s.primes()
        after = s.trial_divisions()
        self.assertGreater(after, 0)
        s.reset_counts()
        self.assertEqual(s.trial_divisions(), 0)
        s.primes()
        self.assertEqual(s.trial_divisions(), after)

    def test_two_sieves_do_not_share_state(self):
        a = build_sieve()
        b = build_sieve()
        a.primes()
        self.assertEqual(b.trial_divisions(), 0)


if __name__ == "__main__":
    unittest.main()
