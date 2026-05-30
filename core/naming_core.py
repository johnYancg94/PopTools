# -*- coding: utf-8 -*-
"""
Pure-function layer for action (animation clip) naming.

No bpy.ops, no context.scene.poptools_props.
All functions receive explicit parameters and return dataclass results.
Operators in action_naming_tools.py are thin wrappers that read props
and delegate here.
"""

from __future__ import annotations
import re
import bpy
from dataclasses import dataclass
from ..generic_model_naming import build_sequential_names, sanitize_identifier


@dataclass
class NamingResult:
    ok: bool
    new_name: str = ""
    old_name: str = ""
    message: str = ""


@dataclass
class BatchNamingResult:
    ok: bool
    renamed: list[dict] | None = None
    message: str = ""
    error: str = ""
    error_kind: str = ""


# ---------------------------------------------------------------------------
# Name construction
# ---------------------------------------------------------------------------

def build_action_name(animation_type: str, animation_name: str,
                      island_name: str = "") -> tuple[bool, str]:
    """Construct the canonical action name from components.

    Returns (ok, name_or_error_message).
    """
    if not animation_type:
        return False, "请先选择动画类型"
    if not animation_name.strip():
        return False, "请先输入动画名称"

    if animation_type == "npc_island":
        if not island_name.strip():
            return False, "海岛动画类型需要输入海岛名"
        return True, f"ani_npc_{island_name}_{animation_name}"

    return True, f"ani_{animation_type}_{animation_name}"


def get_unique_action_name(base_name: str) -> str:
    """Return base_name if unique in bpy.data.actions, else increment suffix."""
    existing = {a.name for a in bpy.data.actions}
    if base_name not in existing:
        return base_name

    match = re.match(r"(.+?)(\d+)$", base_name)
    if match:
        name_part, start_num = match.group(1), int(match.group(2))
    else:
        name_part, start_num = base_name, 1

    counter = start_num
    while True:
        candidate = f"{name_part}{counter:02d}"
        if candidate not in existing:
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# Suffix adjustment
# ---------------------------------------------------------------------------

def adjust_number_suffix(name: str, delta: int) -> tuple[bool, str]:
    """Increment or decrement the trailing numeric suffix by delta.

    Returns (ok, new_name_or_error).
    """
    if not name.strip():
        return False, "动画名称为空"

    match = re.search(r"(.+?)(\d+)$", name.strip())
    if not match:
        if delta > 0:
            return True, name.strip() + "01"
        return False, "动画名称末尾没有找到数字序号"

    name_part = match.group(1)
    current_num = int(match.group(2))
    new_num = current_num + delta

    if new_num < 1:
        return False, "序号不能减少到00或更小"

    return True, f"{name_part}{new_num:02d}"


# ---------------------------------------------------------------------------
# Rename + AC_Settings tag update
# ---------------------------------------------------------------------------

def rename_action_on_object(
    obj: bpy.types.Object,
    animation_type: str,
    animation_name: str,
    island_name: str = "",
    chinese_comment: str = "",
) -> NamingResult:
    """Rename the action on obj according to naming rules.

    Side effects: modifies action.name and optionally action.AC_Settings.tags.
    Must be called from the main thread.
    """
    if not obj:
        return NamingResult(ok=False, message="没有活动对象")
    if not (obj.animation_data and obj.animation_data.action):
        return NamingResult(ok=False, message="选中的对象没有动作数据")

    ok, payload = build_action_name(animation_type, animation_name, island_name)
    if not ok:
        return NamingResult(ok=False, message=payload)

    new_name = payload
    old_name = obj.animation_data.action.name
    obj.animation_data.action.name = new_name

    tag_status = ""
    if chinese_comment.strip():
        try:
            action = bpy.data.actions.get(new_name)
            if action and hasattr(action, "AC_Settings"):
                action.AC_Settings.tags = chinese_comment.strip()
                tag_status = f"，标签已更新: {chinese_comment}"
            else:
                tag_status = "，未找到AC_Settings.tags属性"
        except Exception as exc:
            tag_status = f"，标签更新失败: {exc}"

    return NamingResult(
        ok=True,
        new_name=new_name,
        old_name=old_name,
        message=f"动作重命名成功: {old_name} -> {new_name}{tag_status}",
    )


def apply_generic_model_naming(
    objects: list,
    activity_type: str,
    model_name: str,
    suffix: str = "",
    existing_objects: list | None = None,
) -> BatchNamingResult:
    """Rename selected mesh objects using the generic model naming rule.

    Side effects: modifies object.name and object.data.name.
    Must be called from the main thread.
    """
    mesh_objects = [obj for obj in objects or [] if getattr(obj, "type", None) == "MESH"]
    if not mesh_objects:
        return BatchNamingResult(
            ok=False,
            error_kind="no_mesh_selection",
            error="No selected mesh objects to rename.",
        )

    resolved_activity_type = sanitize_identifier(activity_type)
    resolved_model_name = sanitize_identifier(model_name)
    resolved_suffix = sanitize_identifier(suffix)

    if not resolved_activity_type:
        return BatchNamingResult(
            ok=False,
            error_kind="missing_activity_type",
            error="activity_type is required.",
        )
    if not resolved_model_name:
        return BatchNamingResult(
            ok=False,
            error_kind="missing_model_name",
            error="model_name is required.",
        )

    existing_names = {
        obj.name
        for obj in (existing_objects if existing_objects is not None else bpy.data.objects)
        if obj not in mesh_objects
    }
    sorted_objects = sorted(mesh_objects, key=lambda obj: obj.name.lower())
    new_names = build_sequential_names(
        activity_type=resolved_activity_type,
        model_name=resolved_model_name,
        count=len(sorted_objects),
        existing_names=existing_names,
        suffix=resolved_suffix,
    )

    renamed = []
    for obj, new_name in zip(sorted_objects, new_names):
        old_name = obj.name
        old_data_name = obj.data.name if getattr(obj, "data", None) else ""
        obj.name = new_name
        if getattr(obj, "data", None):
            obj.data.name = new_name
        renamed.append(
            {
                "old_name": old_name,
                "new_name": new_name,
                "old_data_name": old_data_name,
                "new_data_name": new_name if getattr(obj, "data", None) else "",
            }
        )

    return BatchNamingResult(
        ok=True,
        renamed=renamed,
        message=f"Renamed {len(renamed)} mesh object(s).",
    )
