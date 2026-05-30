# -*- coding: utf-8 -*-
"""
Pure-function layer for ReTex utilities (UV inspection, smart renaming).

No bpy.ops, no context.scene.poptools_props. All functions receive explicit
parameters and return dataclass results. Operators in retex_tools.py and the
POPAgent skill handlers in agent_skills/retex_skills.py are thin wrappers that
read state and delegate here.

Objects are duck-typed: anything exposing `.name`, `.type`, and
`.data.uv_layers` works, so these functions are unit-testable without bpy.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# UV inspection
# ---------------------------------------------------------------------------

@dataclass
class UVCheckResult:
    ok: bool
    objects_with_multiple_uvs: list = field(default_factory=list)
    message: str = ""


def check_duplicate_uvs(objects) -> UVCheckResult:
    """List MESH objects that carry more than one UV map.

    Mirrors RT_OT_CheckUVs (retex_tools.py). Read-only: no side effects.
    """
    flagged = []
    for obj in objects or []:
        if getattr(obj, "type", None) != "MESH":
            continue
        data = getattr(obj, "data", None)
        uv_layers = getattr(data, "uv_layers", None)
        if uv_layers is not None and len(uv_layers) > 1:
            flagged.append(obj.name)

    if flagged:
        message = f"发现 {len(flagged)} 个模型有多个 UV Map"
    else:
        message = "所有模型 UV 正常，无重复 UV Map"
    return UVCheckResult(ok=True, objects_with_multiple_uvs=flagged, message=message)


# ---------------------------------------------------------------------------
# Smart rename
# ---------------------------------------------------------------------------

# Letter prefix -> canonical type name. From RT_OT_SmartRenameObjects.
SMART_RENAME_TYPE_MAP = {
    "b": "balloon",
    "h": "hand",
    "p": "prop",
    "c": "cap",
}


@dataclass
class SmartRenameResult:
    ok: bool
    renamed: list = field(default_factory=list)   # [{"old_name", "new_name"}]
    errors: list = field(default_factory=list)
    message: str = ""


def _extract_type_and_number(name: str) -> tuple[str | None, str | None]:
    """Pull a (letter-prefix, number) pair out of a raw object name.

    Accepts letters-then-digits or digits-then-letters. Returns lowercased
    prefix and the digit run, or (None, None) if neither pattern matches.
    """
    letter_first = re.search(r"([a-zA-Z]+).*?(\d+)", name)
    if letter_first:
        return letter_first.group(1).lower(), letter_first.group(2)
    number_first = re.search(r"(\d+).*?([a-zA-Z]+)", name)
    if number_first:
        return number_first.group(2).lower(), number_first.group(1)
    return None, None


def build_smart_rename(
    objects,
    item_land: str,
    existing_names,
    type_mapping: dict | None = None,
) -> SmartRenameResult:
    """Compute new names for objects following the smart-rename convention.

    Produces names like 'mesh_item_{item_land}_{type}_{NN}'. Pure planner:
    does NOT mutate objects. The caller applies obj.name from `renamed`.
    Collision detection considers both pre-existing names and names already
    planned in this batch.
    """
    mapping = type_mapping if type_mapping is not None else SMART_RENAME_TYPE_MAP
    taken = set(existing_names or set())
    renamed: list[dict] = []
    errors: list[str] = []

    for obj in objects or []:
        old_name = obj.name
        type_prefix, number = _extract_type_and_number(old_name)

        if not (type_prefix and number):
            errors.append(f"对象 '{old_name}' 重命名失败：名称中未找到有效的字母和数字组合")
            continue
        if type_prefix not in mapping:
            errors.append(f"对象 '{old_name}' 重命名失败：未知类型前缀 '{type_prefix}'")
            continue

        new_name = f"mesh_item_{item_land}_{mapping[type_prefix]}_{number:0>2}"
        if new_name in taken:
            errors.append(f"对象 '{old_name}' 重命名失败：名称 '{new_name}' 已存在")
            continue

        taken.add(new_name)
        renamed.append({"old_name": old_name, "new_name": new_name})

    if renamed:
        message = f"可重命名 {len(renamed)} 个对象"
    else:
        message = "没有对象可被重命名"
    return SmartRenameResult(
        ok=bool(renamed), renamed=renamed, errors=errors, message=message
    )
