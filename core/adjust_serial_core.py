# -*- coding: utf-8 -*-
"""Pure-function layer for the adjust_serial_number skill.

No bpy.  Computes the new serial value from current + delta with
floor clamping.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class AdjustSerialResult:
    ok: bool
    old_value: int = 0
    new_value: int = 0
    new_value_str: str = ""
    message: str = ""
    error_kind: str = ""
    error: str = ""


def adjust_serial(current_value: str, delta=1,
                  min_value=1,
                  zero_pad: bool = True) -> AdjustSerialResult:
    """Return the adjusted serial number string.  Pure: no side effects.

    Parameters
    ----------
    current_value : str
        Current serial as a decimal string (e.g. "01").
    delta : int | str
        Amount to add (positive) or subtract (negative). Strings are
        coerced (the schema permits string args from the LLM).
    min_value : int | str
        Floor clamp for the result. Strings are coerced.
    zero_pad : bool
        When True, format result as two-digit zero-padded ("01").
    """
    try:
        delta = int(delta)
        min_value = int(min_value)
    except (ValueError, TypeError):
        return AdjustSerialResult(
            ok=False, error_kind="invalid_arguments",
            error=f"delta '{delta}' 和 min_value '{min_value}' 必须是整数。",
        )

    try:
        current_int = int(current_value)
    except (ValueError, TypeError):
        return AdjustSerialResult(
            ok=False, error_kind="invalid_serial",
            error=f"当前序号 '{current_value}' 不是一个有效的数字。",
        )

    new_int = max(current_int + delta, min_value)
    new_str = f"{new_int:02d}" if zero_pad else str(new_int)

    return AdjustSerialResult(
        ok=True,
        old_value=current_int,
        new_value=new_int,
        new_value_str=new_str,
        message=f"序号已从 {current_value} 调整为 {new_str}",
    )
