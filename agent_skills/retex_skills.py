# -*- coding: utf-8 -*-
"""
POPAgent skill wrappers for PopTools ReTex / Marmoset utilities.

Two patterns live here:
  - Pattern 1 (check_uvs, smart_rename): delegate to pure functions in
    core/retex_core.py, then apply results.
  - Pattern 2 (organize_materials, mark_high_low): act directly on bpy.data.
    The underlying operators (rt.organize_selected_materials,
    poptools.marmoset_mark_*) use bpy.data + name assignment only (no bpy.ops)
    and pop a UI message box; we replicate their core mutation here to avoid
    the modal popup side effect.

All handlers are dispatched through POPAgent's main-thread executor, so direct
bpy.data writes are safe. Handlers never raise; they return structured dicts.
"""

from __future__ import annotations
import bpy
from ..core.retex_core import check_duplicate_uvs, build_smart_rename
from ..core.rename_category_core import build_rename_plan
from ..core.adjust_serial_core import adjust_serial
from ..core.texname_core import plan_texture_renames, build_texture_name, coerce_bool


# ===========================================================================
# Pattern 1: poptools.check_uvs
# ===========================================================================

def _handler_check_uvs(context=None) -> dict:
    if context is None:
        context = bpy.context

    objects = list(getattr(context.scene, "objects", []) or [])
    result = check_duplicate_uvs(objects)
    return {
        "ok": True,
        "objects_with_multiple_uvs": result.objects_with_multiple_uvs,
        "count": len(result.objects_with_multiple_uvs),
        "message": result.message,
    }


