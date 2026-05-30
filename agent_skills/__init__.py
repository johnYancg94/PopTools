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
