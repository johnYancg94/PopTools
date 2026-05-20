import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generic_model_naming import build_sequential_names, contains_chinese, sanitize_identifier


class GenericModelNamingTests(unittest.TestCase):
    def test_contains_chinese_detects_cjk(self):
        self.assertTrue(contains_chinese("活动类型"))
        self.assertFalse(contains_chinese("eventType"))

    def test_sanitize_identifier_normalizes_english_input(self):
        self.assertEqual(sanitize_identifier("Event Type"), "eventType")
        self.assertEqual(sanitize_identifier("coin_pusher"), "coinPusher")
        self.assertEqual(sanitize_identifier("Tree-House 01"), "treeHouse01")

    def test_build_sequential_names_skips_existing_conflicts(self):
        existing_names = {
            "mesh_coinPusher_smallCoin01",
            "mesh_coinPusher_smallCoin02",
            "mesh_other_smallCoin01",
        }

        result = build_sequential_names(
            activity_type="coinPusher",
            model_name="smallCoin",
            count=2,
            existing_names=existing_names,
        )

        self.assertEqual(result, ["mesh_coinPusher_smallCoin03", "mesh_coinPusher_smallCoin04"])

    def test_build_sequential_names_places_suffix_before_number(self):
        existing_names = {
            "mesh_coinPusher_smallCoin_clean01",
            "mesh_coinPusher_smallCoin_clean02",
        }

        result = build_sequential_names(
            activity_type="coinPusher",
            model_name="smallCoin",
            count=2,
            existing_names=existing_names,
            suffix="clean",
        )

        self.assertEqual(
            result,
            [
                "mesh_coinPusher_smallCoin_clean03",
                "mesh_coinPusher_smallCoin_clean04",
            ],
        )


if __name__ == "__main__":
    unittest.main()