CHECK_UVS = {
    "name": "poptools.check_uvs",
    "description": (
        "Scan all mesh objects in the scene and report which ones have more "
        "than one UV map. Read-only inspection; does not modify anything. "
        "Useful as a pre-export self-check."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_check_uvs,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


# ===========================================================================
# Pattern 1: poptools.smart_rename
# ===========================================================================

def _handler_smart_rename(context=None, item_land: str = "") -> dict:
    if context is None:
        context = bpy.context

    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No objects selected to rename."}

    resolved_land = item_land.strip()
    if not resolved_land:
        settings = getattr(context.scene, "poptools_props", None)
        retex = getattr(settings, "retex_settings", None)
        resolved_land = getattr(retex, "item_land", "") if retex else ""
    if not resolved_land:
        return {"ok": False, "error_kind": "missing_item_land",
                "error": "item_land is required (set it or pass the argument)."}

    existing = {o.name for o in bpy.data.objects}
    plan = build_smart_rename(objects, item_land=resolved_land, existing_names=existing)

    applied = []
    for entry in plan.renamed:
        obj = bpy.data.objects.get(entry["old_name"])
        if obj is None:
            plan.errors.append(f"对象 '{entry['old_name']}' 重命名失败：已不存在")
            continue
        obj.name = entry["new_name"]
        applied.append(entry)

    return {
        "ok": bool(applied),
        "renamed": applied,
        "errors": plan.errors,
        "message": f"成功重命名 {len(applied)} 个对象" if applied else "没有对象被重命名",
    }


SMART_RENAME = {
    "name": "poptools.smart_rename",
    "description": (
        "Smart-rename the currently selected mesh objects to "
        "'mesh_item_{item_land}_{type}_{NN}'. The type is inferred from a "
        "letter prefix in the original name (b=balloon, h=hand, p=prop, "
        "c=cap) and NN from its trailing number. Objects whose names lack a "
        "recognizable letter+number pattern are skipped and reported in errors."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "item_land": {
                "type": "string",
                "description": (
                    "Item-land identifier inserted into the name. If omitted, "
                    "falls back to the ReTex panel's item_land setting."
                ),
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_smart_rename,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# Pattern 2: poptools.organize_materials
# ===========================================================================

def _handler_organize_materials(context=None) -> dict:
    if context is None:
        context = bpy.context

    objects = [o for o in context.selected_objects if o.type == "MESH"]
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No selected mesh objects."}

    organized = []
    try:
        for obj in objects:
            if obj.data and obj.data.materials:
                obj.data.materials.clear()
            new_mat = bpy.data.materials.new(name=obj.name)
            new_mat.use_nodes = True
            obj.data.materials.append(new_mat)
            organized.append(obj.name)
    except Exception as exc:
        return {"ok": False, "error_kind": "organize_failed", "error": str(exc)}

    return {
        "ok": True,
        "organized": organized,
        "message": f"成功为 {len(organized)} 个选中模型整理了材质",
    }


ORGANIZE_MATERIALS = {
    "name": "poptools.organize_materials",
    "description": (
        "Reset materials on the selected mesh objects: clear every material "
        "slot and create one fresh node-based material named after each "
        "object. Destructive — existing material assignments are removed."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_organize_materials,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# Pattern 2: poptools.mark_high_low
# ===========================================================================

def _handler_mark_high_low(context=None, role: str = "") -> dict:
    if context is None:
        context = bpy.context

    if role not in ("high", "low"):
        return {"ok": False, "error_kind": "invalid_arguments",
                "error": "role must be 'high' or 'low'."}

    from ..marmoset_baker_tools import clean_base_name, LOW_SUFFIX, HIGH_SUFFIX

    suffix = LOW_SUFFIX if role == "low" else HIGH_SUFFIX
    objects = [o for o in context.selected_objects if o.type == "MESH"]
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No selected mesh objects."}

    marked = []
    for obj in objects:
        obj.name = f"{clean_base_name(obj.name)}{suffix}"
        marked.append(obj.name)

    return {
        "ok": True,
        "role": role,
        "marked": marked,
        "message": f"已标记 {len(marked)} 个{('低' if role == 'low' else '高')}模对象",
    }


MARK_HIGH_LOW = {
    "name": "poptools.mark_high_low",
    "description": (
        "Tag the selected mesh objects as high-poly or low-poly for baking by "
        "appending '_high' or '_low' to their names (existing _high/_low and "
        "numeric .001 suffixes are stripped first). Pass role='high' or "
        "role='low'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["high", "low"],
                "description": "Which bake role to assign.",
            },
        },
        "required": ["role"],
    },
    "owner": "poptools",
    "handler": _handler_mark_high_low,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# Pattern 1: poptools.rename_by_category
# ===========================================================================

# Props used as fallback when skill arguments are empty.
_CATEGORY_PROP_MAP = {
    "character_body":  ("character_body_type",  "character_serial_number", "character_suffix"),
    "character_hair":  ("character_body_type",  "character_serial_number", "character_suffix"),
    "character_tool":  ("character_body_type",  "character_serial_number", "texture_suffix"),
    "animal":          ("animal_body_type",     "animal_serial_number",   "character_suffix"),
}


def _handler_rename_by_category(
    context=None,
    category: str = "character_body",
    body_type: str = "",
    serial_number: str = "",
    suffix: str = "",
    building_type: str = "",
    island_name: str = "",
    building_name: str = "",
    gameplay: str = "",
    scene: str = "",
    item_name: str = "",
    activity_type: str = "",
    model_name: str = "",
) -> dict:
    if context is None:
        context = bpy.context

    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No objects selected."}

    # Prop fallback for simple categories
    if category in _CATEGORY_PROP_MAP and not all([body_type, serial_number]):
        settings = getattr(context.scene, "poptools_props", None)
        retex = getattr(settings, "retex_settings", None) if settings else None
        if retex:
            bt_prop, sn_prop, sf_prop = _CATEGORY_PROP_MAP[category]
            if not body_type:
                body_type = getattr(retex, bt_prop, "") or ""
            if not serial_number:
                serial_number = getattr(retex, sn_prop, "") or ""
            if not suffix:
                suffix = getattr(retex, sf_prop, "") or ""

    # Prop fallback for building
    if category == "building" and not all([building_type, island_name, building_name]):
        settings = getattr(context.scene, "poptools_props", None)
        retex = getattr(settings, "retex_settings", None) if settings else None
        if retex:
            if not building_type:
                building_type = getattr(retex, "building_type", "") or ""
            if not island_name:
                island_name = getattr(retex, "building_island_name", "") or ""
            if not building_name:
                building_name = getattr(retex, "building_name", "") or ""

    # Prop fallback for minigame
    if category == "minigame" and not item_name:
        settings = getattr(context.scene, "poptools_props", None)
        retex = getattr(settings, "retex_settings", None) if settings else None
        if retex:
            if not gameplay:
                gameplay = getattr(retex, "minigame_gameplay", "") or ""
            if not scene:
                scene = getattr(retex, "minigame_scene", "") or ""
            if not item_name:
                item_name = getattr(retex, "minigame_item_name", "") or ""

    existing = {o.name for o in bpy.data.objects}
    plan = build_rename_plan(
        category=category,
        objects=objects,
        existing_names=existing,
        body_type=body_type,
        serial_number=serial_number,
        suffix=suffix,
        building_type=building_type,
        island_name=island_name,
        building_name=building_name,
        gameplay=gameplay,
        scene=scene,
        item_name=item_name,
        activity_type=activity_type,
        model_name=model_name,
    )

    if not plan.ok:
        return {"ok": False, "error_kind": plan.error_kind or "rename_failed",
                "error": plan.error or plan.message}

    applied = []
    for entry in plan.planned:
        obj = bpy.data.objects.get(entry["old_name"])
        if obj is None:
            plan.errors.append(f"对象 '{entry['old_name']}' 重命名失败：已不存在")
            continue
        obj.name = entry["new_name"]
        if obj.data:
            obj.data.name = entry["new_name"]
        applied.append(entry)

    return {
        "ok": bool(applied),
        "applied": applied,
        "errors": plan.errors,
        "message": f"成功重命名 {len(applied)} 个对象" if applied else "没有对象被重命名",
    }


RENAME_BY_CATEGORY = {
    "name": "poptools.rename_by_category",
    "description": (
        "Rename selected mesh objects using category-specific naming patterns. "
        "Categories: character_body (mesh_characters_{type}_{NN}), "
        "character_hair (mesh_head_{type}_head{NN}), "
        "character_tool (mesh_buildtools_{type}_{NN}{suffix}), "
        "animal (mesh_special_{type}_{NN}), "
        "building (mesh_{btype}_{island}_{name}{NN}), "
        "minigame (mesh_{gameplay}_{scene}_{item}), "
        "generic (mesh_{activity}_{model}{NN}). "
        "Requires mesh objects to be selected first. "
        "Also renames object data (mesh data) to match."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": [
                    "character_body", "character_hair", "character_tool",
                    "animal", "building", "minigame", "generic",
                ],
                "description": "Which naming pattern to apply.",
            },
            "body_type": {"type": "string", "description": "Body/animal type identifier (e.g. 'man', 'bird'). Falls back to scene prop."},
            "serial_number": {"type": "string", "description": "Serial number string (e.g. '01'). Falls back to scene prop."},
            "suffix": {"type": "string", "description": "Optional name suffix. Falls back to scene prop."},
            "building_type": {"type": "string", "description": "Building type: 'buildpart' or 'anibuild'."},
            "island_name": {"type": "string", "description": "Island name for building category."},
            "building_name": {"type": "string", "description": "Building name for building category."},
            "gameplay": {"type": "string", "description": "Gameplay type for minigame category (e.g. 'cleanup')."},
            "scene": {"type": "string", "description": "Scene type for minigame category (e.g. 'bedroom')."},
            "item_name": {"type": "string", "description": "Item name for minigame category."},
            "activity_type": {"type": "string", "description": "Activity type for generic category."},
            "model_name": {"type": "string", "description": "Model name for generic category."},
        },
        "required": ["category"],
    },
    "owner": "poptools",
    "handler": _handler_rename_by_category,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# Pattern 1: poptools.set_texname_of_object
# ===========================================================================

def _handler_set_texname(context=None, replace_prefix=True,
                         texture_suffix: str = "") -> dict:
    if context is None:
        context = bpy.context

    replace_prefix = coerce_bool(replace_prefix)

    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No objects selected."}

    # Read prop fallback for suffix; replace_prefix is taken from the param
    # (which carries its own default) so an explicit false is respected.
    if not texture_suffix:
        settings = getattr(context.scene, "poptools_props", None)
        retex = getattr(settings, "retex_settings", None) if settings else None
        if retex:
            texture_suffix = getattr(retex, "texture_suffix", "") or ""

    plan = plan_texture_renames(objects, replace_prefix=replace_prefix,
                                texture_suffix=texture_suffix)
    if not plan.ok:
        return {"ok": False, "error_kind": "no_textures",
                "error": "No image textures found on selected objects."}

    import os
    renamed = 0
    errors = []
    for entry in plan.planned:
        try:
            old_path = entry["old_path"]
            new_path = entry["new_path"]
            if old_path != new_path and os.path.exists(old_path):
                os.rename(old_path, new_path)
                # Update Blender image reference
                for image in bpy.data.images:
                    if image.filepath and bpy.path.abspath(image.filepath) == old_path:
                        image.filepath = new_path
                        image.name = entry["new_tex_name"]
                        break
                renamed += 1
        except Exception as exc:
            errors.append(f"纹理 '{entry.get('image_name', '?')}' 重命名失败：{exc}")

    return {
        "ok": renamed > 0,
        "renamed": renamed,
        "errors": errors,
        "message": f"成功重命名 {renamed} 个纹理" if renamed else "没有纹理被重命名",
    }


SET_TEXNAME_OF_OBJECT = {
    "name": "poptools.set_texname_of_object",
    "description": (
        "Rename image texture files on disk to match the owning object's name. "
        "Derives texture names via the mesh_→tex_ prefix convention. "
        "Requires objects with textured materials to be selected. "
        "Modifies files on disk and updates Blender image references."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "replace_prefix": {
                "type": ["boolean", "string"],
                "description": "Whether to replace 'mesh_' prefix with 'tex_'. Defaults to true.",
            },
            "texture_suffix": {
                "type": "string",
                "description": "Optional suffix appended before the tex_ prefix. Falls back to scene prop.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_set_texname,
    "metadata": {
        "modifies_scene": True,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}


# ===========================================================================
# Pattern 2: poptools.sync_texture_names
# ===========================================================================

def _handler_sync_texture_names(context=None, replace_prefix=True) -> dict:
    """Replicate rt.sync_texture_names: set tex names then sync all images."""
    if context is None:
        context = bpy.context

    replace_prefix = coerce_bool(replace_prefix)

    import os
    renamed = 0
    errors = []

    # Pass 1: rename texture files for selected objects (set_texname)
    for obj in context.selected_objects:
        slots = getattr(obj, "material_slots", None) or []
        for slot in slots:
            material = getattr(slot, "material", None)
            nt = getattr(material, "node_tree", None)
            if nt is None:
                continue
            for node in getattr(nt, "nodes", []) or []:
                if getattr(node, "type", None) != "TEX_IMAGE":
                    continue
                image = getattr(node, "image", None)
                if image is None:
                    continue
                filepath = getattr(image, "filepath", "") or ""
                if not filepath:
                    continue
                try:
                    filepath_abs = bpy.path.abspath(filepath)
                    directory = os.path.dirname(filepath_abs)
                    extension = os.path.splitext(filepath_abs)[1]

                    new_name = build_texture_name(obj.name, replace_prefix=replace_prefix)
                    new_filepath = os.path.join(directory, new_name + extension)

                    counter = 1
                    while os.path.exists(new_filepath) and new_filepath != filepath_abs:
                        new_name = build_texture_name(
                            f"{obj.name}_{counter}", replace_prefix=replace_prefix)
                        new_filepath = os.path.join(directory, new_name + extension)
                        counter += 1

                    if filepath_abs != new_filepath:
                        os.rename(filepath_abs, new_filepath)
                        image.filepath = new_filepath
                        image.name = new_name
                        renamed += 1
                except Exception as exc:
                    errors.append(f"纹理 '{image.name}' 重命名失败：{exc}")

    # Pass 2: sync all images (replace_textures)
    total_checked = 0
    total_synced = 0
    for image in bpy.data.images:
        if not image.filepath:
            continue
        total_checked += 1
        try:
            filepath_abs = bpy.path.abspath(image.filepath)
            if not filepath_abs or not os.path.exists(filepath_abs):
                continue

            directory = os.path.dirname(filepath_abs)
            extension = os.path.splitext(filepath_abs)[1]

            sync_name = build_texture_name(image.name, replace_prefix=replace_prefix)
            sync_path = os.path.join(directory, sync_name + extension)

            counter = 1
            while os.path.exists(sync_path) and sync_path != filepath_abs:
                base = sync_name.rsplit('_', 1)[0] if '_' in sync_name else sync_name
                sync_name = f"{base}_{counter}"
                sync_path = os.path.join(directory, sync_name + extension)
                counter += 1

            if filepath_abs != sync_path:
                os.rename(filepath_abs, sync_path)
                image.filepath = sync_path
                image.name = sync_name
                total_synced += 1
        except Exception as exc:
            errors.append(f"纹理 '{image.name}' 同步失败：{exc}")

    total = renamed + total_synced
    return {
        "ok": True,
        "pass1_renamed": renamed,
        "pass2_synced": total_synced,
        "total_checked": total_checked,
        "errors": errors,
        "message": (
            f"已检查 {total_checked} 个纹理，重命名 {renamed} 个，同步 {total_synced} 个"
            + (f"，{len(errors)} 个错误" if errors else "")
        ),
    }


SYNC_TEXTURE_NAMES = {
    "name": "poptools.sync_texture_names",
    "description": (
        "Sync texture names: first rename texture files on selected objects "
        "to match object names (mesh_→tex_), then sync all scene image names "
        "with their on-disk filenames. Requires objects to be selected. "
        "Modifies files on disk and Blender image data."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "replace_prefix": {
                "type": ["boolean", "string"],
                "description": "Whether to replace 'mesh_' prefix with 'tex_'. Defaults to true.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_sync_texture_names,
    "metadata": {
        "modifies_scene": True,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}


# ===========================================================================
# Pattern 1: poptools.adjust_serial_number
# ===========================================================================

# Properties stored as zero-padded strings.
_ZERO_PAD_PROPS = {"character_serial_number", "animal_serial_number"}


def _handler_adjust_serial(
    context=None,
    target_property: str = "character_serial_number",
    delta=1,
    min_value=1,
) -> dict:
    if context is None:
        context = bpy.context

    if not target_property:
        return {"ok": False, "error_kind": "missing_target_property",
                "error": "target_property is required."}

    settings = getattr(context.scene, "poptools_props", None)
    retex = getattr(settings, "retex_settings", None) if settings else None
    if retex is None:
        return {"ok": False, "error_kind": "settings_not_found",
                "error": "PopTools settings not found."}

    current_value = getattr(retex, target_property, None)
    if current_value is None:
        return {"ok": False, "error_kind": "property_not_found",
                "error": f"属性 '{target_property}' 不存在。"}

    zero_pad = target_property in _ZERO_PAD_PROPS
    result = adjust_serial(str(current_value), delta=delta, min_value=min_value,
                           zero_pad=zero_pad)
    if not result.ok:
        return {"ok": False, "error_kind": result.error_kind,
                "error": result.error}

    setattr(retex, target_property, result.new_value_str)

    return {
        "ok": True,
        "target_property": target_property,
        "old_value": result.old_value,
        "new_value": result.new_value,
        "new_value_str": result.new_value_str,
        "message": result.message,
    }


ADJUST_SERIAL_NUMBER = {
    "name": "poptools.adjust_serial_number",
    "description": (
        "Increment or decrement a serial-number scene property by a given "
        "delta, clamped to a minimum value. Typical targets: "
        "'character_serial_number', 'animal_serial_number'. "
        "Modifies a scene property; does not rename objects."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_property": {
                "type": "string",
                "description": (
                    "Scene property name to adjust. "
                    "Common values: 'character_serial_number', 'animal_serial_number'."
                ),
            },
            "delta": {
                "type": ["integer", "string"],
                "description": "Amount to add (positive) or subtract (negative). Default 1.",
            },
            "min_value": {
                "type": ["integer", "string"],
                "description": "Minimum allowed value. Default 1.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_adjust_serial,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}
