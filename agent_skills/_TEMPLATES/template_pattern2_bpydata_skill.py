# -*- coding: utf-8 -*-
"""
TEMPLATE — Pattern 2 skill, direct bpy.data (no bpy.ops, no popup).

Copy into a `poptools/agent_skills/<domain>_skills.py` and rename. Use this
variant when the underlying operator only mutates `bpy.data` + assigns names
AND pops a `show_message_box` (e.g. rt.organize_selected_materials,
poptools.marmoset_mark_*). We REPLICATE the data mutation here so the agent
path stays popup-free. Do NOT call `bpy.ops.rt.*` — that would re-trigger the
modal message box. See CONVENTIONS.md §2.

If the operator needs viewport/selection context, use the temp_override
variant instead (template_pattern2_ops_override_skill.py).
"""

from __future__ import annotations
import bpy


def _handler_example(context=None) -> dict:
    if context is None:
        context = bpy.context

    objects = [o for o in context.selected_objects if o.type == "MESH"]
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No selected mesh objects."}

    # Wrap predictable failures; an uncaught raise becomes an opaque
    # handler_exception (information lost). See §6.
    done = []
    try:
        for obj in objects:
            # --- replicate the operator's bpy.data mutation here ---
            if obj.data and obj.data.materials:
                obj.data.materials.clear()
            mat = bpy.data.materials.new(name=obj.name)
            mat.use_nodes = True
            obj.data.materials.append(mat)
            done.append(obj.name)
    except Exception as exc:
        return {"ok": False, "error_kind": "example_failed", "error": str(exc)}

    return {
        "ok": True,
        "processed": done,
        "message": f"成功处理 {len(done)} 个对象",
    }


EXAMPLE_SKILL = {
    "name": "poptools.example_action",
    "description": (
        "One-line purpose. "
        "Requires mesh objects to be selected first. "
        "Destructive — note what existing data is removed."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
    "owner": "poptools",
    "handler": _handler_example,
    "metadata": {
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,
        "requires_confirmation": "first",   # reversible via Ctrl+Z; if it wrote files/deleted irreversibly => "always"
    },
}
