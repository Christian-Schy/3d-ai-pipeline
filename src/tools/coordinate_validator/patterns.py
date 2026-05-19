"""Coordinate Validator — hole-pattern checks.

Check 10 — the pattern span (spacing × count) fits the parent dimension.
Check 12 — each individual hole in the pattern stays inside the part edge.
"""

from __future__ import annotations

import math

from .geometry import _face_half_dims
from .issue import CoordIssue


def _pattern_child_offsets(ftype: str, params: dict) -> list[tuple[float, float]]:
    """Kind-Bohrungs-Offsets pro Pattern in pattern-lokalen Koordinaten
    (zentriert auf 0,0). Liefert leere Liste bei fehlenden Params.

    - Grid: rows×cols Raster mit spacing_x/spacing_y.
    - Linear: count Bohrungen entlang `direction` ("x"/"y") mit spacing.
    - Circular: count Bohrungen auf bolt_circle_diameter/pitch_diameter,
      optional start_angle_deg.
    """
    if ftype == "hole_pattern_grid":
        try:
            rows = int(params.get("rows") or 0)
            cols = int(params.get("cols") or 0)
        except (TypeError, ValueError):
            return []
        iso = params.get("spacing")
        try:
            sx = float(params.get("spacing_x") or iso or 0)
            sy = float(params.get("spacing_y") or iso or 0)
        except (TypeError, ValueError):
            return []
        if rows <= 0 or cols <= 0:
            return []
        cx0 = (cols - 1) / 2.0
        ry0 = (rows - 1) / 2.0
        return [
            ((c - cx0) * sx, (r - ry0) * sy)
            for r in range(rows) for c in range(cols)
        ]
    if ftype == "hole_pattern_linear":
        try:
            count = int(params.get("count") or 0)
            spacing = float(params.get("spacing") or 0)
        except (TypeError, ValueError):
            return []
        direction = str(params.get("direction") or "x").lower()
        if count <= 0 or spacing <= 0:
            return []
        i0 = (count - 1) / 2.0
        if direction == "y":
            return [(0.0, (i - i0) * spacing) for i in range(count)]
        return [((i - i0) * spacing, 0.0) for i in range(count)]
    if ftype == "hole_pattern_circular":
        try:
            count = int(params.get("count") or 0)
            pitch = float(_pattern_pitch_diameter(params) or 0)
        except (TypeError, ValueError):
            return []
        try:
            start_angle = float(params.get("start_angle_deg") or 0.0)
        except (TypeError, ValueError):
            start_angle = 0.0
        if count <= 0 or pitch <= 0:
            return []
        radius = pitch / 2.0
        step = 360.0 / count
        return [
            (radius * math.cos(math.radians(start_angle + i * step)),
             radius * math.sin(math.radians(start_angle + i * step)))
            for i in range(count)
        ]
    return []


