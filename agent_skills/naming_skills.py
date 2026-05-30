# -*- coding: utf-8 -*-
"""
POPAgent skill wrappers for PopTools naming utilities.

Handlers do not call bpy.ops, but some still modify bpy.data names and must be
executed through POPAgent's main-thread executor.
"""

from __future__ import annotations
import bpy
from ..core.naming_core import (
    apply_generic_model_naming,
    build_action_name,
    get_unique_action_name,
    rename_action_on_object,
)
from ..generic_model_naming import build_sequential_names
from ..retex_naming import build_texture_name_from_object_name


# ---------------------------------------------------------------------------
# poptools.apply_action_naming
# ---------------------------------------------------------------------------

def _handler_name_action(
    context=None,
    animation_type: str = "",
    animation_name: str = "",
    island_name: str = "",
    chinese_comment: str = "",
) -> dict:
    if context is None:
        context = bpy.context

    obj = context.active_object
    result = rename_action_on_object(
        obj=obj,
        animation_type=animation_type,
        animation_name=animation_name,
        island_name=island_name,
        chinese_comment=chinese_comment,
    )
    if not result.ok:
        return {"ok": False, "error_kind": "naming_error", "error": result.message}
    return {"ok": True, "old_name": result.old_name, "new_name": result.new_name, "message": result.message}


APPLY_ACTION_NAMING = {
    "name": "poptools.apply_action_naming",
    "description": (
        "Rename the animation action on the active object following the project naming convention. "
        "Produces names like 'ani_idle_stand_wave01' or 'ani_npc_loveisland_dance01'. "
        "animation_name should already be in English (translate first if needed). "
        "animation_type options: idle_stand, idle_sit, celebrate_clap, move_walk, move_run, "
        "play_chat, play_control, npc_island."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "animation_type": {
                "type": "string",
                "enum": [
                    "idle_stand", "idle_sit", "celebrate_clap",
                    "move_walk", "move_run", "play_chat",
                    "play_control", "npc_island",
                ],
                "description": "Animation category.",
            },
            "animation_name": {
                "type": "string",
                "description": "English snake_case animation name stem, e.g. 'wave01'.",
            },
            "island_name": {
                "type": "string",
                "description": "Required when animation_type='npc_island'. Island identifier, e.g. 'loveisland'.",
            },
            "chinese_comment": {
                "type": "string",
                "description": "Optional Chinese annotation stored in AC_Settings.tags.",
            },
        },
        "required": ["animation_type", "animation_name"],
    },
    "owner": "poptools",
    "handler": _handler_name_action,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ---------------------------------------------------------------------------
# poptools.apply_generic_naming
# ---------------------------------------------------------------------------

def _handler_apply_generic_naming(
    context=None,
    activity_type: str = "",
    model_name: str = "",
    suffix: str = "",
) -> dict:
    if context is None:
        context = bpy.context

    result = apply_generic_model_naming(
        objects=list(context.selected_objects),
        activity_type=activity_type,
        model_name=model_name,
        suffix=suffix,
    )
    if not result.ok:
        return {
            "ok": False,
            "error_kind": result.error_kind or "naming_error",
            "error": result.error,
        }
    return {
        "ok": True,
        "renamed": result.renamed or [],
        "message": result.message,
    }


APPLY_GENERIC_NAMING = {
    "name": "poptools.apply_generic_naming",
    "description": (
        "Rename the currently selected mesh objects following the generic model convention "
        "'mesh_{activity_type}_{model_name}{N:02d}'. "
        "Also syncs each object's mesh data name. Use this when the user asks to apply "
        "generic PopTools naming to selected models."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "activity_type": {
                "type": "string",
                "description": "Activity/category prefix, e.g. 'idle', 'run', 'sit'.",
            },
            "model_name": {
                "type": "string",
                "description": "Model identifier, e.g. 'npc_chef'.",
            },
            "suffix": {
                "type": "string",
                "description": "Optional suffix inserted before the serial number.",
            },
        },
        "required": ["activity_type", "model_name"],
    },
    "owner": "poptools",
    "handler": _handler_apply_generic_naming,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ---------------------------------------------------------------------------
