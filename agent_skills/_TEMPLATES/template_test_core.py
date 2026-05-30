# -*- coding: utf-8 -*-
"""
TEMPLATE — unit test for a Pattern 1 core module.

Copy to `poptools/tests/test_<domain>_core.py` and point it at your real core
file. This template targets template_core.py so it runs as-is (verifies the
template is usable). See CONVENTIONS.md §11.

Key trick: load the core file BY PATH via importlib so we bypass the poptools
package __init__ (which does `import bpy`). Register in sys.modules BEFORE
exec_module, or dataclass annotation resolution under
`from __future__ import annotations` fails.
"""

import sys
import unittest
import importlib.util
from pathlib import Path


# Targets the sibling template_core.py so this file runs as-is from _TEMPLATES/
# (proves the template works). In a real test copied to tests/, use instead:
#   ROOT = Path(__file__).resolve().parents[1]
#   CORE_PATH = ROOT / "core" / "<domain>_core.py"
CORE_PATH = Path(__file__).resolve().parent / "template_core.py"

_spec = importlib.util.spec_from_file_location("example_core_under_test", CORE_PATH)
example_core = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = example_core          # MUST precede exec_module
_spec.loader.exec_module(example_core)


class _FakeObj:
    def __init__(self, name, obj_type="MESH"):
        self.name = name
        self.type = obj_type


class BuildExamplePlanTests(unittest.TestCase):
    def test_plans_new_names(self):
        result = example_core.build_example_plan(
            [_FakeObj("cube")], suffix="_low", existing_names=set()
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.planned,
                         [{"old_name": "cube", "new_name": "cube_low"}])

    def test_skips_non_mesh(self):
        result = example_core.build_example_plan(
            [_FakeObj("lamp", obj_type="LIGHT")], suffix="_low", existing_names=set()
        )
        self.assertFalse(result.ok)
        self.assertEqual(len(result.errors), 1)

    def test_collision_with_existing(self):
        result = example_core.build_example_plan(
            [_FakeObj("cube")], suffix="_low", existing_names={"cube_low"}
        )
        self.assertFalse(result.ok)
        self.assertIn("已存在", result.errors[0])

    def test_empty_input(self):
        result = example_core.build_example_plan([], suffix="_low", existing_names=set())
        self.assertFalse(result.ok)
        self.assertEqual(result.planned, [])


if __name__ == "__main__":
    unittest.main()
