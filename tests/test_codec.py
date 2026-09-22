import os
import tempfile
import unittest

from qsketch import FormatError, SampleSet, ShardSet, codec


class SampleSetRoundTripTest(unittest.TestCase):
    def test_values_survive(self):
        samples = SampleSet([3, 1.5, 2])
        loaded = codec.load(codec.dump(samples))
        self.assertIsInstance(loaded, SampleSet)
        self.assertEqual(loaded.values(), samples.values())

    def test_quantiles_survive(self):
        samples = SampleSet([float(i) / 7 for i in range(30)])
        loaded = codec.load(codec.dump(samples))
        for q in (0.0, 0.1, 0.5, 0.99, 1.0):
            self.assertEqual(loaded.quantile(q), samples.quantile(q))

    def test_dump_is_byte_stable(self):
        samples = SampleSet([1, 2, 3])
        self.assertEqual(codec.dump(samples), codec.dump(samples))

    def test_dump_rejects_other_types(self):
        with self.assertRaises(FormatError):
            codec.dump([1, 2, 3])


class ShardSetRoundTripTest(unittest.TestCase):
    def _build(self):
        shards = ShardSet()
        for name, value in (("b", 2), ("a", 1), ("a", 3)):
            shards.add(name, value)
        return shards

    def test_structure_survives(self):
        shards = self._build()
        loaded = codec.load(codec.dump(shards))
        self.assertIsInstance(loaded, ShardSet)
        self.assertEqual(loaded.names(), shards.names())
        self.assertEqual(loaded.values("a"), shards.values("a"))
        self.assertEqual(loaded.count(), shards.count())

    def test_quantiles_survive(self):
        shards = self._build()
        loaded = codec.load(codec.dump(shards))
        for q in (0.0, 0.25, 0.5, 1.0):
            self.assertEqual(loaded.quantile(q), shards.quantile(q))

    def test_loaded_copy_is_independent(self):
        shards = self._build()
        loaded = codec.load(codec.dump(shards))
        loaded.add("a", 100)
        self.assertEqual(shards.count("a"), 2)


class BadPayloadTest(unittest.TestCase):
    def test_not_bytes(self):
        with self.assertRaises(FormatError):
            codec.load("not bytes")

    def test_not_json(self):
        with self.assertRaises(FormatError):
            codec.load(b"{not json")

    def test_not_an_object(self):
        with self.assertRaises(FormatError):
            codec.load(b"[1,2,3]")

    def test_missing_fmt(self):
        with self.assertRaises(FormatError):
            codec.load(b'{"kind":"sample_set","samples":[]}')

    def test_unknown_fmt(self):
        with self.assertRaises(FormatError):
            codec.load(b'{"fmt":99,"kind":"sample_set","samples":[]}')

    def test_unknown_kind(self):
        with self.assertRaises(FormatError):
            codec.load(b'{"fmt":1,"kind":"wat","samples":[]}')

    def test_samples_not_a_list(self):
        with self.assertRaises(FormatError):
            codec.load(b'{"fmt":1,"kind":"sample_set","samples":{"a":1}}')

    def test_bad_sample_value(self):
        for raw in (b'"x"', b"null", b"true", b"[]"):
            with self.assertRaises(FormatError):
                codec.load(b'{"fmt":1,"kind":"sample_set","samples":[' + raw + b"]}")

    def test_shards_missing(self):
        with self.assertRaises(FormatError):
            codec.load(b'{"fmt":1,"kind":"shard_set"}')

    def test_shard_values_not_a_list(self):
        with self.assertRaises(FormatError):
            codec.load(b'{"fmt":1,"kind":"shard_set","shards":{"a":1}}')


class FileTest(unittest.TestCase):
    def test_save_and_read(self):
        samples = SampleSet([1, 2.5, 4])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "samples.json")
            codec.save(samples, path)
            loaded = codec.read(path)
        self.assertEqual(loaded.values(), samples.values())

    def test_read_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                codec.read(os.path.join(tmp, "nope.json"))


if __name__ == "__main__":
    unittest.main()
