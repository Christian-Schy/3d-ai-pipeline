"""Coordinate Validator — Check 9: build_order sorting.

Ensures additive features are built before subtractive ones per parent,
and fixes the order in-place when they are not (a hole built before its
pad would not cut through the added material).
"""

from __future__ import annotations

import structlog

from .issue import CoordIssue

log = structlog.get_logger()

_SUBTRACTIVE_TYPES = {
    "hole", "hole_pattern_grid", "hole_pattern_circular",
    "pocket_rect", "pocket_round", "slot", "cutout",
    "chamfer", "fillet",
}


def _check_build_order_sorting(
    build_order: list, features: dict, issues: list
) -> None:
    """Check 9: All additive features should come before subtractive ones per parent.

    If a hole is built before an add (pad/extrusion), the hole won't go through
    the added material. This is a common Planner error.

    Rather than just warning, this FIXES the build_order in-place by sorting:
    additive operations first, then subtractive.
    """
    # Group features by parent
    by_parent: dict[str | None, list[str]] = {}
    for fid in build_order:
        feat = features.get(fid, {})
        parent = feat.get("parent")
        by_parent.setdefault(parent, []).append(fid)

    reordered = False
    for parent, children in by_parent.items():
        if len(children) < 2:
            continue

        adds = []
        subs = []
        for fid in children:
            feat = features.get(fid, {})
            ftype = feat.get("type", "")
            operation = feat.get("operation", "add")
            if ftype in _SUBTRACTIVE_TYPES or operation in ("subtract", "cut"):
                subs.append(fid)
            else:
                adds.append(fid)

        # Check: any subtract appears before an add?
        if subs and adds:
            first_sub_idx = None
            last_add_idx = None
            for i, fid in enumerate(children):
                if fid in subs and first_sub_idx is None:
                    first_sub_idx = i
                if fid in adds:
                    last_add_idx = i

            if first_sub_idx is not None and last_add_idx is not None and first_sub_idx < last_add_idx:
                reordered = True
                # Fix: reorder children so adds come first
                correct_order = adds + subs
                issues.append(CoordIssue(
                    severity="WARNING", feature_id=subs[0],
                    check="build_order_sorting",
                    message=(
                        f"Subtractive feature before additive on parent '{parent}' — "
                        f"reordered: adds {adds} before subtracts {subs}"
                    )
                ))

                # Apply fix in-place on build_order
                # Replace the children segment with correct order
                for old_fid in children:
                    build_order.remove(old_fid)
                # Find insertion point (after parent in build_order, or at the end)
                if parent and parent in build_order:
                    insert_at = build_order.index(parent) + 1
                else:
                    insert_at = len(build_order)
                for i, fid in enumerate(correct_order):
                    build_order.insert(insert_at + i, fid)

    if reordered:
        log.info("build_order_reordered", new_order=build_order)
