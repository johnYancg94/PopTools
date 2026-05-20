import sys
import importlib.util
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

if "poptools" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "poptools",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["poptools"] = module
    spec.loader.exec_module(module)

from poptools.obj_export_tools import triangulate_mesh


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.mesh.primitive_plane_add()
    original_obj = bpy.context.active_object
    original_obj.name = "OriginalPlane"

    copy_mesh = original_obj.data.copy()
    export_copy = original_obj.copy()
    export_copy.data = copy_mesh
    bpy.context.collection.objects.link(export_copy)

    before_original_faces = len(original_obj.data.polygons)

    triangulate_mesh(export_copy, method="BEAUTY", keep_normals=True)

    after_original_faces = len(original_obj.data.polygons)
    after_copy_faces = len(export_copy.data.polygons)

    assert before_original_faces == 1, before_original_faces
    assert after_original_faces == 1, (
        f"Original mesh was modified during export triangulation: "
        f"before={before_original_faces}, after={after_original_faces}"
    )
    assert after_copy_faces == 2, after_copy_faces


if __name__ == "__main__":
    main()
