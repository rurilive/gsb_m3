"""包的对外面：导出清单、异常层级、模块归属。"""

import unittest

import taglens
from taglens import errors, scrape


class ExportTest(unittest.TestCase):
    def test_all_names_resolve(self):
        for name in taglens.__all__:
            self.assertTrue(hasattr(taglens, name), name)

    def test_no_duplicates(self):
        self.assertEqual(len(taglens.__all__), len(set(taglens.__all__)))

    def test_helpers_come_from_scrape(self):
        self.assertIs(taglens.extract_text, scrape.extract_text)
        self.assertIs(taglens.strip_tags, scrape.strip_tags)


class ErrorHierarchyTest(unittest.TestCase):
    def test_bad_tag_name_is_subclass(self):
        self.assertTrue(issubclass(errors.BadTagName, errors.TaglensError))

    def test_taglens_error_is_value_error(self):
        self.assertTrue(issubclass(errors.TaglensError, ValueError))


if __name__ == "__main__":
    unittest.main()