# poptools.preview_generic_names
# ---------------------------------------------------------------------------

def _handler_preview_generic_names(
    context=None,
    activity_type: str = "",
    model_name: str = "",
    count: int = 1,
    suffix: str = "",
) -> dict:
    existing = {obj.name for obj in bpy.data.objects} if bpy.data else set()
    names = build_sequential_names(
        activity_type=activity_type,
        model_name=model_name,
        count=count,
        existing_names=existing,
        suffix=suffix,
    )
    return {"ok": True, "names": names}


PREVIEW_GENERIC_NAMES = {
    "name": "poptools.preview_generic_names",
    "description": (
        "Preview sequential generic mesh names without changing the scene. "
        "Use apply_generic_naming when the user wants to actually rename selected objects."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "activity_type": {
                "type": "string",
                "description": "Activity/category prefix, e.g. 'minigame'.",
            },
            "model_name": {
                "type": "string",
                "description": "Model identifier, e.g. 'cake'.",
            },
            "count": {
                "type": "integer",
                "description": "How many sequential names to generate.",
                "minimum": 1,
            },
            "suffix": {
                "type": "string",
                "description": "Optional suffix inserted before the serial number.",
            },
        },
        "required": ["activity_type", "model_name"],
    },
    "owner": "poptools",
    "handler": _handler_preview_generic_names,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


# ---------------------------------------------------------------------------
# poptools.build_texture_name
# ---------------------------------------------------------------------------

def _handler_build_texture_name(
    context=None,
    object_name: str = "",
    replace_prefix: bool = True,
    texture_suffix: str = "",
) -> dict:
    name = build_texture_name_from_object_name(
        object_name=object_name,
        replace_prefix=replace_prefix,
        texture_suffix=texture_suffix,
    )
    return {"texture_name": name}


BUILD_TEXTURE_NAME = {
    "name": "poptools.build_texture_name",
    "description": (
        "Derive a texture asset name from a mesh object name. "
        "Replaces 'mesh_' prefix with 'tex_' by default. "
        "E.g. 'mesh_idle_npc_chef01' → 'tex_idle_npc_chef01'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "object_name": {
                "type": "string",
                "description": "Source mesh object name.",
            },
            "replace_prefix": {
                "type": "boolean",
                "description": "Replace 'mesh_' with 'tex_' (default true).",
            },
            "texture_suffix": {
                "type": "string",
                "description": "Optional suffix appended before the final name, e.g. 'albedo'.",
            },
        },
        "required": ["object_name"],
    },
    "owner": "poptools",
    "handler": _handler_build_texture_name,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


# ---------------------------------------------------------------------------
# poptools.retex_name_from_active
# ---------------------------------------------------------------------------

def _handler_retex_name_from_active(
    context=None,
    replace_prefix: bool = True,
    texture_suffix: str = "",
) -> dict:
    if context is None:
        context = bpy.context

    obj = context.active_object
    if obj is None:
        return {"ok": False, "error_kind": "no_active", "error": "No active object."}

    texture_name = build_texture_name_from_object_name(
        object_name=obj.name,
        replace_prefix=replace_prefix,
        texture_suffix=texture_suffix,
    )
    return {"ok": True, "object_name": obj.name, "texture_name": texture_name}


RETEX_NAME_FROM_ACTIVE = {
    "name": "poptools.retex_name_from_active",
    "description": (
        "Derive the texture asset name from the currently active object's name. "
        "Replaces 'mesh_' prefix with 'tex_' (e.g. 'mesh_idle_chef01' → 'tex_idle_chef01'). "
        "Use this when the user asks to name a texture for the selected object."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "replace_prefix": {
                "type": "boolean",
                "description": "Replace 'mesh_' prefix with 'tex_' (default true).",
            },
            "texture_suffix": {
                "type": "string",
                "description": "Optional suffix, e.g. 'albedo', 'normal'.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_retex_name_from_active,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}
