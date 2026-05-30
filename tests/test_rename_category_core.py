import sys
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# Load rename_category_core.py directly by path to bypass import bpy chain.
# generic_model_naming.py (its dependency) is pure Python (only imports re).
_spec = importlib.util.spec_from_file_location(
    "rename_category_core_under_test", ROOT / "core" / "rename_category_core.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)


class _FakeObj:
    def __init__(self, name, obj_type="MESH"):
        self.name = name
        self.type = obj_type


# ---------------------------------------------------------------------------
# Simple categories (body/hair/tool/animal)
# ---------------------------------------------------------------------------

class CharacterBodyTests(unittest.TestCase):
    def test_basic(self):
        r = _mod.build_rename_plan(
            "character_body", [_FakeObj("cube")], set(),
            body_type="man", serial_number="03", suffix="",
        )
        self.assertTrue(r.ok)
        self.assertEqual(r.planned, [{"old_name": "cube", "new_name": "mesh_characters_man_03"}])

    def test_with_suffix(self):
        r = _mod.build_rename_plan(
            "character_body", [_FakeObj("cube")], set(),
            body_type="woman", serial_number="01", suffix="diff",
        )
        self.assertEqual(r.planned[0]["new_name"], "mesh_characters_woman_01_diff")

    def test_missing_body_type(self):
        r = _mod.build_rename_plan(
            "character_body", [_FakeObj("cube")], set(),
            body_type="", serial_number="01",
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "missing_body_type")


class CharacterHairTests(unittest.TestCase):
    def test_basic(self):
        r = _mod.build_rename_plan(
            "character_hair", [_FakeObj("hair")], set(),
            body_type="kid", serial_number="05",
        )
        self.assertEqual(r.planned[0]["new_name"], "mesh_head_kid_head05")


class CharacterToolTests(unittest.TestCase):
    def test_with_suffix(self):
        r = _mod.build_rename_plan(
            "character_tool", [_FakeObj("sword")], set(),
            body_type="man", serial_number="01", suffix="gold",
        )
        self.assertEqual(r.planned[0]["new_name"], "mesh_buildtools_man_01gold")

    def test_missing_suffix(self):
        r = _mod.build_rename_plan(
            "character_tool", [_FakeObj("sword")], set(),
            body_type="man", serial_number="01", suffix="",
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "missing_suffix")


class AnimalTests(unittest.TestCase):
    def test_basic(self):
        r = _mod.build_rename_plan(
            "animal", [_FakeObj("bird")], set(),
            body_type="bird", serial_number="02",
        )
        self.assertEqual(r.planned[0]["new_name"], "mesh_special_bird_02")


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------

class BuildingTests(unittest.TestCase):
    def test_auto_increment(self):
        objs = [_FakeObj("wall1"), _FakeObj("wall2")]
        r = _mod.build_rename_plan(
            "building", objs, set(),
            building_type="buildpart", island_name="tropical", building_name="hut",
        )
        self.assertTrue(r.ok)
        self.assertEqual(len(r.planned), 2)
        self.assertEqual(r.planned[0]["new_name"], "mesh_buildpart_tropical_hut01")
        self.assertEqual(r.planned[1]["new_name"], "mesh_buildpart_tropical_hut02")

    def test_skips_existing(self):
        r = _mod.build_rename_plan(
            "building", [_FakeObj("obj")], {"mesh_buildpart_island_house01"},
            building_type="buildpart", island_name="island", building_name="house",
        )
        self.assertEqual(r.planned[0]["new_name"], "mesh_buildpart_island_house02")

    def test_missing_params(self):
        r = _mod.build_rename_plan(
            "building", [_FakeObj("obj")], set(),
            building_type="", island_name="", building_name="",
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "missing_building_params")


# ---------------------------------------------------------------------------
# Minigame
# ---------------------------------------------------------------------------

class MinigameTests(unittest.TestCase):
    def test_basic(self):
        r = _mod.build_rename_plan(
            "minigame", [_FakeObj("cube")], set(),
            gameplay="cleanup", scene="bedroom", item_name="toy",
        )
        self.assertEqual(r.planned[0]["new_name"], "mesh_cleanupminigame_bedroom_toy")

    def test_collision_suffix(self):
        r = _mod.build_rename_plan(
            "minigame", [_FakeObj("a"), _FakeObj("b")],
            {"mesh_cleanupminigame_bedroom_toy"},
            gameplay="cleanup", scene="bedroom", item_name="toy",
        )
        self.assertTrue(r.ok)
        self.assertEqual(r.planned[0]["new_name"], "mesh_cleanupminigame_bedroom_toy_01")
        self.assertEqual(r.planned[1]["new_name"], "mesh_cleanupminigame_bedroom_toy_02")

    def test_missing_item_name(self):
        r = _mod.build_rename_plan(
            "minigame", [_FakeObj("cube")], set(),
            gameplay="cleanup", scene="bedroom", item_name="",
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "missing_item_name")


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class GenericTests(unittest.TestCase):
    def test_sequential(self):
        objs = [_FakeObj("a"), _FakeObj("b")]
        r = _mod.build_rename_plan(
            "generic", objs, set(),
            activity_type="event", model_name="gift",
        )
        self.assertTrue(r.ok)
        names = [p["new_name"] for p in r.planned]
        self.assertEqual(names, ["mesh_event_gift01", "mesh_event_gift02"])

    def test_no_mesh_selected(self):
        r = _mod.build_rename_plan(
            "generic", [_FakeObj("lamp", "LIGHT")], set(),
            activity_type="event", model_name="gift",
        )
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "no_selection")


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

class MiscTests(unittest.TestCase):
    def test_invalid_category(self):
        r = _mod.build_rename_plan("nonexistent", [], set())
        self.assertFalse(r.ok)
        self.assertEqual(r.error_kind, "invalid_category")

    def test_skips_non_mesh(self):
        r = _mod.build_rename_plan(
            "character_body", [_FakeObj("lamp", "LIGHT")], set(),
            body_type="man", serial_number="01",
        )
        self.assertFalse(r.ok)
        self.assertEqual(len(r.errors), 1)
        self.assertIn("不是网格", r.errors[0])

    def test_empty_input(self):
        r = _mod.build_rename_plan(
            "character_body", [], set(),
            body_type="man", serial_number="01",
        )
        self.assertFalse(r.ok)

    def test_collision_detection(self):
        r = _mod.build_rename_plan(
            "character_body", [_FakeObj("cube")], {"mesh_characters_man_01"},
            body_type="man", serial_number="01",
        )
        self.assertFalse(r.ok)
        self.assertIn("已存在", r.errors[0])


if __name__ == "__main__":
    unittest.main()
