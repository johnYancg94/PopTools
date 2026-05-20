# -*- coding: utf-8 -*-
"""Naming helpers for ReTex tools."""


def build_texture_name_from_object_name(object_name, replace_prefix=True, texture_suffix=""):
    """Build a texture name from an object name.

    ``mesh_`` is the only object prefix that should be replaced. Names without
    that prefix are treated as the actual asset name and receive ``tex_``.
    """
    new_name = object_name
    suffix = (texture_suffix or "").strip()

    if suffix:
        new_name = f"{new_name}_{suffix}"

    if not replace_prefix:
        return new_name

    if new_name.startswith("tex_"):
        return new_name
    if new_name.startswith("mesh_"):
        return "tex_" + new_name[len("mesh_"):]
    return "tex_" + new_name
