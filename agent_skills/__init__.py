# poptools/agent_skills/__init__.py
"""
PopTools agent skills — registered into POPAgent's skill registry when both
addons are active.

Import guard: if POPAgent is not installed, registration is silently skipped.
"""

from __future__ import annotations
from .export_skills import EXPORT_FBX, EXPORT_OBJ, EXPORT_GLTF
from .naming_skills import (
    APPLY_ACTION_NAMING,
    APPLY_GENERIC_NAMING,
    PREVIEW_GENERIC_NAMES,
    BUILD_TEXTURE_NAME,
    RETEX_NAME_FROM_ACTIVE,
)
from .retex_skills import (
    CHECK_UVS,
    SMART_RENAME,
    ORGANIZE_MATERIALS,
    MARK_HIGH_LOW,
    RENAME_BY_CATEGORY,
    SET_TEXNAME_OF_OBJECT,
    SYNC_TEXTURE_NAMES,
    ADJUST_SERIAL_NUMBER,
)
from .obj_export_skills import EXPORT_OBJ_BATCH, OPEN_EXPORT_DIR
from .marmoset_skills import (
    AUTO_MARK_HIGH_LOW,
    SHOW_POLYCOUNT,
    FIND_MISSING_TEXTURES,
    GENERATE_LOWPOLY,
    SECURE_TEXTURE_RESOURCES,
    AUTO_DETECT_TOOLBAG,
)
from .vertex_baker_skills import (
    VTBB_CREATE_EMPTIES,
    VTBB_BIND_VERTICES,
    VTBB_BAKE_WEIGHTS,
    VTBB_CLEAR_EMPTIES,
)

_ALL_SKILLS = [
    EXPORT_FBX,
    EXPORT_OBJ,
    EXPORT_GLTF,
    APPLY_ACTION_NAMING,
    APPLY_GENERIC_NAMING,
    PREVIEW_GENERIC_NAMES,
    BUILD_TEXTURE_NAME,
    RETEX_NAME_FROM_ACTIVE,
    CHECK_UVS,
    SMART_RENAME,
    ORGANIZE_MATERIALS,
    MARK_HIGH_LOW,
    RENAME_BY_CATEGORY,
    SET_TEXNAME_OF_OBJECT,
    SYNC_TEXTURE_NAMES,
    ADJUST_SERIAL_NUMBER,
    EXPORT_OBJ_BATCH,
    OPEN_EXPORT_DIR,
    AUTO_MARK_HIGH_LOW,
    SHOW_POLYCOUNT,
    FIND_MISSING_TEXTURES,
    GENERATE_LOWPOLY,
    SECURE_TEXTURE_RESOURCES,
    AUTO_DETECT_TOOLBAG,
    VTBB_CREATE_EMPTIES,
    VTBB_BIND_VERTICES,
    VTBB_BAKE_WEIGHTS,
    VTBB_CLEAR_EMPTIES,
]

_OWNER_PREFIX = "poptools"


def register() -> None:
    """Register all PopTools skills into POPAgent's registry (if available)."""
    try:
        from POPAgent.agent_core import skill_registry
    except ImportError:
        return

    for skill in _ALL_SKILLS:
        skill_registry.register_skill(skill)


def unregister() -> None:
    """Remove all PopTools skills from POPAgent's registry (if available)."""
    try:
        from POPAgent.agent_core import skill_registry
    except ImportError:
        return

    skill_registry.unregister_namespace(_OWNER_PREFIX)