def _pattern_hole_diameter(params: dict) -> float | None:
    """Return the canonical pattern child-hole diameter.

    The pipeline schema uses `hole_diameter`; older tests/blueprints used
    `diameter`. The validator accepts both so schema-correct goldens are
    actually checked.
    """
    value = params.get("hole_diameter")
    if value is None:
        value = params.get("diameter")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pattern_pitch_diameter(params: dict) -> float | None:
    """Return the circular-pattern diameter from canonical or legacy keys."""
    value = params.get("bolt_circle_diameter")
    if value is None:
        value = params.get("pitch_diameter")
    if value is None:
        value = params.get("circle_diameter")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _check_pattern_child_bounds(
    fid: str, feat: dict,
    parent_bbox: tuple[float, float, float] | None, issues: list
) -> None:
    """Check 12: Pattern-Kind-Bohrungen gegen Bauteilrand.

    Berechnet pro Kind-Bohrung im Pattern (Grid/Linear/Kreis) die globale
    Position auf der Placement-Face und meldet WARNING wenn
    `|center| + radius` ueber die Bauteilkante hinaus geht. Pattern-
    Rotation (angle_deg fuer Grid/Linear) wird angewandt; Kreis ist
    rotations-invariant. Max 5 Einzelmeldungen pro Pattern, danach
    Aggregat-Meldung.

    Komplementaer zu Check 10 `_check_pattern_spacing` (prueft den
    Pattern-Span gegen Parent-Dim, nicht die Pattern-Position).
    """
    if parent_bbox is None:
        return
    ftype = feat.get("type", "")
    if ftype not in (
        "hole_pattern_grid", "hole_pattern_linear", "hole_pattern_circular"
    ):
        return
    placement = feat.get("placement") or {}
    if not isinstance(placement, dict):
        return
    params = feat.get("params") or {}

    diameter = _pattern_hole_diameter(params)
    if diameter is None or diameter <= 0:
        return
    radius = diameter / 2

    children = _pattern_child_offsets(ftype, params)
    if not children:
        return

    offset_x = float(placement.get("offset_x", 0.0) or 0.0)
    offset_y = float(placement.get("offset_y", 0.0) or 0.0)
    angle_deg = float(placement.get("angle_deg", 0.0) or 0.0)
    face = placement.get("face", ">Z")

    face_half_x, face_half_y = _face_half_dims(parent_bbox, face)

    # Pattern-Rotation auf Kind-Offsets anwenden (Grid/Linear; Kreis
    # ist rotations-invariant — start_angle_deg ist Pattern-intern).
    if angle_deg and ftype in ("hole_pattern_grid", "hole_pattern_linear"):
        a = math.radians(angle_deg)
        cos_a, sin_a = math.cos(a), math.sin(a)
        children = [
            (cx * cos_a - cy * sin_a, cx * sin_a + cy * cos_a)
            for (cx, cy) in children
        ]

    overhangs: list[tuple[int, float, float, float, float]] = []
    for i, (cx, cy) in enumerate(children):
        global_x = offset_x + cx
        global_y = offset_y + cy
        oh_x = (abs(global_x) + radius) - face_half_x
        oh_y = (abs(global_y) + radius) - face_half_y
        if oh_x > 0.1 or oh_y > 0.1:
            overhangs.append((i, global_x, global_y, oh_x, oh_y))

    if not overhangs:
        return

    for (i, gx, gy, oh_x, oh_y) in overhangs[:5]:
        worst_axis = "X" if oh_x >= oh_y else "Y"
        worst = max(oh_x, oh_y)
        issues.append(CoordIssue(
            severity="WARNING", feature_id=fid,
            check="pattern_child_bounds",
            message=(
                f"Pattern-Kind-Bohrung #{i} bei ({gx:.1f}, {gy:.1f}) ragt "
                f"~{worst:.2f}mm ueber {worst_axis}-Bauteilkante "
                f"(radius={radius:.1f}, face_half=({face_half_x:.1f}, "
                f"{face_half_y:.1f}))."
            ),
        ))
    if len(overhangs) > 5:
        issues.append(CoordIssue(
            severity="WARNING", feature_id=fid,
            check="pattern_child_bounds",
            message=(
                f"... und {len(overhangs) - 5} weitere Kind-Bohrungen "
                f"mit Ueberhang."
            ),
        ))


def _check_pattern_spacing(
    fid: str, params: dict, parent_bbox: tuple[float, float, float] | None,
    parent_id: str | None, issues: list
) -> None:
    """Check 10: Hole pattern grid fits within parent dimensions.

    For rArray: spacing_x * (count_x - 1) + hole_diameter must fit parent X,
    and same for Y.
    """
    if parent_bbox is None:
        return

    px, py, _ = parent_bbox
    spacing_x = params.get("spacing_x") or params.get("x_spacing")
    spacing_y = params.get("spacing_y") or params.get("y_spacing")
    count_x = params.get("cols") or params.get("count_x") or params.get("x_count")
    count_y = params.get("rows") or params.get("count_y") or params.get("y_count")
    diameter = _pattern_hole_diameter(params)

    if not all([spacing_x, count_x, diameter]):
        return

    try:
        sx, cx, d = float(spacing_x), int(count_x), float(diameter)
        pattern_x = sx * (cx - 1) + d
        if pattern_x > px + 0.1:
            issues.append(CoordIssue(
                severity="ERROR", feature_id=fid,
                check="pattern_fits_x",
                message=(
                    f"Hole pattern too wide: spacing({sx}) × ({cx}-1) + ∅{d} = "
                    f"{pattern_x:.1f}mm > parent '{parent_id}' width {px}mm"
                )
            ))
    except (TypeError, ValueError):
        pass

    if spacing_y and count_y:
        try:
            sy, cy, d = float(spacing_y), int(count_y), float(diameter)
            pattern_y = sy * (cy - 1) + d
            if pattern_y > py + 0.1:
                issues.append(CoordIssue(
                    severity="ERROR", feature_id=fid,
                    check="pattern_fits_y",
                    message=(
                        f"Hole pattern too tall: spacing({sy}) × ({cy}-1) + ∅{d} = "
                        f"{pattern_y:.1f}mm > parent '{parent_id}' height {py}mm"
                    )
                ))
        except (TypeError, ValueError):
            pass
