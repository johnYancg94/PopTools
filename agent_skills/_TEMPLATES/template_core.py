# -*- coding: utf-8 -*-
"""
TEMPLATE — core pure-function layer (Pattern 1).

Copy to `poptools/core/<domain>_core.py` and rename. This layer holds the
business algorithm with NO Blender dependency so it can be unit-tested with
plain Python. See CONVENTIONS.md §9.

Rules enforced here:
  - Never `import bpy`. Never read `context.scene.*`.
  - All environment state (selected objects, existing names, panel settings)
    arrives as explicit parameters.
  - Use `getattr(obj, "attr", None)` so duck-typed fakes work in tests.
  - "Plan, don't apply": return a description of what should change; the
    skill handler performs the actual `obj.name = ...` mutation.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ExampleResult:
    ok: bool
    planned: list = field(default_factory=list)   # e.g. [{"old_name", "new_name"}]
    errors: list = field(default_factory=list)
    message: str = ""
    # Add `error: str = ""` / `error_kind: str = ""` if the function itself
    # can fail in a categorized way (see SmartRenameResult in retex_core.py).


def build_example_plan(objects, suffix: str, existing_names) -> ExampleResult:
    """Compute a rename plan. Pure: does NOT mutate any object.

    `existing_names` is passed in (not read from bpy.data) so collision
    detection is testable. The batch's own planned names also count as taken.
    """
    taken = set(existing_names or set())
    planned: list[dict] = []
    errors: list[str] = []

    for obj in objects or []:
        name = getattr(obj, "name", None)
        if not name:
            continue
        if getattr(obj, "type", None) != "MESH":
            errors.append(f"对象 '{name}' 跳过：不是网格")
            continue

        new_name = f"{name}{suffix}"
        if new_name in taken:
            errors.append(f"对象 '{name}' 失败：名称 '{new_name}' 已存在")
            continue

        taken.add(new_name)
        planned.append({"old_name": name, "new_name": new_name})

    message = f"可处理 {len(planned)} 个对象" if planned else "没有可处理的对象"
    return ExampleResult(ok=bool(planned), planned=planned, errors=errors, message=message)
