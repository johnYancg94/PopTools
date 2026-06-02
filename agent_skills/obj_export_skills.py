# -*- coding: utf-8 -*-
"""
POPAgent skill wrappers for PopTools OBJ batch export utilities.

Pattern 2 — handler temporarily applies agent params to scene props,
calls the existing operator, then restores.  This avoids duplicating the
complex export-copy / modifier / triangulation pipeline.
"""

from __future__ import annotations
import os
import bpy


# ---------------------------------------------------------------------------
# poptools.export_obj_batch
# ---------------------------------------------------------------------------

def _handler_export_obj_batch(
    context=None,
    output_path: str = "",
    scale: float = 1.0,
    coord_up: str = "Y",
    coord_forward: str = "-Z",
    materials: bool = False,
    triangulate: bool = False,
    tri_method: str = "BEAUTY",
    keep_normals: bool = True,
) -> dict:
    if context is None:
        context = bpy.context

    mesh_objects = [o for o in context.selected_objects if o.type == "MESH"]
    if not mesh_objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No mesh objects selected for export."}

    scene_props = context.scene.poptools_props.obj_export_settings

    # ---- save original props ----
    saved = {
        "obj_export_path": scene_props.obj_export_path,
        "obj_export_scale": scene_props.obj_export_scale,
        "obj_export_coord_up": scene_props.obj_export_coord_up,
        "obj_export_coord_forward": scene_props.obj_export_coord_forward,
        "obj_export_materials": scene_props.obj_export_materials,
        "obj_export_triangulate": scene_props.obj_export_triangulate,
        "obj_export_tri_method": scene_props.obj_export_tri_method,
        "obj_export_keep_normals": scene_props.obj_export_keep_normals,
    }

    try:
        # ---- apply agent params ----
        if output_path:
            scene_props.obj_export_path = output_path
        scene_props.obj_export_scale = scale
        scene_props.obj_export_coord_up = coord_up
        scene_props.obj_export_coord_forward = coord_forward
        scene_props.obj_export_materials = materials
        scene_props.obj_export_triangulate = triangulate
        scene_props.obj_export_tri_method = tri_method
        scene_props.obj_export_keep_normals = keep_normals

        # ---- call operator ----
        result = bpy.ops.obj.batch_export()
        if result != {"FINISHED"}:
            return {"ok": False, "error_kind": "export_failed",
                    "error": "obj.batch_export operator returned CANCELLED."}

        export_dir = bpy.path.abspath(scene_props.obj_export_path)
        exported = []
        if os.path.isdir(export_dir):
            exported = [os.path.join(export_dir, f)
                        for f in os.listdir(export_dir) if f.endswith(".obj")]

        return {
            "ok": True,
            "exported_files": exported,
            "export_dir": export_dir,
            "message": f"Exported {len(exported)} OBJ file(s) to {export_dir}.",
        }

    except Exception as exc:
        return {"ok": False, "error_kind": "export_failed", "error": str(exc)}

    finally:
        # ---- restore original props ----
        for k, v in saved.items():
            try:
                setattr(scene_props, k, v)
            except Exception:
                pass


EXPORT_OBJ_BATCH = {
    "name": "poptools.export_obj_batch",
    "description": (
        "Batch-export selected mesh objects as individual OBJ files into the "
        "given directory. Each object is exported with a copy that has "
        "modifiers applied and optional triangulation. "
        "Requires mesh objects to be selected."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Absolute directory path for OBJ output files.",
            },
            "scale": {
                "type": "number",
                "description": "Export scale factor. Default 1.0.",
            },
            "coord_up": {
                "type": "string",
                "enum": ["X", "Y", "Z", "-X", "-Y", "-Z"],
                "description": "Up axis for exported mesh. Default 'Y'.",
            },
            "coord_forward": {
                "type": "string",
                "enum": ["X", "Y", "Z", "-X", "-Y", "-Z"],
                "description": "Forward axis for exported mesh. Default '-Z'.",
            },
            "materials": {
                "type": "boolean",
                "description": "Export material information. Default false.",
            },
            "triangulate": {
                "type": "boolean",
                "description": "Triangulate meshes before export. Default false.",
            },
            "tri_method": {
                "type": "string",
                "enum": ["BEAUTY", "CLIP", "QUAD", "FIXED", "FIXED_ALTERNATE"],
                "description": "Triangulation method. Default 'BEAUTY'.",
            },
            "keep_normals": {
                "type": "boolean",
                "description": "Preserve normals during triangulation. Default true.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_export_obj_batch,
    "metadata": {
        "modifies_scene": False,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}


# ---------------------------------------------------------------------------
# poptools.open_export_dir
# ---------------------------------------------------------------------------

def _handler_open_export_dir(context=None, export_path: str = "") -> dict:
    if context is None:
        context = bpy.context

    if not export_path:
        scene_props = context.scene.poptools_props.obj_export_settings
        export_path = bpy.path.abspath(scene_props.obj_export_path)

    abs_path = os.path.abspath(export_path)
    if not os.path.exists(abs_path):
        return {"ok": False, "error_kind": "path_not_found",
                "error": f"Directory does not exist: {abs_path}"}

    try:
        os.startfile(abs_path)
        return {"ok": True, "message": f"Opened directory: {abs_path}"}
    except Exception as exc:
        return {"ok": False, "error_kind": "external_launch_failed",
                "error": str(exc)}


OPEN_EXPORT_DIR = {
    "name": "poptools.open_export_dir",
    "description": (
        "Open the export directory in the system file explorer. "
        "If no path is given, uses the current OBJ export path setting."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "export_path": {
                "type": "string",
                "description": "Directory path to open. Defaults to current OBJ export path.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_open_export_dir,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": True,
        "undoable": False,
        "requires_confirmation": "always",
    },
}
