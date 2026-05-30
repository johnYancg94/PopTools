# -*- coding: utf-8 -*-
"""
Pure-parameter export entry point.

Wraps MultiExport logic with explicit parameters instead of reading
context.scene.poptools_props. All bpy.ops calls remain (they cannot
be avoided for mesh processing), so this MUST be called from the
Blender main thread — use agent_core.main_thread.run_on_main().

Usage:
    result = do_export(
        objects=bpy.context.selected_objects,
        format="FBX",
        mode="INDIVIDUAL",
        options=ExportOptions(...),
        context=bpy.context,
    )
"""

from __future__ import annotations
import bpy
import os
import math
from dataclasses import dataclass, field
from datetime import datetime
from .. import utils
from mathutils import Vector


@dataclass
class ExportOptions:
    # Path
    export_path: str = ""           # explicit path; empty = derive from blend file
    custom_export_path: bool = False

    # Format / mode
    export_format: str = "FBX"      # "FBX" | "OBJ" | "GLTF"
    fbx_export_mode: str = "INDIVIDUAL"  # "ALL" | "INDIVIDUAL" | "PARENT" | "COLLECTION"
    export_target_engine: str = "OTHER"  # "UNITY2023" | "OTHER"

    # Transforms
    apply_rot: bool = True
    apply_scale: bool = True
    apply_loc: bool = False
    apply_rot_rotated: bool = False

    # Mesh processing
    delete_mats_before_export: bool = False
    triangulate_before_export: bool = False
    export_combine_meshes: bool = False

    # ALL mode
    set_custom_fbx_name: bool = False
    custom_fbx_name: str = ""


@dataclass
class ExportResult:
    ok: bool
    exported_files: list[str] = field(default_factory=list)
    export_dir: str = ""
    incorrect_names: list[str] = field(default_factory=list)
    message: str = ""
    error: str = ""


_EXPORT_SETTING_FIELDS = (
    "fbx_export_mode",
    "export_format",
    "export_target_engine",
    "apply_rot",
    "apply_scale",
    "apply_loc",
    "apply_rot_rotated",
    "delete_mats_before_export",
    "export_combine_meshes",
    "triangulate_before_export",
    "set_custom_fbx_name",
    "custom_fbx_name",
)


def _get_scene_export_settings(context):
    props = getattr(context.scene, "poptools_props", None)
    return getattr(props, "export_tools_settings", None) if props else None


def _snapshot_scene_export_settings(context) -> dict | None:
    settings = _get_scene_export_settings(context)
    if settings is None:
        return None
    return {field: getattr(settings, field) for field in _EXPORT_SETTING_FIELDS}


def _restore_scene_export_settings(context, snapshot: dict | None) -> None:
    if snapshot is None:
        return
    settings = _get_scene_export_settings(context)
    if settings is None:
        return
    for field, value in snapshot.items():
        setattr(settings, field, value)


def _apply_options_to_scene_export_settings(context, options: ExportOptions) -> None:
    settings = _get_scene_export_settings(context)
    if settings is None:
        return
    target_engine = options.export_target_engine
    if target_engine == "OTHER":
        target_engine = "3DCOAT"
    settings.fbx_export_mode = options.fbx_export_mode
    settings.export_format = options.export_format
    settings.export_target_engine = target_engine
    settings.apply_rot = options.apply_rot
    settings.apply_scale = options.apply_scale
    settings.apply_loc = options.apply_loc
    settings.apply_rot_rotated = options.apply_rot_rotated
    settings.delete_mats_before_export = options.delete_mats_before_export
    settings.export_combine_meshes = options.export_combine_meshes
    settings.triangulate_before_export = options.triangulate_before_export
    settings.set_custom_fbx_name = options.set_custom_fbx_name
    settings.custom_fbx_name = options.custom_fbx_name


def _set_cursor_to_world_origin(context) -> None:
    context.scene.cursor.location = (0.0, 0.0, 0.0)


def _set_cursor_to_selection_center(context) -> None:
    selected = list(context.selected_objects)
    if not selected:
        return
    center = Vector((0.0, 0.0, 0.0))
    for obj in selected:
        center += obj.matrix_world.translation
    context.scene.cursor.location = center / len(selected)


def _move_selection_center_to_cursor(context) -> None:
    selected = list(context.selected_objects)
    if not selected:
        return
    center = Vector((0.0, 0.0, 0.0))
    for obj in selected:
        center += obj.matrix_world.translation
    delta = context.scene.cursor.location - (center / len(selected))
    for obj in selected:
        obj.location += delta


