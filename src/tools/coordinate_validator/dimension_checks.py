"""Coordinate Validator — bounding-box / dimension checks.

The small per-feature checks that compare a feature's own dimensions
against its parent's bounding box:

    Check 1 — feature not larger than parent (subtractive only)
    Check 2 — hole/pocket depth not exceeding parent material
    Check 4 — bolt-circle radius + hole radius fit the parent radius
    Check 5 — residual wall after a hole >= 2mm
    Check 6 — all numeric parameters non-negative

Each appends to the shared `issues` list; the calling dispatcher
(core._check_feature) owns the ftype gating.
"""

from __future__ import annotations

from .issue import CoordIssue


def _check_dimensions_positive(fid: str, params: dict, issues: list) -> None:
    """Check 6: every numeric parameter must be >= 0 (None depth = through-hole)."""
    for key, val in params.items():
        if val is None:
            continue  # null depth = through-hole, valid
        try:
            if float(val) < 0:
                issues.append(CoordIssue(
                    severity="ERROR", feature_id=fid,
                    check="dimensions_positive",
                    message=f"Parameter '{key}' is negative: {val}"
                ))
        except (TypeError, ValueError):
            pass


def _check_feature_fits_parent(
    fid: str, ftype: str, parent_id: str,
    parent_bbox: tuple[float, float, float] | None,
    my_bbox: tuple[float, float, float] | None, issues: list
) -> None:
    """Check 1: a subtractive feature larger than its parent in both X and Y.

    Additive features may legitimately exceed the parent — the caller only
    invokes this for subtractive features.
    """
    if not (parent_bbox and my_bbox):
        return
    px, py, _ = parent_bbox
    fx, fy, _ = my_bbox
    if fx > px * 1.05 and fy > py * 1.05:
        issues.append(CoordIssue(
            severity="WARNING", feature_id=fid,
            check="feature_fits_parent",
            message=(
                f"{ftype} ({fx}×{fy}) is larger than parent '{parent_id}' "
                f"({px}×{py}) in both X and Y"
            )
        ))


def _check_depth_vs_material(
    fid: str, params: dict,
    depth_parent_bbox: tuple[float, float, float] | None,
    depth_parent_label: str | None, issues: list
) -> None:
    """Check 2: a hole/pocket depth must not exceed the parent material height.

    `depth_parent_bbox` is resolved by the caller — for feature-in-feature
    children the resolver already spans pocket+hole, so the reference is
    the root-owning part, not the immediate pocket parent.
    """
    depth = params.get("depth")
    if depth is None or not depth_parent_bbox:
        return
    pz = depth_parent_bbox[2]
    if float(depth) > pz:
        issues.append(CoordIssue(
            severity="ERROR", feature_id=fid,
            check="depth_vs_material",
            message=(
                f"Depth {depth}mm exceeds parent '{depth_parent_label}' "
                f"height {pz}mm"
            )
        ))


def _check_bolt_circle(
    fid: str, params: dict,
    parent_bbox: tuple[float, float, float] | None, issues: list
) -> None:
    """Check 4: bolt-circle radius + hole radius must fit the parent radius."""
    cd = (
        params.get("bolt_circle_diameter")
        or params.get("pitch_diameter")
        or params.get("circle_diameter")
    )
    hd = params.get("hole_diameter") or params.get("diameter")
    if not (cd and hd and parent_bbox):
        return
    circle_r = float(cd) / 2
    hole_r = float(hd) / 2
    px, py, _ = parent_bbox
    parent_r = min(px, py) / 2
    if circle_r + hole_r > parent_r:
        issues.append(CoordIssue(
            severity="ERROR", feature_id=fid,
            check="bolt_circle_fits",
            message=(
                f"Bolt circle: circle_r({circle_r}) + hole_r({hole_r}) = "
                f"{circle_r + hole_r:.1f} > parent_r({parent_r:.1f})"
            )
        ))


def _check_wall_thickness(
    fid: str, params: dict,
    parent_bbox: tuple[float, float, float] | None,
    parent_id: str | None, issues: list
) -> None:
    """Check 5: residual wall after a hole should be >= 2mm (WARNING below)."""
    hd = params.get("diameter") or params.get("hole_diameter")
    if not (hd and parent_bbox):
        return
    px, py, _ = parent_bbox
    min_wall = min(px, py) / 2 - float(hd) / 2
    if 0 < min_wall < 2.0:
        issues.append(CoordIssue(
            severity="WARNING", feature_id=fid,
            check="wall_thickness",
            message=(
                f"Wall thickness ~{min_wall:.1f}mm after hole ∅{hd}mm "
                f"in '{parent_id}' ({px}×{py}) — minimum recommended 2mm"
            )
        ))
