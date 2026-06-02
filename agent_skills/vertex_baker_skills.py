# -*- coding: utf-8 -*-
"""
POPAgent skill wrappers for PopTools Vertex Baker utilities.

Pattern 2 (ops_override) — handlers replicate the operator logic directly,
using ``bpy.context.temp_override`` for ``bpy.ops`` calls that require a
viewport / selection context.

All handlers are dispatched through POPAgent's main-thread executor.
Handlers never raise; they return structured dicts.
"""

from __future__ import annotations
import bpy
import bmesh
from mathutils import Vector


_COLLECTION_NAME = "VTBB_Empties"


def _ensure_collection(context):
    """Return the VTBB_Empties collection, creating it if absent."""
    if _COLLECTION_NAME in bpy.data.collections:
        return bpy.data.collections[_COLLECTION_NAME]
    col = bpy.data.collections.new(_COLLECTION_NAME)
    context.scene.collection.children.link(col)
    return col


def _get_empties():
    """Return all EMPTY objects in the VTBB_Empties collection, or []."""
    col = bpy.data.collections.get(_COLLECTION_NAME)
    if not col:
        return []
    return [o for o in col.objects if o.type == "EMPTY"]


def _viewport_override(context):
    """Build a temp_override dict targeting the first VIEW_3D area."""
    override = {}
    for window in getattr(context.window_manager, "windows", []):
        if window.screen:
            override["window"] = window
            override["screen"] = window.screen
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    override["area"] = area
                    break
            break
    return override


# ===========================================================================
# poptools.vtbb_create_empties
# ===========================================================================

def _handler_create_empties(context=None) -> dict:
    if context is None:
        context = bpy.context

    armature = context.active_object
    if not armature or armature.type != "ARMATURE":
        return {"ok": False, "error_kind": "wrong_type",
                "error": "Active object must be an armature."}

    empty_collection = _ensure_collection(context)
    created = []

    for bone in armature.data.bones:
        empty_name = f"empty_{bone.name}"
        if empty_name in bpy.data.objects:
            empty = bpy.data.objects[empty_name]
        else:
            empty = bpy.data.objects.new(empty_name, None)
            empty.empty_display_type = "ARROWS"
            empty.empty_display_size = 0.1
            empty_collection.objects.link(empty)

        bone_head_world = armature.matrix_world @ bone.head_local
        empty.location = bone_head_world

        # Copy-location constraint
        con_loc = empty.constraints.new(type="COPY_LOCATION")
        con_loc.target = armature
        con_loc.subtarget = bone.name

        # Copy-rotation constraint
        con_rot = empty.constraints.new(type="COPY_ROTATION")
        con_rot.target = armature
        con_rot.subtarget = bone.name

        created.append(empty_name)

    return {
        "ok": True,
        "created_count": len(created),
        "empties": created,
        "message": f"Created {len(created)} empty(s) for armature bones.",
    }


