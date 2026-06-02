# -*- coding: utf-8 -*-
"""
POPAgent skill wrappers for PopTools Marmoset Baker utilities.

All handlers are dispatched through POPAgent's main-thread executor, so direct
bpy.data writes are safe.  Handlers never raise; they return structured dicts.
"""

from __future__ import annotations
import os
import bpy
from ..marmoset_baker_tools import (
    count_mesh_faces_and_tris,
    get_candidate_meshes,
    image_is_packed,
    image_is_regular_file,
    image_source_path,
    infer_high_low_pairs,
    iter_texture_image_users,
)
from ..core.highlow_pairing_core import complexity_of, plan_high_low_pairs
from ..core.texname_core import coerce_bool


# ===========================================================================
# Pattern 2: poptools.auto_mark_high_low
# ===========================================================================

def _handler_auto_mark_high_low(context=None, prefix: str = "",
                                dry_run: bool = False) -> dict:
    if context is None:
        context = bpy.context

    dry_run = coerce_bool(dry_run, default=False)
    settings = context.scene.poptools_props.marmoset_baker_settings
    resolved_prefix = prefix.strip() or settings.model_name_prefix.strip()
    objects = get_candidate_meshes(context, settings)

    # Always plan on a draft first (no renaming). The legacy infer_high_low_pairs
    # renames as it computes, so committing with leftovers/ambiguity present would
    # leave the scene half-renamed while we report failure.
    plan = plan_high_low_pairs([(o.name, complexity_of(o)) for o in objects])

    # dry_run: hand the agent the full draft (per-pair polygon counts + ambiguity)
    # so it can inspect / screenshot before deciding to commit. Never renames.
    if dry_run:
        return {
            "ok": plan.ok, "dry_run": True, "error_kind": plan.error_kind,
            "message": plan.message, "pairs": plan.pairs,
            "leftovers": plan.leftovers, "ambiguous_pairs": plan.ambiguous_pairs,
        }

    if not plan.ok:
        return {
            "ok": False, "error_kind": plan.error_kind, "error": plan.message,
            "pairs": plan.pairs, "leftovers": plan.leftovers,
            "ambiguous_pairs": plan.ambiguous_pairs,
        }

    # plan.ok guarantees zero leftovers and no ambiguous pairs, so the commit
    # pass pairs everything with an unambiguous high/low assignment.
    pairs, _ = infer_high_low_pairs(objects, resolved_prefix)

    return {
        "ok": True,
        "pair_count": len(pairs),
        "pairs": [p["base_name"] for p in pairs],
        "message": f"Auto-marked {len(pairs)} high/low pair(s).",
    }