def _resolve_export_path(options: ExportOptions) -> tuple[bool, str]:
    """Return (ok, path). Validates and creates the directory."""
    if options.custom_export_path:
        if not options.export_path:
            return False, "Export Path can't be empty"
        resolved = os.path.realpath(bpy.path.abspath(options.export_path))
        if not os.path.exists(resolved):
            return False, f"Directory for export does not exist: {resolved}"
        return True, resolved + "/"

    if not bpy.data.filepath:
        return False, "Blend file is not saved. Use custom_export_path=True with an explicit export_path."

    fmt = options.export_format
    path = bpy.path.abspath(f"//{fmt}s/")
    if not os.path.exists(path):
        os.makedirs(path)
    return True, path


def do_export(
    objects: list,
    format: str = "FBX",
    mode: str = "INDIVIDUAL",
    options: ExportOptions | None = None,
    context=None,
) -> ExportResult:
    """Export objects with the given format and mode.

    Must be called from the Blender main thread.
    objects: list of bpy.types.Object to export.
    format:  "FBX" | "OBJ" | "GLTF"
    mode:    "ALL" | "INDIVIDUAL" | "PARENT" | "COLLECTION"
    """
    if context is None:
        context = bpy.context
    if options is None:
        options = ExportOptions()

    # Unify format/mode into options so helpers don't need separate args.
    options.export_format = format
    options.fbx_export_mode = mode

    start_time = datetime.now()
    incorrect_names: list[str] = []
    exported_files: list[str] = []

    # Validate ALL-mode custom name.
    if mode == "ALL" and options.set_custom_fbx_name and not options.custom_fbx_name:
        return ExportResult(ok=False, error="Custom Name can't be empty")

    ok, path_or_err = _resolve_export_path(options)
    if not ok:
        return ExportResult(ok=False, error=path_or_err)
    path = path_or_err

    # ---- Save scene state ----
    start_selected = list(context.selected_objects)
    start_active = context.active_object
    current_selected = list(objects)
    exp_objects: list = []
    duplicated_data: list[str] = []
    export_settings_snapshot = _snapshot_scene_export_settings(context)
    _apply_options_to_scene_export_settings(context, options)

    saved_cursor_loc = context.scene.cursor.location.copy()
    saved_pivot_point = context.scene.tool_settings.transform_pivot_point
    saved_pivot_align = context.scene.tool_settings.use_transform_pivot_point_align
    if saved_pivot_align:
        context.scene.tool_settings.use_transform_pivot_point_align = False

    active_name = start_active.name if start_active else ""

    try:
        # Filter: keep MESH, EMPTY, ARMATURE, CURVE, FONT only.
        bpy.ops.object.select_all(action="DESELECT")
        for obj in current_selected:
            if obj.type in {"MESH", "EMPTY", "ARMATURE", "CURVE", "FONT"}:
                obj.select_set(True)
        current_selected = list(context.selected_objects)

        # Mark originals with _ex suffix so we can find them after duplicate.
        for obj in current_selected:
            obj.name += "_ex"
            if obj.type in {"MESH", "ARMATURE"}:
                obj.data.name += "_ex"

        # Duplicate for export processing.
        bpy.ops.object.duplicate()
        exp_objects = list(context.selected_objects)

        # make_single_user
        if options.export_target_engine == "UNITY2023" and format == "FBX":
            if options.export_combine_meshes:
                bpy.ops.object.make_single_user(
                    type="SELECTED_OBJECTS", object=True, obdata=True
                )
        else:
            bpy.ops.object.make_single_user(
                type="SELECTED_OBJECTS", object=True, obdata=True
            )

        # Apply/remove modifiers per object.
        for obj in exp_objects:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            context.view_layer.objects.active = obj

            if obj.type != "EMPTY":
                for mod in reversed(obj.modifiers):
                    if not (mod.show_viewport and mod.show_render):
                        obj.modifiers.remove(mod)

            if options.export_target_engine == "UNITY2023" and format == "FBX":
                if (obj.type == "MESH" and obj.data.users < 2) or (
                    mode != "INDIVIDUAL" and options.export_combine_meshes
                ):
                    for mod in obj.modifiers:
                        if mod.type != "ARMATURE":
                            try:
                                bpy.ops.object.modifier_apply(modifier=mod.name)
                            except Exception:
                                bpy.ops.object.modifier_remove(modifier=mod.name)
                elif obj.type != "EMPTY":
                    bpy.ops.object.convert(target="MESH")
            else:
                if obj.type == "MESH":
                    for mod in obj.modifiers:
                        if mod.type != "ARMATURE":
                            try:
                                bpy.ops.object.modifier_apply(modifier=mod.name)
                            except Exception:
                                bpy.ops.object.modifier_remove(modifier=mod.name)
                elif obj.type != "EMPTY":
                    bpy.ops.object.convert(target="MESH")

        # Strip _ex.001 from duplicated names.
        for obj in exp_objects:
            obj.name = obj.name[:-7]
            if obj.type in {"MESH", "ARMATURE"}:
                obj.data.name = obj.name

        # Delete materials (optional).
        if options.delete_mats_before_export:
            for obj in exp_objects:
                if obj.type == "MESH" and obj.data.materials:
                    for i in reversed(range(len(obj.data.materials))):
                        context.object.active_material_index = i
                        obj.data.materials.pop(index=i)

        # Triangulate (optional).
        if options.triangulate_before_export:
            for obj in exp_objects:
                if obj.type == "MESH":
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    bpy.ops.object.mode_set(mode="EDIT")
                    bpy.ops.mesh.reveal()
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.mesh.quads_convert_to_tris(
                        quad_method="BEAUTY", ngon_method="BEAUTY"
                    )
                    bpy.ops.mesh.select_all(action="DESELECT")
                    bpy.ops.object.mode_set(mode="OBJECT")

        # Select all exp_objects.
        for obj in exp_objects:
            obj.select_set(True)

        # Apply transforms.
        if (options.export_target_engine == "UNITY2023" and format == "FBX") or format == "GLTF":
            cur_active = context.view_layer.objects.active
            bpy.ops.object.select_all(action="DESELECT")
            for x in exp_objects:
                if (x.type == "MESH" and x.data.users < 2) or x.type != "MESH":
                    context.view_layer.objects.active = x
                    x.select_set(True)
            bpy.ops.object.transform_apply(
                location=False,
                rotation=options.apply_rot,
                scale=options.apply_scale,
            )
            context.view_layer.objects.active = cur_active
        else:
            bpy.ops.object.transform_apply(
                location=False, rotation=False, scale=options.apply_scale
            )
            if options.apply_rot:
                context.scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
                for x in exp_objects:
                    bpy.ops.object.select_all(action="DESELECT")
                    if x.parent is None:
                        x.select_set(True)
                        context.view_layer.objects.active = x
                        child_rotated = False
                        bpy.ops.object.select_grouped(extend=True, type="CHILDREN_RECURSIVE")
                        for y in context.selected_objects:
                            if (
                                abs(y.rotation_euler.x)
                                + abs(y.rotation_euler.y)
                                + abs(y.rotation_euler.z)
                                > 0.017
                            ):
                                child_rotated = True
                        bpy.ops.object.select_all(action="DESELECT")
                        x.select_set(True)
                        if format == "FBX" and (
                            options.apply_rot_rotated
                            or (not options.apply_rot_rotated and not child_rotated)
                            or mode != "PARENT"
                        ):
                            bpy.ops.object.transform_apply(
                                location=False, rotation=True, scale=False
                            )
                            bpy.ops.transform.rotate(
                                value=math.pi * -90 / 180,
                                orient_axis="X",
                                orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                orient_type="GLOBAL",
                                constraint_axis=(True, False, False),
                                orient_matrix_type="GLOBAL",
                                mirror=False,
                                use_proportional_edit=False,
                                proportional_edit_falloff="SMOOTH",
                                proportional_size=1,
                            )
                            bpy.ops.object.select_grouped(
                                extend=True, type="CHILDREN_RECURSIVE"
                            )
                            bpy.ops.object.transform_apply(
                                location=False, rotation=True, scale=False
                            )
                            bpy.ops.object.select_all(action="DESELECT")
                            x.select_set(True)
                            bpy.ops.transform.rotate(
                                value=math.pi * 90 / 180,
                                orient_axis="X",
                                orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                orient_type="GLOBAL",
                                constraint_axis=(True, False, False),
                                orient_matrix_type="GLOBAL",
                                mirror=False,
                                use_proportional_edit=False,
                                proportional_edit_falloff="SMOOTH",
                                proportional_size=1,
                            )

        bpy.ops.object.select_all(action="DESELECT")
        for x in exp_objects:
            if x.type in {"MESH", "EMPTY", "ARMATURE"}:
                x.select_set(True)

        duplicated_data = [obj.data.name for obj in exp_objects if obj.type == "MESH"]
        combined_meshes: list = []

        # ---- Export by mode ----
        def _export(name_raw: str) -> str:
            """Sanitize name, call utils.export_model, return final path."""
            clean = utils.prefilter_export_name(name_raw)
            if clean != name_raw:
                incorrect_names.append(name_raw)
            utils.export_model(path, clean)
            ext = {"FBX": ".fbx", "OBJ": ".obj", "GLTF": ".glb"}.get(format, "")
            fp = path + clean + ext
            exported_files.append(fp)
            return fp

        if mode == "ALL":
            if options.export_combine_meshes:
                if start_active and start_active.type == "MESH":
                    context.view_layer.objects.active = start_active
                    bpy.ops.object.join()
                else:
                    for obj in exp_objects:
                        if obj.type == "MESH":
                            context.view_layer.objects.active = obj
                    bpy.ops.object.join()
                exp_objects = list(context.selected_objects)

            fname = options.custom_fbx_name if options.set_custom_fbx_name else active_name
            _export(fname)

        elif mode == "INDIVIDUAL":
            for x in exp_objects:
                obj_loc = (0.0, 0.0, 0.0)
                context.scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
                bpy.ops.object.select_all(action="DESELECT")
                x.select_set(True)
                context.view_layer.objects.active = x
                if options.apply_loc:
                    _set_cursor_to_selection_center(context)
                    obj_loc = context.scene.cursor.location.copy()
                    bpy.ops.object.location_clear(clear_delta=False)
                else:
                    _set_cursor_to_world_origin(context)
                    context.scene.tool_settings.transform_pivot_point = "CURSOR"
                _export(x.name)
                if options.apply_loc:
                    context.scene.cursor.location = obj_loc
                    _move_selection_center_to_cursor(context)

        elif mode == "PARENT":
            bpy.ops.object.select_all(action="DESELECT")
            for x in exp_objects:
                if x.parent is None:
                    x.select_set(True)
            parent_objs = list(context.selected_objects)

            for x in parent_objs:
                bpy.ops.object.select_all(action="DESELECT")
                context.view_layer.objects.active = x
                x.select_set(True)
                if options.export_combine_meshes:
                    if x.type == "MESH":
                        bpy.ops.object.select_grouped(extend=True, type="CHILDREN_RECURSIVE")
                        bpy.ops.object.join()
                        for obj in list(context.selected_objects):
                            if obj.type == "EMPTY" and len(obj.children) == 0:
                                bpy.data.objects.remove(obj, do_unlink=True)
                    else:
                        cur_active = context.view_layer.objects.active
                        parent_loc = cur_active.location.copy()
                        parent_name = cur_active.name
                        bpy.ops.object.select_grouped(
                            extend=False, type="CHILDREN_RECURSIVE"
                        )
                        for obj in context.selected_objects:
                            if obj.type == "MESH":
                                context.view_layer.objects.active = obj
                        bpy.ops.object.join()
                        context.view_layer.objects.active.name = parent_name + "_Mesh"
                        cur_active.select_set(True)
                        context.view_layer.objects.active = cur_active
                        bpy.ops.object.parent_set(type="OBJECT", keep_transform=True)
                        context.scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
                        context.scene.cursor.location = parent_loc
                        bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
                        for obj in list(context.selected_objects):
                            if obj.type == "EMPTY" and len(obj.children) == 0:
                                bpy.data.objects.remove(obj, do_unlink=True)
                        context.view_layer.objects.active = cur_active

                cur_parent = context.view_layer.objects.active
                obj_loc = (0.0, 0.0, 0.0)
                context.scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
                bpy.ops.object.select_all(action="DESELECT")
                cur_parent.select_set(True)
                context.view_layer.objects.active = cur_parent
                if options.apply_loc:
                    _set_cursor_to_selection_center(context)
                    obj_loc = context.scene.cursor.location.copy()
                    bpy.ops.object.location_clear(clear_delta=False)
                else:
                    _set_cursor_to_world_origin(context)
                    context.scene.tool_settings.transform_pivot_point = "CURSOR"
                bpy.ops.object.select_grouped(extend=True, type="CHILDREN_RECURSIVE")
                _export(cur_parent.name)
                if options.export_combine_meshes:
                    combined_meshes.extend(context.selected_objects)
                bpy.ops.object.select_all(action="DESELECT")
                cur_parent.select_set(True)
                if options.apply_loc:
                    context.scene.cursor.location = obj_loc
                    _move_selection_center_to_cursor(context)

        elif mode == "COLLECTION":
            origin_loc = (0.0, 0.0, 0.0)
            context.scene.tool_settings.transform_pivot_point = "MEDIAN_POINT"
            used_collections: list[str] = []
            obj_col_dict: dict = {}
            for x in exp_objects:
                col = x.users_collection[0].name if x.users_collection else ""
                if col not in used_collections:
                    used_collections.append(col)
                obj_col_dict[x] = col

            for c in used_collections:
                bpy.ops.object.select_all(action="DESELECT")
                set_active_mesh = False
                for obj, col_name in obj_col_dict.items():
                    if col_name == c:
                        obj.select_set(True)
                        if obj.type == "MESH" and not set_active_mesh:
                            context.view_layer.objects.active = obj
                            if options.export_combine_meshes:
                                obj.name = c
                            set_active_mesh = True
                if options.export_combine_meshes and set_active_mesh:
                    bpy.ops.object.join()
                    context.scene.cursor.location = origin_loc
                    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")
                    for obj in list(context.selected_objects):
                        if obj.type == "EMPTY" and len(obj.children) == 0:
                            bpy.data.objects.remove(obj, do_unlink=True)
                _export(c)
                if options.export_combine_meshes:
                    combined_meshes.extend(context.selected_objects)

            bpy.ops.object.select_all(action="DESELECT")

        if options.export_combine_meshes and mode in {"PARENT", "COLLECTION"}:
            exp_objects = combined_meshes

        # ---- Cleanup duplicates ----
        bpy.ops.object.select_all(action="DESELECT")
        for obj in exp_objects:
            obj.select_set(True)
        bpy.ops.object.delete()
        for data_name in duplicated_data:
            try:
                bpy.data.meshes.remove(bpy.data.meshes[data_name])
            except Exception:
                pass

        # Restore original names (remove _ex).
        bpy.ops.object.select_all(action="DESELECT")
        for j in current_selected:
            j.name = j.name[:-3]
            if j.type in {"MESH", "ARMATURE"}:
                j.data.name = j.data.name[:-3]

        for i in start_selected:
            i.select_set(True)
        context.view_layer.objects.active = start_active

        utils.print_execution_time("Export", start_time)
        return ExportResult(
            ok=True,
            exported_files=exported_files,
            export_dir=path,
            incorrect_names=incorrect_names,
            message=f"导出完成，{len(exported_files)} 个文件已保存到 {path}",
        )

    except Exception as exc:
        # Best-effort restore on failure.
        try:
            if exp_objects:
                bpy.ops.object.select_all(action="DESELECT")
                for obj in exp_objects:
                    if obj and obj.name in bpy.data.objects:
                        obj.select_set(True)
                bpy.ops.object.delete()
            for data_name in duplicated_data:
                try:
                    bpy.data.meshes.remove(bpy.data.meshes[data_name])
                except Exception:
                    pass
            bpy.ops.object.select_all(action="DESELECT")
            for obj in current_selected:
                if obj and obj.name in bpy.data.objects:
                    if obj.name.endswith("_ex"):
                        obj.name = obj.name[:-3]
                    if obj.type in {"MESH", "ARMATURE"} and obj.data.name.endswith("_ex"):
                        obj.data.name = obj.data.name[:-3]
            for obj in start_selected:
                if obj and obj.name in bpy.data.objects:
                    obj.select_set(True)
            if start_active and start_active.name in bpy.data.objects:
                context.view_layer.objects.active = start_active
            context.scene.cursor.location = saved_cursor_loc
            context.scene.tool_settings.transform_pivot_point = saved_pivot_point
            context.scene.tool_settings.use_transform_pivot_point_align = saved_pivot_align
            _restore_scene_export_settings(context, export_settings_snapshot)
        except Exception:
            pass
        return ExportResult(ok=False, error=str(exc))

    finally:
        # Always restore cursor/pivot even on success path.
        try:
            context.scene.cursor.location = saved_cursor_loc
            context.scene.tool_settings.transform_pivot_point = saved_pivot_point
            context.scene.tool_settings.use_transform_pivot_point_align = saved_pivot_align
            _restore_scene_export_settings(context, export_settings_snapshot)
        except Exception:
            pass
