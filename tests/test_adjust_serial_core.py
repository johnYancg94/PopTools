import sys
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "adjust_serial_core_under_test", ROOT / "core" / "adjust_serial_core.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)


class AdjustSerialTests(unittest.TestCase):
    def test_increment(self):
        r = _mod.adjust_serial("01", delta=1)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "02")
        self.assertEqual(r.old_value, 1)
        self.assertEqual(r.new_value, 2)

    def test_decrement(self):
        r = _mod.adjust_serial("05", delta=-2)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "03")

    def test_floor_clamp(self):
        r = _mod.adjust_serial("01", delta=-5, min_value=1)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "01")
        self.assertEqual(r.new_value, 1)

    def test_custom_min_value(self):
        r = _mod.adjust_serial("03", delta=-1, min_value=0)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "02")

    def test_zero_pad_false(self):
        r = _mod.adjust_serial("5", delta=1, zero_pad=False)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "6")

    def test_invalid_input(self):
        r = _mod.adjust_serial("abc", delta=1)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "invalid_serial")

    def test_empty_string(self):
        r = _mod.adjust_serial("", delta=1)
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "invalid_serial")

    def test_large_delta(self):
        r = _mod.adjust_serial("01", delta=99)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "100")

    def test_string_delta_coerced(self):
        r = _mod.adjust_serial("01", delta="-1", min_value=1)
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "01")

    def test_string_min_value_coerced(self):
        r = _mod.adjust_serial("05", delta=-10, min_value="3")
        self.assertTrue(r.ok)
        self.assertEqual(r.new_value_str, "03")

    def test_non_numeric_delta_rejected(self):
        r = _mod.adjust_serial("01", delta="abc")
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "invalid_arguments")

    def test_non_numeric_min_value_rejected(self):
        r = _mod.adjust_serial("01", delta=1, min_value="xyz")
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "invalid_arguments")


if __name__ == "__main__":
    unittest.main()
