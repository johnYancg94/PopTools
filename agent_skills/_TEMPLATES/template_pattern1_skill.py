# -*- coding: utf-8 -*-
"""
TEMPLATE — Pattern 1 skill (handler delegates to a core pure function).

Copy into an existing `poptools/agent_skills/<domain>_skills.py` (or a new one)
and rename. Pattern 1 = the algorithm lives in `core/<domain>_core.py` (pure,
testable); this handler only reads Blender state, calls the pure function, and
applies the resulting plan. See CONVENTIONS.md §2 (decision tree) and §7.

Choose Pattern 1 when the logic is worth unit-testing (naming rules, numbering,
collision detection, name derivation, size math).
"""

from __future__ import annotations
import bpy

# Real import would be: from ..core.example_core import build_example_plan
# (template keeps it local so the file compiles standalone)
def build_example_plan(objects, suffix, existing_names):  # placeholder
    raise NotImplementedError


def _handler_example(context=None, suffix: str = "_suffix") -> dict:
    # Iron rule: context fallback (executor always passes context=context, but
    # pure-Python callers / tests may not).
    if context is None:
        context = bpy.context

    # Read selection; bail early with a structured error (never let a later
    # bpy call explode into an opaque handler_exception).
    objects = list(context.selected_objects)
    if not objects:
        return {"ok": False, "error_kind": "no_selection",
                "error": "No objects selected."}

    # Collect environment state HERE, pass it into the pure function.
    existing = {o.name for o in bpy.data.objects}
    plan = build_example_plan(objects, suffix=suffix, existing_names=existing)

    # Apply the plan (defend against objects vanishing mid-batch).
    applied = []
    for entry in plan.planned:
        obj = bpy.data.objects.get(entry["old_name"])
        if obj is None:
            plan.errors.append(f"对象 '{entry['old_name']}' 失败：已不存在")
            continue
        obj.name = entry["new_name"]
        applied.append(entry)

    return {
        "ok": bool(applied),
        "applied": applied,
        "errors": plan.errors,
        "message": f"成功处理 {len(applied)} 个对象" if applied else "没有对象被处理",
    }


EXAMPLE_SKILL = {
    "name": "poptools.example_action",          # §3: poptools.<action>, search first to avoid collisions
    "description": (                            # §8: English, 3 parts, ≤4 sentences
        "One-line purpose. "
        "Precondition, e.g. 'Requires mesh objects to be selected first.' "
        "What it returns / key parameter semantics."
    ),
    "parameters": {                             # §4: only type/required/enum honored
        "type": "object",
        "properties": {
            "suffix": {"type": "string", "description": "Suffix to append."},
        },
        "required": [],                         # only params that block the work
    },
    "owner": "poptools",                        # §3: always "poptools"
    "handler": _handler_example,
    "metadata": {                               # §5: fill from the matrix
        "modifies_scene": True,
        "writes_files": False,
        "launches_external_process": False,
        "undoable": True,                       # True => executor auto undo_push; handler must NOT push undo itself
        "requires_confirmation": "first",       # reversible (Ctrl+Z) => first; irreversible => always
    },
}