AUTO_MARK_HIGH_LOW = {
    "name": "poptools.auto_mark_high_low",
    "description": (
        "Automatically detect and mark high/low poly pairs among selected mesh "
        "objects by polygon count, renaming them with _high/_low suffixes. "
        "Validates before renaming: if any object is left unpaired, or any pair "
        "has equal polygon counts (so high vs low is ambiguous), NOTHING is "
        "renamed and the draft (per-pair polygon counts, leftovers, "
        "ambiguous_pairs) is returned. On an ambiguous/unpaired result: if vision "
        "is available, call blender.viewport_screenshot to inspect and decide; "
        "otherwise ask the user to confirm the pairing manually. Do NOT guess. "
        "Use dry_run=true to preview the pairing without renaming. Requires at "
        "least 2 mesh objects."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prefix": {
                "type": "string",
                "description": (
                    "Name prefix for the pairs. Falls back to the scene's "
                    "model_name_prefix setting if empty."
                ),
            },
            "dry_run": {
                "type": ["boolean", "string"],
                "description": (
                    "If true, return the planned pairing (with polygon counts and "
                    "ambiguity flags) WITHOUT renaming anything. Default false."
                ),
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_auto_mark_high_low,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# Pattern 1 (read-only): poptools.show_polycount
# ===========================================================================

def _handler_show_polycount(context=None) -> dict:
    if context is None:
        context = bpy.context

    selected_meshes = [o for o in context.selected_objects if o.type == "MESH"]
    if not selected_meshes:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No mesh objects selected."}

    depsgraph = context.evaluated_depsgraph_get()
    per_object = []
    total_faces = 0
    total_tris = 0
    for obj in selected_meshes:
        face_count, tri_count = count_mesh_faces_and_tris(obj, depsgraph)
        per_object.append({"name": obj.name, "faces": face_count, "tris": tri_count})
        total_faces += face_count
        total_tris += tri_count

    return {
        "ok": True,
        "objects": per_object,
        "total_faces": total_faces,
        "total_tris": total_tris,
        "object_count": len(per_object),
        "message": (
            f"{len(per_object)} mesh(es): "
            f"Faces {total_faces:,}, Tris {total_tris:,}"
        ),
    }


SHOW_POLYCOUNT = {
    "name": "poptools.show_polycount",
    "description": (
        "Count polygon statistics (faces and triangles) for selected mesh "
        "objects. Read-only; does not modify anything or display viewport overlays."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_show_polycount,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


# ===========================================================================
# Pattern 1 (read-only): poptools.find_missing_textures
# ===========================================================================

def _handler_find_missing_textures(context=None) -> dict:
    if context is None:
        context = bpy.context

    missing = []
    total_nodes = 0
    seen = set()

    for owner_label, _node, image in iter_texture_image_users():
        total_nodes += 1
        ptr = image.as_pointer()
        if ptr in seen:
            continue
        seen.add(ptr)

        if image_is_packed(image):
            continue
        if not image_is_regular_file(image):
            continue

        filepath = image_source_path(image)
        if filepath and not os.path.isfile(filepath):
            missing.append({
                "image_name": image.name,
                "filepath": filepath,
                "owner": owner_label,
            })

    return {
        "ok": True,
        "total_nodes": total_nodes,
        "missing_count": len(missing),
        "missing": missing,
        "message": (
            f"Scanned {total_nodes} texture node(s); "
            f"{len(missing)} missing."
        ),
    }


FIND_MISSING_TEXTURES = {
    "name": "poptools.find_missing_textures",
    "description": (
        "Scan all texture image nodes in the scene and report which ones "
        "point to files that no longer exist on disk. Read-only detection; "
        "does not relink or modify any file paths."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_find_missing_textures,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}


# ===========================================================================
# Pattern 2: poptools.generate_lowpoly
# ===========================================================================

def _handler_generate_lowpoly(context=None, decimate_ratio: float = 0.1,
                               prefix: str = "") -> dict:
    if context is None:
        context = bpy.context

    high_objects = [o for o in context.selected_objects if o.type == "MESH"]
    if not high_objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No mesh objects selected."}

    settings = context.scene.poptools_props.marmoset_baker_settings

    # Temporarily apply agent params to scene props
    saved_ratio = settings.lowpoly_decimate_ratio
    saved_prefix = settings.model_name_prefix
    try:
        settings.lowpoly_decimate_ratio = decimate_ratio
        if prefix.strip():
            settings.model_name_prefix = prefix.strip()

        result = bpy.ops.poptools.marmoset_generate_lowpoly()
        if result != {"FINISHED"}:
            return {"ok": False, "error_kind": "generation_failed",
                    "error": "Lowpoly generation operator returned CANCELLED."}

        return {
            "ok": True,
            "generated_count": len(high_objects),
            "decimate_ratio": decimate_ratio,
            "message": f"Generated {len(high_objects)} low-poly object(s) at ratio {decimate_ratio:g}.",
        }
    except Exception as exc:
        return {"ok": False, "error_kind": "generation_failed", "error": str(exc)}
    finally:
        settings.lowpoly_decimate_ratio = saved_ratio
        settings.model_name_prefix = saved_prefix


GENERATE_LOWPOLY = {
    "name": "poptools.generate_lowpoly",
    "description": (
        "Generate low-poly versions of selected mesh objects.  Duplicates "
        "each object, applies a Decimate modifier at the given ratio, runs "
        "smart UV projection, and names them with _low suffix. "
        "Modifies the scene; requires mesh objects to be selected."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "decimate_ratio": {
                "type": "number",
                "description": "Decimate collapse ratio (0.0001–1.0). Default 0.1.",
            },
            "prefix": {
                "type": "string",
                "description": (
                    "Name prefix for generated pairs. Falls back to scene "
                    "model_name_prefix if empty."
                ),
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_generate_lowpoly,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# Pattern 2: poptools.secure_texture_resources
# ===========================================================================

def _handler_secure_texture_resources(context=None) -> dict:
    if context is None:
        context = bpy.context

    from ..marmoset_baker_tools import secure_project_textures

    try:
        stats = secure_project_textures(context)
    except Exception as exc:
        return {"ok": False, "error_kind": "secure_failed", "error": str(exc)}

    return {
        "ok": True,
        "total_nodes": stats["total_nodes"],
        "copied": stats["copied"],
        "relinked": stats["relinked"],
        "already_safe": stats["already_safe"],
        "packed": stats["packed"],
        "skipped": stats["skipped"],
        "missing": stats["missing"],
        "errors": stats["errors"],
        "message": (
            f"Scanned {stats['total_nodes']} nodes; "
            f"copied {stats['copied']}, relinked {stats['relinked']}, "
            f"safe {stats['already_safe']}, packed {stats['packed']}, "
            f"skipped {stats['skipped']}."
            + (f" Still missing: {len(stats['missing'])}." if stats["missing"] else "")
            + (f" Errors: {len(stats['errors'])}." if stats["errors"] else "")
        ),
    }


SECURE_TEXTURE_RESOURCES = {
    "name": "poptools.secure_texture_resources",
    "description": (
        "Copy all project textures into a local 'textures/' directory next to "
        "the .blend file and relink image paths to relative references. "
        "Prevents texture loss when moving the project folder. "
        "Requires the .blend to be saved first."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_secure_texture_resources,
    "metadata": {
        "modifies_scene": True,
        "writes_files": True,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "always",
    },
}


# ===========================================================================
# Pattern 1/2: poptools.auto_detect_toolbag
# ===========================================================================

def _handler_auto_detect_toolbag(context=None, save_to_preferences: bool = False) -> dict:
    if context is None:
        context = bpy.context

    from ..marmoset_baker_tools import (
        find_toolbag_executable,
        save_marmoset_path_to_preferences,
    )

    toolbag_path = find_toolbag_executable()
    if not toolbag_path:
        return {"ok": False, "error_kind": "not_found",
                "error": "Marmoset Toolbag not found on this system."}

    if save_to_preferences:
        try:
            save_marmoset_path_to_preferences(context, toolbag_path)
        except Exception as exc:
            return {
                "ok": True,
                "toolbag_path": toolbag_path,
                "saved": False,
                "message": f"Found Toolbag at {toolbag_path}, but could not save to preferences: {exc}",
            }

    return {
        "ok": True,
        "toolbag_path": toolbag_path,
        "saved": save_to_preferences,
        "message": f"Found Marmoset Toolbag: {toolbag_path}",
    }


AUTO_DETECT_TOOLBAG = {
    "name": "poptools.auto_detect_toolbag",
    "description": (
        "Auto-detect the Marmoset Toolbag installation path by searching "
        "common locations (PATH, Program Files, AppData). Returns the path "
        "if found. Optionally saves to addon preferences."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "save_to_preferences": {
                "type": "boolean",
                "description": "Save the found path to addon preferences. Default false.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_auto_detect_toolbag,
    "metadata": {
        "modifies_scene": False,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": False,
        "requires_confirmation": "never",
    },
}
