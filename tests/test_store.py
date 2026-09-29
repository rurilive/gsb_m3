"""colstore 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from colstore.column import Column
from colstore.store import Store


def build_store():
    return Store(
        [
            Column("id", [1, 2, 3, 4]),
            Column("city", [1, 1, 2, 2]),
            Column("amount", [30, 10, 20, 40]),
        ]
    )


class TestColumn(unittest.TestCase):
    def test_name_and_length(self):
        col = Column("id", [1, 2, 3])
        self.assertEqual(col.name, "id")
        self.assertEqual(len(col), 3)

    def test_get_and_to_list(self):
        col = Column("id", [7, 8, 9])
        self.assertEqual(col.get(0), 7)
        self.assertEqual(col.get(2), 9)
        self.assertEqual(col.to_list(), [7, 8, 9])

    def test_get_out_of_range(self):
        col = Column("id", [1])
        with self.assertRaises(IndexError):
            col.get(1)

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            Column("", [1])

    def test_non_int_value_rejected(self):
        with self.assertRaises(ValueError):
            Column("id", [1, "x"])

    def test_bool_value_rejected(self):
        with self.assertRaises(ValueError):
            Column("id", [1, True])

    def test_empty_column_allowed(self):
        col = Column("id", [])
        self.assertEqual(len(col), 0)
        self.assertEqual(col.to_list(), [])

    def test_source_values_not_aliased(self):
        source = [1, 2, 3]
        col = Column("id", source)
        source.append(4)
        self.assertEqual(len(col), 3)

    def test_storage_size_is_length(self):
        col = Column("id", [1, 2, 3, 4])
        self.assertEqual(col.storage_size(), 4)


class TestStore(unittest.TestCase):
    def test_column_names_and_rows(self):
        st = build_store()
        self.assertEqual(st.column_names, ("id", "city", "amount"))
        self.assertEqual(st.num_rows(), 4)

    def test_get_column(self):
        st = build_store()
        self.assertEqual(st.get_column("city").name, "city")

    def test_get_column_missing(self):
        st = build_store()
        with self.assertRaises(ValueError):
            st.get_column("nope")

    def test_get_value_and_row(self):
        st = build_store()
        self.assertEqual(st.get_value("amount", 2), 20)
        self.assertEqual(
            st.get_row(0), {"id": 1, "city": 1, "amount": 30}
        )

    def test_scan_returns_copy(self):
        st = build_store()
        out = st.scan("amount")
        out.append(999)
        self.assertEqual(st.scan("amount"), [30, 10, 20, 40])

    def test_empty_store_rejected(self):
        with self.assertRaises(ValueError):
            Store([])

    def test_non_column_rejected(self):
        with self.assertRaises(ValueError):
            Store([[1, 2, 3]])

    def test_duplicate_column_rejected(self):
        with self.assertRaises(ValueError):
            Store([Column("id", [1]), Column("id", [2])])

    def test_ragged_columns_rejected(self):
        with self.assertRaises(ValueError):
            Store([Column("id", [1, 2]), Column("city", [1])])

    def test_storage_size_sums_columns(self):
        st = build_store()
        self.assertEqual(st.storage_size(), 12)


if __name__ == "__main__":
    unittest.main()