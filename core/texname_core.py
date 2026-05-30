# -*- coding: utf-8 -*-
"""Pure-function layer for the set_texname_of_object skill.

No bpy.  Plans texture file renames derived from object names, with
disk-path collision avoidance.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class TexnameResult:
    ok: bool
    planned: list = field(default_factory=list)   # [{old_path, new_path, image_name, new_tex_name}]
    errors: list = field(default_factory=list)
    message: str = ""


def coerce_bool(value, default: bool = True) -> bool:
    """Coerce an LLM-supplied value to bool.

    The skill schema permits string args, so a string 'false'/'0'/'no' must
    not read as truthy. Unrecognized strings fall back to *default*.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("false", "0", "no", "off", ""):
            return False
        if v in ("true", "1", "yes", "on"):
            return True
        return default
    if value is None:
        return default
    return bool(value)


def build_texture_name(object_name: str, replace_prefix: bool = True,
                       texture_suffix: str = "") -> str:
    """Derive a texture name from an object name.

    ``mesh_`` → ``tex_`` when *replace_prefix* is True.  Other prefixes
    get ``tex_`` prepended.  Names already starting with ``tex_`` are
    left as-is.
    """
    name = object_name
    suffix = (texture_suffix or "").strip()
    if suffix:
        name = f"{name}_{suffix}"
    if not replace_prefix:
        return name
    if name.startswith("tex_"):
        return name
    if name.startswith("mesh_"):
        return "tex_" + name[len("mesh_"):]
    return "tex_" + name


def plan_texture_renames(
    objects,
    replace_prefix: bool = True,
    texture_suffix: str = "",
) -> TexnameResult:
    """Plan file renames for image textures on *objects*.

    For each selected object whose first material has TEX_IMAGE nodes
    with linked images, computes a new filename derived from the object
    name.  Handles on-disk collision by appending ``_N``.

    Parameters
    ----------
    objects : iterable
        Duck-typed items with ``.name``, ``.material_slots`` (list of
        items with ``.material``), where ``material.node_tree.nodes``
        yields items with ``.type``, ``.image`` (with ``.name``,
        ``.filepath``).
    """
    planned: list[dict] = []
    errors: list[str] = []
    used_paths: set[str] = set()

    for obj in (objects or []):
        slots = getattr(obj, "material_slots", None) or []
        if not slots:
            continue

        material = getattr(slots[0], "material", None)
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

            directory = os.path.dirname(filepath)
            extension = os.path.splitext(filepath)[1]

            new_name = build_texture_name(
                obj.name,
                replace_prefix=replace_prefix,
                texture_suffix=texture_suffix,
            )
            new_path = os.path.join(directory, new_name + extension)

            # Collision avoidance on disk
            counter = 1
            while (os.path.exists(new_path) and new_path != filepath) or new_path in used_paths:
                new_name = build_texture_name(
                    f"{obj.name}_{counter}",
                    replace_prefix=replace_prefix,
                    texture_suffix=texture_suffix,
                )
                new_path = os.path.join(directory, new_name + extension)
                counter += 1

            if new_path != filepath:
                used_paths.add(new_path)
                planned.append({
                    "old_path": filepath,
                    "new_path": new_path,
                    "image_name": getattr(image, "name", ""),
                    "new_tex_name": new_name,
                })

    msg = f"可重命名 {len(planned)} 个纹理" if planned else "没有纹理需要重命名"
    return TexnameResult(ok=bool(planned), planned=planned, errors=errors, message=msg)
