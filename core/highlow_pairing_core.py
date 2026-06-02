# -*- coding: utf-8 -*-
"""
Pure-function layer for Marmoset high/low auto-pairing.

The legacy operator helper `infer_high_low_pairs` (marmoset_baker_tools.py)
computes the pairing AND renames objects in the same pass, so it cannot be used
to "preview" a pairing without mutating the scene. This module provides a
side-effect-free dry-run: given each object's (name, complexity), it returns the
planned pairs and any leftovers WITHOUT touching real names.

The POPAgent handler runs this first; only when there are zero leftovers AND no
ambiguous pairs does it delegate to the real (mutating) operator helper to commit
the rename. This makes "failure == nothing happened" hold true for the agent.

A pair is "ambiguous" when its two members have equal polygon counts: the
algorithm cannot decide which is high and which is low, so the handler refuses to
guess and surfaces the pair for the agent to disambiguate (screenshot or ask the
user) rather than silently committing an arbitrary assignment.

Objects are duck-typed: anything exposing `.name` and `.data.polygons` /
`.data.vertices` works via the `complexity_of` helper, so this is unit-testable
without bpy.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PairingPlan:
    ok: bool
    pairs: list = field(default_factory=list)      # [{"low","high","low_polys","high_polys","ambiguous"}]
    leftovers: list = field(default_factory=list)  # names that could not pair
    ambiguous_pairs: list = field(default_factory=list)  # pairs where low/high polys are equal
    error_kind: str = ""
    message: str = ""


def complexity_of(obj) -> int:
    """Polygon count, falling back to vertex count. Mirrors mesh_complexity()."""
    data = getattr(obj, "data", None)
    if not data:
        return 0
    return len(getattr(data, "polygons", []) or []) or len(getattr(data, "vertices", []) or [])


def plan_high_low_pairs(items) -> PairingPlan:
    """Dry-run the high/low pairing. NO side effects, NO renaming.

    `items` is an iterable of (name, complexity) tuples. The caller is
    responsible for resolving real objects to this shape (see complexity_of).

    Algorithm mirrors infer_high_low_pairs (marmoset_baker_tools.py:309):
    sort by complexity, lower half = low, upper half = high, pair index-wise.
    Odd counts leave the last object unpaired.
    """
    items = list(items or [])

    if len(items) < 2:
        return PairingPlan(
            ok=False,
            leftovers=[name for name, _ in items],
            error_kind="not_enough_objects",
            message="Need at least 2 mesh objects to pair.",
        )

    ordered = sorted(items, key=lambda it: it[1])
    pair_count = len(ordered) // 2
    lows = ordered[:pair_count]
    # Mirror infer_high_low_pairs exactly: take the whole upper slice, re-sort,
    # then pair index-wise against lows. Extra tail items (odd count) fall out
    # as leftovers and never get paired.
    highs = sorted(ordered[pair_count:], key=lambda it: it[1])
    leftover_items = ordered[pair_count * 2:]

    pairs = []
    ambiguous = []
    for i in range(pair_count):
        low_name, low_polys = lows[i]
        high_name, high_polys = highs[i]
        # Equal polygon counts mean the algorithm cannot tell which is the high
        # and which is the low poly — the assignment is arbitrary. Flag it so the
        # agent can disambiguate (screenshot / ask the user) instead of guessing.
        is_ambiguous = low_polys == high_polys
        pairs.append({
            "low": low_name, "high": high_name,
            "low_polys": low_polys, "high_polys": high_polys,
            "ambiguous": is_ambiguous,
        })
        if is_ambiguous:
            ambiguous.append({"low": low_name, "high": high_name, "polys": low_polys})

    leftovers = [name for name, _ in leftover_items]

    if leftovers:
        return PairingPlan(
            ok=False, pairs=pairs, leftovers=leftovers, ambiguous_pairs=ambiguous,
            error_kind="unpaired_objects",
            message=f"Could not pair: {', '.join(leftovers)}",
        )

    if ambiguous:
        names = [f"{p['low']}/{p['high']}" for p in ambiguous]
        return PairingPlan(
            ok=False, pairs=pairs, leftovers=[], ambiguous_pairs=ambiguous,
            error_kind="ambiguous_pairs",
            message=("Equal polygon counts, cannot tell high from low for: "
                     + "; ".join(names)),
        )

    return PairingPlan(
        ok=True, pairs=pairs, leftovers=[], ambiguous_pairs=[],
        message=f"Planned {len(pairs)} high/low pair(s).",
    )
