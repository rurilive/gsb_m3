"""tabox 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from tabox.reader import CsvReader
from tabox import CsvReader as ExportedCsvReader


class TestCsvReader(unittest.TestCase):
    def test_single_row(self):
        reader = CsvReader("a,b,c")
        self.assertEqual(reader.read(), [["a", "b", "c"]])

    def test_multiple_rows(self):
        reader = CsvReader("a,b\nc,d")
        self.assertEqual(reader.read(), [["a", "b"], ["c", "d"]])

    def test_trailing_newline_ignored(self):
        reader = CsvReader("a,b\nc,d\n")
        self.assertEqual(reader.read(), [["a", "b"], ["c", "d"]])

    def test_empty_text(self):
        reader = CsvReader("")
        self.assertEqual(reader.read(), [])

    def test_double_quoted_field(self):
        reader = CsvReader('a,"b c",d')
        self.assertEqual(reader.read(), [["a", "b c", "d"]])

    def test_single_quotes_are_literal(self):
        reader = CsvReader("a,'b',c")
        self.assertEqual(reader.read(), [["a", "'b'", "c"]])

    def test_text_property(self):
        reader = CsvReader("x,y")
        self.assertEqual(reader.text, "x,y")

    def test_package_exports_csvreader(self):
        self.assertIs(ExportedCsvReader, CsvReader)


if __name__ == "__main__":
    unittest.main()
