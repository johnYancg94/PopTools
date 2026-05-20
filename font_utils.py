# -*- coding: utf-8 -*-
"""Shared font loading helpers for PopTools viewport overlays."""

import os

import blf


_FONT_CACHE = {}
FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
MIKADO_BLACK_FONT_PATH = os.path.join(FONTS_DIR, "Mikado Black.otf")


def load_font(font_path):
    """Load a BLF font once and return its font id, falling back to Blender default."""
    if not font_path or not os.path.exists(font_path):
        return 0

    cached_font_id = _FONT_CACHE.get(font_path)
    if cached_font_id is not None:
        return cached_font_id

    try:
        font_id = blf.load(font_path)
    except Exception as exc:
        print(f"[PopTools字体] 加载字体失败: {font_path} - {exc}")
        font_id = 0

    _FONT_CACHE[font_path] = font_id
    return font_id


def get_mikado_black_font_id():
    """Return the Mikado Black font id when bundled, otherwise Blender's default font."""
    return load_font(MIKADO_BLACK_FONT_PATH)
