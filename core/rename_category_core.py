# -*- coding: utf-8 -*-
"""Pure-function layer for the rename_by_category skill.

Merges seven operators (character_body/hair/tool, animal, building,
minigame, generic) into a single category-based planner.  No bpy,
no context.scene reads — all state arrives as explicit parameters.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


# Inlined from generic_model_naming.py (only imports re, safe to duplicate).
def _sanitize_identifier(text):
    normalized = (text or "").strip()
    parts = re.split(r"[^a-zA-Z0-9]+", normalized)
    parts = [part for part in parts if part]
    if not parts:
        return ""
    first = parts[0].lower()
    rest = [p[:1].upper() + p[1:].lower() for p in parts[1:]]
    return first + "".join(rest)


def _build_sequential_names(activity_type, model_name, count, existing_names,
                            suffix=""):
    names = []
    taken = set(existing_names or set())
    serial = 1
    sf = _sanitize_identifier(suffix)
    while len(names) < count:
        if sf:
            candidate = f"mesh_{activity_type}_{model_name}_{sf}{serial:02d}"
        else:
            candidate = f"mesh_{activity_type}_{model_name}{serial:02d}"
        if candidate not in taken:
            names.append(candidate)
            taken.add(candidate)
        serial += 1
    return names


@dataclass
class RenameCategoryResult:
    ok: bool
    planned: list = field(default_factory=list)   # [{"old_name", "new_name"}]
    errors: list = field(default_factory=list)
    message: str = ""
    error_kind: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Per-category name builders
# ---------------------------------------------------------------------------

def _fmt_serial(n: int) -> str:
    return f"{n:02d}"


def _build_simple_name(body_type: str, serial_str: str, suffix: str, category: str):
    """Build the new name for character_body/hair/tool/animal categories.

    Formats (from the original operators):
      character_body:  mesh_characters_{type}_{NN}[_{suffix}]
      character_hair:  mesh_head_{type}_head{NN}[_{suffix}]
      character_tool:  mesh_buildtools_{type}_{NN}{suffix}   (suffix required, concatenated)
      animal:          mesh_special_{type}_{NN}[_{suffix}]
    """
    if category == "character_hair":
        base = f"mesh_head_{body_type}_head{serial_str}"
        return f"{base}_{suffix}" if suffix else base
    if category == "character_tool":
        return f"mesh_buildtools_{body_type}_{serial_str}{suffix}"
    # character_body, animal
    prefix = "mesh_characters" if category == "character_body" else "mesh_special"
    base = f"{prefix}_{body_type}_{serial_str}"
    return f"{base}_{suffix}" if suffix else base


_SIMPLE_CATEGORIES = {"character_body", "character_hair", "character_tool", "animal"}


# ---------------------------------------------------------------------------
# Building  (auto-increment serial, collision-safe)
# ---------------------------------------------------------------------------

def _plan_building(objects, building_type, island_name, building_name,
                   existing_names) -> RenameCategoryResult:
    taken = set(existing_names or set())
    planned: list[dict] = []
    errors: list[str] = []
    serial = 1

    for obj in (objects or []):
        if getattr(obj, "type", None) != "MESH":
            continue
        while True:
            candidate = f"mesh_{building_type}_{island_name}_{building_name}{serial:02d}"
            if candidate not in taken:
                break
            serial += 1
        taken.add(candidate)
        planned.append({"old_name": obj.name, "new_name": candidate})
        serial += 1

    msg = f"可重命名 {len(planned)} 个建筑对象" if planned else "没有建筑对象可重命名"
    return RenameCategoryResult(ok=bool(planned), planned=planned, errors=errors, message=msg)


# ---------------------------------------------------------------------------
# Minigame  (collision-safe with _NN suffix)
# ---------------------------------------------------------------------------

_GAMEPLAY_MAP = {"cleanup": "cleanupminigame"}
_SCENE_MAP = {"bedroom": "bedroom", "livingroom": "livingroom"}


def _plan_minigame(objects, gameplay, scene, item_name,
                   existing_names) -> RenameCategoryResult:
    taken = set(existing_names or set())
    planned: list[dict] = []
    errors: list[str] = []

    gameplay_en = _GAMEPLAY_MAP.get(gameplay, gameplay)
    scene_en = _SCENE_MAP.get(scene, scene)
    base = f"mesh_{gameplay_en}_{scene_en}_{item_name}"

    for obj in (objects or []):
        if getattr(obj, "type", None) != "MESH":
            continue
        candidate = base
        counter = 1
        while candidate in taken:
            candidate = f"{base}_{counter:02d}"
            counter += 1
        taken.add(candidate)
        planned.append({"old_name": obj.name, "new_name": candidate})

    msg = f"可重命名 {len(planned)} 个 minigame 对象" if planned else "没有 minigame 对象可重命名"
    return RenameCategoryResult(ok=bool(planned), planned=planned, errors=errors, message=msg)


# ---------------------------------------------------------------------------
# Generic  (delegates to build_sequential_names)
# ---------------------------------------------------------------------------

def _plan_generic(objects, activity_type, model_name, suffix,
                  existing_names) -> RenameCategoryResult:
    taken = set(existing_names or set())
    mesh_objs = [o for o in (objects or []) if getattr(o, "type", None) == "MESH"]
    if not mesh_objs:
        return RenameCategoryResult(
            ok=False, error_kind="no_selection",
            error="No selected mesh objects.",
        )

    sorted_objs = sorted(mesh_objs, key=lambda o: o.name.lower())
    new_names = _build_sequential_names(
        activity_type=activity_type,
        model_name=model_name,
        count=len(sorted_objs),
        existing_names=taken,
        suffix=suffix,
    )
    planned = [{"old_name": o.name, "new_name": n}
               for o, n in zip(sorted_objs, new_names)]

    msg = f"可重命名 {len(planned)} 个对象" if planned else "没有对象可重命名"
    return RenameCategoryResult(ok=bool(planned), planned=planned, message=msg)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_rename_plan(
    category: str,
    objects,
    existing_names,
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
) -> RenameCategoryResult:
    """Compute a rename plan for *category*.  Pure: does NOT mutate objects."""

    if category in ("building", "minigame", "generic"):
        return _dispatch_special(
            category, objects, existing_names,
            building_type, island_name, building_name,
            gameplay, scene, item_name,
            activity_type, model_name, suffix,
        )

    if category not in _SIMPLE_CATEGORIES:
        return RenameCategoryResult(
            ok=False, error_kind="invalid_category",
            error=f"Unknown category '{category}'.",
        )

    # Validate required params for simple categories
    if not body_type:
        return RenameCategoryResult(
            ok=False, error_kind="missing_body_type",
            error=f"body_type is required for category '{category}'.",
        )
    if not serial_number:
        return RenameCategoryResult(
            ok=False, error_kind="missing_serial_number",
            error=f"serial_number is required for category '{category}'.",
        )

    # Resolve suffix — character_tool requires it
    effective_suffix = suffix
    if category == "character_tool" and not effective_suffix:
        return RenameCategoryResult(
            ok=False, error_kind="missing_suffix",
            error="Suffix is required for character_tool category.",
        )

    serial_str = _fmt_serial(int(serial_number))
    taken = set(existing_names or set())
    planned: list[dict] = []
    errors: list[str] = []

    for obj in (objects or []):
        name = getattr(obj, "name", None)
        if not name:
            continue
        if getattr(obj, "type", None) != "MESH":
            errors.append(f"对象 '{name}' 跳过：不是网格")
            continue

        new_name = _build_simple_name(body_type, serial_str, effective_suffix, category)

        if new_name in taken:
            errors.append(f"对象 '{name}' 重命名失败：名称 '{new_name}' 已存在")
            continue
        taken.add(new_name)
        planned.append({"old_name": name, "new_name": new_name})

    msg = f"可重命名 {len(planned)} 个对象" if planned else "没有对象可重命名"
    return RenameCategoryResult(ok=bool(planned), planned=planned, errors=errors, message=msg)


def _dispatch_special(category, objects, existing_names,
                      building_type, island_name, building_name,
                      gameplay, scene, item_name,
                      activity_type, model_name, suffix):
    if category == "building":
        if not building_type or not island_name or not building_name:
            return RenameCategoryResult(
                ok=False, error_kind="missing_building_params",
                error="building_type, island_name, and building_name are required.",
            )
        return _plan_building(objects, building_type, island_name, building_name,
                              existing_names)

    if category == "minigame":
        if not item_name:
            return RenameCategoryResult(
                ok=False, error_kind="missing_item_name",
                error="item_name is required for minigame category.",
            )
        return _plan_minigame(objects, gameplay, scene, item_name, existing_names)

    if category == "generic":
        if not activity_type or not model_name:
            return RenameCategoryResult(
                ok=False, error_kind="missing_generic_params",
                error="activity_type and model_name are required for generic category.",
            )
        return _plan_generic(objects, activity_type, model_name, suffix, existing_names)

    return RenameCategoryResult(
        ok=False, error_kind="invalid_category",
        error=f"Unknown category '{category}'.",
    )
