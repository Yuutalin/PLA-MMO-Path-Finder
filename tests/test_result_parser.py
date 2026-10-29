import unittest
from pla_mmo.result_parser import result_count, summarize_item


class ResultParserTests(unittest.TestCase):
    def test_counts_list_and_dict_results(self):
        self.assertEqual(result_count([{}, {}]), 2)
        self.assertEqual(result_count({"a": 1}), 1)
        self.assertEqual(result_count(None), 0)

    def test_summarizes_known_aliases_without_dropping_raw_fields(self):
        item = {"species": "Bidoof", "is_shiny": True, "is_alpha": False, "path": [1, 2, 3]}
        summary = summarize_item(item)
        self.assertEqual(summary["title"], "Bidoof")
        self.assertTrue(summary["shiny"])
        self.assertEqual(summary["path"], [1, 2, 3])
        self.assertEqual(summary["fields"], item)


if __name__ == "__main__":
    unittest.main()
