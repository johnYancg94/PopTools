# -*- coding: utf-8 -*-
"""
POPAgent skill wrappers for PopTools export functionality.

These handlers must be called from the Blender main thread because do_export()
internally calls bpy.ops. Use agent_core.main_thread.run_on_main() when
invoking from an async context.
"""

from __future__ import annotations
import bpy
from ..core.export_core import do_export, ExportOptions


def _handler_export_fbx(
    context=None,
    export_path: str = "",
    mode: str = "INDIVIDUAL",
    target_engine: str = "OTHER",
    apply_rot: bool = True,
    apply_scale: bool = True,
    apply_loc: bool = False,
    triangulate: bool = False,
    combine_meshes: bool = False,
) -> dict:
    if context is None:
        context = bpy.context

    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection", "error": "No objects selected."}

    options = ExportOptions(
        export_path=export_path,
        custom_export_path=bool(export_path),
        export_format="FBX",
        fbx_export_mode=mode,
        export_target_engine=target_engine,
        apply_rot=apply_rot,
        apply_scale=apply_scale,
        apply_loc=apply_loc,
        triangulate_before_export=triangulate,
        export_combine_meshes=combine_meshes,
    )
    result = do_export(objects=objects, format="FBX", mode=mode, options=options, context=context)
    return {
        "ok": result.ok,
        "exported_files": result.exported_files,
        "export_dir": result.export_dir,
        "incorrect_names": result.incorrect_names,
        "message": result.message,
        **({"error": result.error} if not result.ok else {}),
    }


def _handler_export_obj(
    context=None,
    export_path: str = "",
    mode: str = "INDIVIDUAL",
    apply_rot: bool = True,
    apply_scale: bool = True,
    triangulate: bool = False,
) -> dict:
    if context is None:
        context = bpy.context

    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection", "error": "No objects selected."}

    options = ExportOptions(
        export_path=export_path,
        custom_export_path=bool(export_path),
        export_format="OBJ",
        fbx_export_mode=mode,
        apply_rot=apply_rot,
        apply_scale=apply_scale,
        triangulate_before_export=triangulate,
    )
    result = do_export(objects=objects, format="OBJ", mode=mode, options=options, context=context)
    return {
        "ok": result.ok,
        "exported_files": result.exported_files,
        "export_dir": result.export_dir,
        "incorrect_names": result.incorrect_names,
        "message": result.message,
        **({"error": result.error} if not result.ok else {}),
    }


def _handler_export_gltf(
    context=None,
    export_path: str = "",
    mode: str = "INDIVIDUAL",
    apply_rot: bool = True,
    apply_scale: bool = True,
    triangulate: bool = False,
) -> dict:
    if context is None:
        context = bpy.context

    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection", "error": "No objects selected."}

    options = ExportOptions(
        export_path=export_path,
        custom_export_path=bool(export_path),
        export_format="GLTF",
        fbx_export_mode=mode,
        apply_rot=apply_rot,
        apply_scale=apply_scale,
        triangulate_before_export=triangulate,
    )
    result = do_export(objects=objects, format="GLTF", mode=mode, options=options, context=context)
    return {
        "ok": result.ok,
        "exported_files": result.exported_files,
        "export_dir": result.export_dir,
        "incorrect_names": result.incorrect_names,
        "message": result.message,
        **({"error": result.error} if not result.ok else {}),
    }


_EXPORT_PARAMS_COMMON = {
    "export_path": {
        "type": "string",
        "description": "Absolute export directory path. Leave empty to use the blend file location.",
    },
    "mode": {
        "type": "string",
        "enum": ["ALL", "INDIVIDUAL", "PARENT", "COLLECTION"],
        "description": "Export mode: ALL exports all selected as one file, INDIVIDUAL exports each object separately, PARENT groups by parent, COLLECTION groups by collection.",
    },
    "apply_rot": {"type": "boolean", "description": "Apply rotation before export."},
    "apply_scale": {"type": "boolean", "description": "Apply scale before export."},
    "triangulate": {"type": "boolean", "description": "Triangulate meshes before export."},
}

EXPORT_FBX = {
    "name": "poptools.export_fbx",
    "description": (
        "Export the currently selected Blender objects as FBX file(s). "
        "Requires objects to be selected first. "
        "Returns exported file paths and the export directory."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_EXPORT_PARAMS_COMMON,
            "target_engine": {
                "type": "string",
                "enum": ["UNITY2023", "OTHER"],
                "description": "Target engine preset (affects axis/scale defaults).",
            },
            "apply_loc": {"type": "boolean", "description": "Apply location before export."},
            "combine_meshes": {"type": "boolean", "description": "Combine all selected meshes into one before export (ALL mode)."},
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_export_fbx,
    "metadata": {
        "modifies_scene": False,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}

EXPORT_OBJ = {
    "name": "poptools.export_obj",
    "description": (
        "Export the currently selected Blender objects as OBJ file(s). "
        "Requires objects to be selected first."
    ),
    "parameters": {
        "type": "object",
        "properties": _EXPORT_PARAMS_COMMON,
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_export_obj,
    "metadata": {
        "modifies_scene": False,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}

EXPORT_GLTF = {
    "name": "poptools.export_gltf",
    "description": (
        "Export the currently selected Blender objects as glTF/GLB file(s). "
        "Requires objects to be selected first."
    ),
    "parameters": {
        "type": "object",
        "properties": _EXPORT_PARAMS_COMMON,
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_export_gltf,
    "metadata": {
        "modifies_scene": False,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}
