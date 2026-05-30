# -*- coding: utf-8 -*-
"""
TEMPLATE — Pattern 2 skill, bpy.ops with temp_override.

Copy into a `poptools/agent_skills/<domain>_skills.py` and rename. Use this
variant ONLY when the work genuinely needs a bpy.ops call that depends on
viewport / selection context (e.g. transform_apply, origin_set). The agent
runs from a timer with no active 3D view, so we build an override dict.

`_override_with_objects` is copied from POPAgent/builtin_skills/blender_transform.py.
See CONVENTIONS.md §2 (decision tree, deepest branch).
"""

from __future__ import annotations
import bpy


def _override_with_objects(context, objs):
    override = {"selected_objects": objs, "active_object": objs[0], "object": objs[0]}
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


def _handler_example(context=None) -> dict:
    if context is None:
        context = bpy.context

    objs = list(context.selected_objects)
    if not objs:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No objects selected."}

    try:
        with bpy.context.temp_override(**_override_with_objects(context, objs)):
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    except Exception as exc:
        return {"ok": False, "error_kind": "example_failed", "error": str(exc)}

    return {"ok": True, "objects": [o.name for o in objs], "count": len(objs)}


EXAMPLE_SKILL = {
    "name": "poptools.example_action",
    "description": (
        "One-line purpose. "
        "Requires objects to be selected first. "
        "What it returns."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_example,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",
    },
}