VTBB_CREATE_EMPTIES = {
    "name": "poptools.vtbb_create_empties",
    "description": (
        "Create an empty object for each bone in the active armature. "
        "Each empty gets copy-location and copy-rotation constraints "
        "targeting its bone. Empties are placed in a 'VTBB_Empties' collection."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_create_empties,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# poptools.vtbb_bind_vertices
# ===========================================================================

def _handler_bind_vertices(context=None, target_mesh: str = "") -> dict:
    if context is None:
        context = bpy.context

    # Resolve target mesh
    mesh = None
    if target_mesh:
        mesh = bpy.data.objects.get(target_mesh)
    if not mesh:
        props = getattr(context.scene, "poptools_props", None)
        vs = getattr(props, "vertex_baker_settings", None) if props else None
        mesh = getattr(vs, "target_mesh", None) if vs else None
    if not mesh or mesh.type != "MESH":
        return {"ok": False, "error_kind": "wrong_type",
                "error": "No valid target mesh specified."}

    empties = _get_empties()
    if not empties:
        return {"ok": False, "error_kind": "no_empties",
                "error": "No empties found. Run vtbb_create_empties first."}

    # Read mesh vertices via bmesh (needs edit-mode toggle)
    override = _viewport_override(context)
    bm = bmesh.new()
    try:
        with context.temp_override(**override):
            context.view_layer.objects.active = mesh
            bpy.ops.object.mode_set(mode="EDIT")
            bm.from_mesh(mesh.data)
            bm.verts.ensure_lookup_table()
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        bm.free()
        return {"ok": False, "error_kind": "bmesh_failed",
                "error": "Failed to read mesh vertices."}

    bound_count = 0
    try:
        for empty in empties:
            closest = None
            min_dist = float("inf")
            for vert in bm.verts:
                vert_world = mesh.matrix_world @ vert.co
                dist = (empty.location - vert_world).length
                if dist < min_dist:
                    min_dist = dist
                    closest = vert
            if closest:
                empty.location = mesh.matrix_world @ closest.co
                bound_count += 1
    finally:
        bm.free()

    return {
        "ok": True,
        "bound_count": bound_count,
        "message": f"Bound {bound_count} empty(s) to nearest vertices.",
    }


VTBB_BIND_VERTICES = {
    "name": "poptools.vtbb_bind_vertices",
    "description": (
        "Snap each empty in the VTBB_Empties collection to the nearest vertex "
        "on the target mesh. The target mesh name can be passed explicitly or "
        "falls back to the scene's vertex_baker_settings.target_mesh."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_mesh": {
                "type": "string",
                "description": "Name of the target mesh object.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_bind_vertices,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# poptools.vtbb_bake_weights
# ===========================================================================

def _handler_bake_weights(context=None, target_mesh: str = "") -> dict:
    if context is None:
        context = bpy.context

    # Resolve target mesh
    mesh = None
    if target_mesh:
        mesh = bpy.data.objects.get(target_mesh)
    if not mesh:
        props = getattr(context.scene, "poptools_props", None)
        vs = getattr(props, "vertex_baker_settings", None) if props else None
        mesh = getattr(vs, "target_mesh", None) if vs else None
    if not mesh or mesh.type != "MESH":
        return {"ok": False, "error_kind": "wrong_type",
                "error": "No valid target mesh specified."}

    empties = _get_empties()
    if not empties:
        return {"ok": False, "error_kind": "no_empties",
                "error": "No empties found. Run vtbb_create_empties first."}

    # Ensure vertex groups exist for each empty
    for empty in empties:
        group_name = empty.name.replace("empty_", "")
        if group_name not in mesh.vertex_groups:
            mesh.vertex_groups.new(name=group_name)

    # Read mesh vertices via bmesh
    override = _viewport_override(context)
    bm = bmesh.new()
    try:
        with context.temp_override(**override):
            context.view_layer.objects.active = mesh
            bpy.ops.object.mode_set(mode="EDIT")
            bm.from_mesh(mesh.data)
            bm.verts.ensure_lookup_table()
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        bm.free()
        return {"ok": False, "error_kind": "bmesh_failed",
                "error": "Failed to read mesh vertices."}

    baked_count = 0
    try:
        for empty in empties:
            group_name = empty.name.replace("empty_", "")
            vertex_group = mesh.vertex_groups.get(group_name)
            if not vertex_group:
                continue

            for vert in bm.verts:
                vert_world = mesh.matrix_world @ vert.co
                distance = (empty.location - vert_world).length
                weight = 1.0 / (1.0 + distance) if distance > 0 else 1.0
                weight = max(0.0, min(1.0, weight))
                vertex_group.add([vert.index], weight, "REPLACE")

            baked_count += 1
    finally:
        bm.free()

    return {
        "ok": True,
        "baked_count": baked_count,
        "message": f"Baked weights for {baked_count} vertex group(s).",
    }


VTBB_BAKE_WEIGHTS = {
    "name": "poptools.vtbb_bake_weights",
    "description": (
        "Bake empty-object positions into vertex weights on the target mesh. "
        "For each empty, creates a vertex group (named after the bone) and "
        "assigns weights inversely proportional to vertex distance."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target_mesh": {
                "type": "string",
                "description": "Name of the target mesh object.",
            },
        },
        "required": [],
    },
    "owner": "poptools",
    "handler": _handler_bake_weights,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}


# ===========================================================================
# poptools.vtbb_clear_empties
# ===========================================================================

def _handler_clear_empties(context=None) -> dict:
    if context is None:
        context = bpy.context

    col = bpy.data.collections.get(_COLLECTION_NAME)
    if not col:
        return {"ok": False, "error_kind": "not_found",
                "error": "VTBB_Empties collection not found."}

    empties = [o for o in col.objects if o.type == "EMPTY"]
    if not empties:
        return {"ok": False, "error_kind": "empty_collection",
                "error": "No empties in the collection."}

    count = len(empties)
    for empty in empties:
        bpy.data.objects.remove(empty, do_unlink=True)
    bpy.data.collections.remove(col)

    return {
        "ok": True,
        "removed_count": count,
        "message": f"Removed {count} empty(s) and the VTBB_Empties collection.",
    }


VTBB_CLEAR_EMPTIES = {
    "name": "poptools.vtbb_clear_empties",
    "description": (
        "Delete all empty objects in the VTBB_Empties collection and remove "
        "the collection itself. Use after the baking workflow is complete."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_clear_empties,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}
