import sys
import unittest
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "texname_core_under_test", ROOT / "core" / "texname_core.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)


# ---------------------------------------------------------------------------
# build_texture_name
# ---------------------------------------------------------------------------

class BuildTextureNameTests(unittest.TestCase):
    def test_mesh_prefix_replaced(self):
        self.assertEqual(
            _mod.build_texture_name("mesh_character_01"),
            "tex_character_01",
        )

    def test_tex_prefix_unchanged(self):
        self.assertEqual(
            _mod.build_texture_name("tex_existing"),
            "tex_existing",
        )

    def test_other_prefix_gets_tex(self):
        self.assertEqual(
            _mod.build_texture_name("cube"),
            "tex_cube",
        )

    def test_no_replace_prefix(self):
        self.assertEqual(
            _mod.build_texture_name("mesh_cube", replace_prefix=False),
            "mesh_cube",
        )

    def test_with_suffix(self):
        self.assertEqual(
            _mod.build_texture_name("mesh_cube", texture_suffix="normal"),
            "tex_cube_normal",
        )

    def test_suffix_with_no_replace(self):
        self.assertEqual(
            _mod.build_texture_name("cube", replace_prefix=False, texture_suffix="albedo"),
            "cube_albedo",
        )


# ---------------------------------------------------------------------------
# plan_texture_renames — fakes
# ---------------------------------------------------------------------------

class _FakeImage:
    def __init__(self, name, filepath):
        self.name = name
        self.filepath = filepath


class _FakeNode:
    def __init__(self, node_type, image=None):
        self.type = node_type
        self.image = image


class _FakeNodeTree:
    def __init__(self, nodes):
        self.nodes = nodes


class _FakeMaterial:
    def __init__(self, node_tree):
        self.node_tree = node_tree


class _FakeSlot:
    def __init__(self, material):
        self.material = material


class _FakeObj:
    def __init__(self, name, slots=None):
        self.name = name
        self.material_slots = slots or []


class PlanTextureRenamesTests(unittest.TestCase):
    def test_no_objects(self):
        r = _mod.plan_texture_renames([])
        self.assertFalse(r.ok)

    def test_no_material_slots(self):
        r = _mod.plan_texture_renames([_FakeObj("cube")])
        self.assertFalse(r.ok)

    def test_no_tex_image_nodes(self):
        node = _FakeNode("BSDF_PRINCIPLED")
        mat = _FakeMaterial(_FakeNodeTree([node]))
        obj = _FakeObj("cube", [_FakeSlot(mat)])
        r = _mod.plan_texture_renames([obj])
        self.assertFalse(r.ok)

    def test_tex_image_with_file(self):
        image = _FakeImage("old_name", "/textures/mesh_cube_01.png")
        node = _FakeNode("TEX_IMAGE", image)
        mat = _FakeMaterial(_FakeNodeTree([node]))
        obj = _FakeObj("cube_01", [_FakeSlot(mat)])
        r = _mod.plan_texture_renames([obj])
        self.assertTrue(r.ok)
        self.assertEqual(len(r.planned), 1)
        entry = r.planned[0]
        self.assertEqual(entry["new_tex_name"], "tex_cube_01")
        self.assertEqual(entry["old_path"], "/textures/mesh_cube_01.png")
        self.assertIn("tex_cube_01", entry["new_path"])

    def test_skips_images_without_filepath(self):
        image = _FakeImage("name", "")
        node = _FakeNode("TEX_IMAGE", image)
        mat = _FakeMaterial(_FakeNodeTree([node]))
        obj = _FakeObj("cube", [_FakeSlot(mat)])
        r = _mod.plan_texture_renames([obj])
        self.assertFalse(r.ok)

    def test_with_suffix(self):
        image = _FakeImage("name", "/tex/old.png")
        node = _FakeNode("TEX_IMAGE", image)
        mat = _FakeMaterial(_FakeNodeTree([node]))
        obj = _FakeObj("mesh_cube", [_FakeSlot(mat)])
        r = _mod.plan_texture_renames([obj], texture_suffix="normal")
        self.assertTrue(r.ok)
        self.assertEqual(r.planned[0]["new_tex_name"], "tex_cube_normal")

    def test_no_replace_prefix(self):
        image = _FakeImage("name", "/tex/old.png")
        node = _FakeNode("TEX_IMAGE", image)
        mat = _FakeMaterial(_FakeNodeTree([node]))
        obj = _FakeObj("mesh_cube", [_FakeSlot(mat)])
        r = _mod.plan_texture_renames([obj], replace_prefix=False)
        self.assertTrue(r.ok)
        self.assertEqual(r.planned[0]["new_tex_name"], "mesh_cube")

    def test_multiple_objects(self):
        objs = []
        for name in ["mesh_a", "mesh_b"]:
            image = _FakeImage("img", f"/tex/{name}.png")
            node = _FakeNode("TEX_IMAGE", image)
            mat = _FakeMaterial(_FakeNodeTree([node]))
            objs.append(_FakeObj(name, [_FakeSlot(mat)]))
        r = _mod.plan_texture_renames(objs)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.planned), 2)


class CoerceBoolTests(unittest.TestCase):
    def test_real_bools_pass_through(self):
        self.assertTrue(_mod.coerce_bool(True))
        self.assertFalse(_mod.coerce_bool(False))

    def test_falsey_strings(self):
        for s in ("false", "False", "0", "no", "off", "", "  FALSE  "):
            self.assertFalse(_mod.coerce_bool(s), s)

    def test_truthy_strings(self):
        for s in ("true", "True", "1", "yes", "on"):
            self.assertTrue(_mod.coerce_bool(s), s)

    def test_unknown_string_uses_default(self):
        self.assertTrue(_mod.coerce_bool("maybe", default=True))
        self.assertFalse(_mod.coerce_bool("maybe", default=False))

    def test_none_uses_default(self):
        self.assertTrue(_mod.coerce_bool(None, default=True))
        self.assertFalse(_mod.coerce_bool(None, default=False))


if __name__ == "__main__":
    unittest.main()
