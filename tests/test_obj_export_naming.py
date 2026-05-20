import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from obj_export_naming import (
    build_export_identity,
    build_obj_export_options,
    rewrite_obj_group_name,
    resolve_export_mesh_name,
)


class FakeMeshData:
    def __init__(self, name):
        self.name = name


class FakeObject:
    def __init__(self, name, data=None):
        self.name = name
        self.data = data


class ObjExportNamingTests(unittest.TestCase):
    def test_resolve_export_mesh_name_prefers_mesh_data_name(self):
        obj = FakeObject(name="ObjectName", data=FakeMeshData(name="Mesh.Data"))

        result = resolve_export_mesh_name(obj)

        self.assertEqual(result, "Mesh_Data")

    def test_resolve_export_mesh_name_falls_back_to_object_name(self):
        obj = FakeObject(name="Object.Name", data=None)

        result = resolve_export_mesh_name(obj)

        self.assertEqual(result, "Object_Name")

    def test_build_obj_export_options_enables_object_groups(self):
        options = build_obj_export_options(
            export_filepath="C:/tmp/test.obj",
            global_scale=1.0,
            forward_axis="NEGATIVE_Z",
            up_axis="Y",
            export_materials=False,
        )

        self.assertTrue(options["export_object_groups"])
        self.assertFalse(options["export_material_groups"])

    def test_build_export_identity_does_not_force_mesh_data_rename(self):
        obj = FakeObject(name="ObjectName", data=FakeMeshData(name="Mesh.Data"))

        identity = build_export_identity(obj)

        self.assertEqual(identity["object_name"], "Mesh_Data")
        self.assertEqual(identity["file_stem"], "Mesh_Data")
        self.assertFalse(identity["sync_mesh_data_name"])

    def test_rewrite_obj_group_name_replaces_repeated_group_name(self):
        original_text = "# Blender 4.2\ng Cube.002_Cube.002\nv 0 0 0\n"

        result = rewrite_obj_group_name(original_text, "Cube")

        self.assertIn("\ng Cube\n", result)
        self.assertNotIn("Cube.002_Cube.002", result)


if __name__ == "__main__":
    unittest.main()
