import sys
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Load core/retex_core.py directly by path: it imports no bpy, so we bypass the
# poptools top-level package __init__ (which does `import bpy`) entirely.
_spec = importlib.util.spec_from_file_location(
    "retex_core_under_test", ROOT / "core" / "retex_core.py"
)
retex_core = importlib.util.module_from_spec(_spec)
# Register before exec: dataclass annotation resolution under
# `from __future__ import annotations` looks the module up in sys.modules.
sys.modules[_spec.name] = retex_core
_spec.loader.exec_module(retex_core)


class _FakeUVLayers:
    def __init__(self, count):
        self._count = count

    def __len__(self):
        return self._count


class _FakeData:
    def __init__(self, uv_count):
        self.uv_layers = _FakeUVLayers(uv_count)


class _FakeObj:
    def __init__(self, name, obj_type="MESH", uv_count=1):
        self.name = name
        self.type = obj_type
        self.data = _FakeData(uv_count)


class CheckDuplicateUVsTests(unittest.TestCase):
    def test_flags_objects_with_multiple_uv_maps(self):
        objs = [_FakeObj("a", uv_count=2), _FakeObj("b", uv_count=1),
                _FakeObj("c", uv_count=3)]
        result = retex_core.check_duplicate_uvs(objs)
        self.assertTrue(result.ok)
        self.assertEqual(result.objects_with_multiple_uvs, ["a", "c"])

    def test_ignores_non_mesh(self):
        objs = [_FakeObj("light", obj_type="LIGHT", uv_count=5)]
        result = retex_core.check_duplicate_uvs(objs)
        self.assertEqual(result.objects_with_multiple_uvs, [])

    def test_empty_scene_reports_clean(self):
        result = retex_core.check_duplicate_uvs([])
        self.assertTrue(result.ok)
        self.assertEqual(result.objects_with_multiple_uvs, [])


class _RenameObj:
    def __init__(self, name):
        self.name = name


class BuildSmartRenameTests(unittest.TestCase):
    def test_letter_first_pattern_with_zero_pad(self):
        result = retex_core.build_smart_rename(
            [_RenameObj("b3")], item_land="sky", existing_names=set()
        )
        self.assertTrue(result.ok)
        self.assertEqual(
            result.renamed, [{"old_name": "b3", "new_name": "mesh_item_sky_balloon_03"}]
        )
        self.assertEqual(result.errors, [])

    def test_number_first_pattern(self):
        result = retex_core.build_smart_rename(
            [_RenameObj("12h")], item_land="sky", existing_names=set()
        )
        self.assertEqual(
            result.renamed, [{"old_name": "12h", "new_name": "mesh_item_sky_hand_12"}]
        )

    def test_unknown_prefix_is_reported(self):
        result = retex_core.build_smart_rename(
            [_RenameObj("z9")], item_land="sky", existing_names=set()
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.renamed, [])
        self.assertEqual(len(result.errors), 1)
        self.assertIn("未知类型前缀", result.errors[0])

    def test_no_letter_number_combo_is_reported(self):
        result = retex_core.build_smart_rename(
            [_RenameObj("plainname")], item_land="sky", existing_names=set()
        )
        # "plainname" -> letters 'plainname' but no digits -> no match
        self.assertFalse(result.ok)
        self.assertIn("未找到有效", result.errors[0])

    def test_collision_with_existing_name(self):
        result = retex_core.build_smart_rename(
            [_RenameObj("p1")], item_land="sky",
            existing_names={"mesh_item_sky_prop_01"},
        )
        self.assertFalse(result.ok)
        self.assertIn("已存在", result.errors[0])

    def test_collision_within_batch(self):
        # "p1" -> '01', "p01" -> '01'; both map to mesh_item_sky_prop_01.
        result = retex_core.build_smart_rename(
            [_RenameObj("p1"), _RenameObj("p01")], item_land="sky",
            existing_names=set(),
        )
        self.assertEqual(len(result.renamed), 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("已存在", result.errors[0])


if __name__ == "__main__":
    unittest.main()
