"""bitidx 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from bitidx.recordset import RecordSet


def build_set():
    return RecordSet(
        {
            "id": [1, 2, 3, 4],
            "city": [1, 1, 2, 2],
            "amount": [30, 10, 20, 40],
        }
    )


class TestRecordSet(unittest.TestCase):
    def test_column_names_and_rows(self):
        rs = build_set()
        self.assertEqual(rs.column_names, ("id", "city", "amount"))
        self.assertEqual(rs.num_rows(), 4)

    def test_get_value(self):
        rs = build_set()
        self.assertEqual(rs.get_value("amount", 2), 20)

    def test_get_value_missing_column(self):
        rs = build_set()
        with self.assertRaises(ValueError):
            rs.get_value("nope", 0)

    def test_get_row(self):
        rs = build_set()
        self.assertEqual(rs.get_row(1), {"id": 2, "city": 1, "amount": 10})

    def test_scan_returns_copy(self):
        rs = build_set()
        out = rs.scan("amount")
        out.append(999)
        self.assertEqual(rs.scan("amount"), [30, 10, 20, 40])

    def test_empty_set_rejected(self):
        with self.assertRaises(ValueError):
            RecordSet({})

    def test_non_dict_rejected(self):
        with self.assertRaises(ValueError):
            RecordSet([("id", [1, 2])])

    def test_empty_column_name_rejected(self):
        with self.assertRaises(ValueError):
            RecordSet({"": [1, 2]})

    def test_non_int_value_rejected(self):
        with self.assertRaises(ValueError):
            RecordSet({"id": [1, "x"]})

    def test_bool_value_rejected(self):
        with self.assertRaises(ValueError):
            RecordSet({"id": [1, True]})

    def test_ragged_columns_rejected(self):
        with self.assertRaises(ValueError):
            RecordSet({"id": [1, 2], "city": [1]})

    def test_select_matches_scan(self):
        rs = build_set()
        self.assertEqual(rs.select("city", 1), [0, 1])
        self.assertEqual(rs.select("city", 2), [2, 3])

    def test_select_no_hit_is_empty(self):
        rs = build_set()
        self.assertEqual(rs.select("amount", 99), [])

    def test_select_missing_column(self):
        rs = build_set()
        with self.assertRaises(ValueError):
            rs.select("nope", 1)

    def test_insert_appends_row(self):
        rs = build_set()
        row = rs.insert({"id": 5, "city": 2, "amount": 50})
        self.assertEqual(row, 4)
        self.assertEqual(rs.num_rows(), 5)
        self.assertEqual(rs.get_row(4), {"id": 5, "city": 2, "amount": 50})

    def test_insert_missing_field_rejected(self):
        rs = build_set()
        with self.assertRaises(ValueError):
            rs.insert({"id": 5, "city": 2})

    def test_insert_non_int_rejected(self):
        rs = build_set()
        with self.assertRaises(ValueError):
            rs.insert({"id": 5, "city": 2, "amount": "x"})

    def test_delete_shifts_later_rows(self):
        rs = build_set()
        rs.delete(1)
        self.assertEqual(rs.num_rows(), 3)
        self.assertEqual(rs.scan("id"), [1, 3, 4])
        self.assertEqual(rs.get_row(1), {"id": 3, "city": 2, "amount": 20})

    def test_delete_out_of_range(self):
        rs = build_set()
        with self.assertRaises(IndexError):
            rs.delete(4)

    def test_source_columns_not_aliased(self):
        source = [1, 2, 3]
        rs = RecordSet({"id": source})
        source.append(4)
        self.assertEqual(rs.num_rows(), 3)


if __name__ == "__main__":
    unittest.main()
