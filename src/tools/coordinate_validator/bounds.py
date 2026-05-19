"""Coordinate Validator — containment / clearance checks.

Check 8  — feature center + half-size stays inside the parent.
Pocket   — a feature-in-feature child stays inside its pocket footprint.
Check 11 — slot outer contour keeps a minimum rest-wall to the part edge.
"""

from __future__ import annotations

import math

from .geometry import _face_half_dims
from .issue import CoordIssue

# Mindest-Restwandstaerke (mm) zwischen Slot-Aussenkontur und Bauteilkante.
# Wird als WARNING gemeldet (nicht ERROR) — Konstrukteur kann eine knappe
# Restkante bewusst wollen (z.B. Soll-Bruch). docs/conventions/21_nut_slot_din.md.
_MIN_SLOT_REST_WALL_MM = 0.5


def _check_offset_bounds(
    fid: str, feat: dict, parent_feat: dict,
    parent_bbox: tuple[float, float, float] | None, issues: list
) -> None:
    """Check 8: Feature center + half-size must stay inside parent bounds.

    Uses placement.offset_x / offset_y and the feature's own size to verify
    the feature doesn't hang over the edge. This catches the common LLM error
    of computing offset = -X instead of -(Parent/2 - X).

    For additive features (union/add), overhang is only a WARNING — plates and
    pads commonly sit on_top with flush edges that extend beyond the parent face.
    For subtractive features (holes, pockets), overhang is an ERROR.
    """
    if parent_bbox is None:
        return

    placement = feat.get("placement", {})
    if not isinstance(placement, dict):
        return

    offset_x = placement.get("offset_x")
    offset_y = placement.get("offset_y")
    if offset_x is None and offset_y is None:
        return  # centered, no check needed

    params = feat.get("params", {}) or {}
    ftype = feat.get("type", "")
    operation = feat.get("operation", "add")
    is_subtractive = operation in ("subtract", "cut") or "hole" in ftype or ftype in (
        "pocket_rect", "pocket_round", "slot", "cutout"
    )
    # Additive features that overhang are only warnings, not errors
    severity = "ERROR" if is_subtractive else "WARNING"

    # Determine the feature's half-size in X and Y on the placement face
    face = placement.get("face", ">Z")
    parent_half_x, parent_half_y = _face_half_dims(parent_bbox, face)

    # Feature half-size: use diameter for holes, x/y for boxes
    if "hole" in ftype and params.get("diameter"):
        feat_half = float(params["diameter"]) / 2
        feat_half_x = feat_half
        feat_half_y = feat_half
    elif params.get("x") and params.get("y"):
        # Rotations-bewusste AABB fuer Tasche/Box-artige Features. Vor
        # 2026-05-18 nutzte der Check axis-aligned x/2, y/2 ohne Rotation
        # -> unterschaetzte die AABB rotierter Pockets nahe Kante (CLAUDE.md
        # "Bekannte Limitierungen"). Mit angle_deg=0 unveraendert.
        x_half = float(params["x"]) / 2
        y_half = float(params["y"]) / 2
        angle_deg = float(placement.get("angle_deg", 0.0) or 0.0)
        if angle_deg:
            a = math.radians(angle_deg)
            cos_a, sin_a = abs(math.cos(a)), abs(math.sin(a))
            feat_half_x = x_half * cos_a + y_half * sin_a
            feat_half_y = x_half * sin_a + y_half * cos_a
        else:
            feat_half_x = x_half
            feat_half_y = y_half
    elif params.get("width") and params.get("length"):
        # Slot template convention: angle=0 => length along face-X,
        # angle=90 => length along face-Y. Use the rotated AABB here so
        # generic offset bounds match the dedicated slot-restwall check.
        width_half = float(params["width"]) / 2
        length_half = float(params["length"]) / 2
        angle_deg = float(placement.get("angle_deg", 0.0) or 0.0)
        if angle_deg:
            a = math.radians(angle_deg)
            cos_a, sin_a = abs(math.cos(a)), abs(math.sin(a))
            feat_half_x = length_half * cos_a + width_half * sin_a
            feat_half_y = length_half * sin_a + width_half * cos_a
        else:
            feat_half_x = length_half
            feat_half_y = width_half
    else:
        return  # can't determine size

    def _append_bound_issue(axis: str, offset_abs: float, feat_half: float, parent_half: float) -> None:
        if is_subtractive:
            if feat_half > parent_half + 0.1 and offset_abs < 0.1:
                issues.append(CoordIssue(
                    severity="ERROR", feature_id=fid,
                    check=f"offset_bounds_{axis}",
                    message=(
                        f"Feature is larger than parent in {axis.upper()}: "
                        f"half_size={feat_half:.1f} > parent_half={parent_half:.1f}"
                    )
                ))
                return
            if offset_abs - feat_half > parent_half + 0.1:
                issues.append(CoordIssue(
                    severity="ERROR", feature_id=fid,
                    check=f"offset_bounds_{axis}",
                    message=(
                        f"Feature is fully outside parent in {axis.upper()}: "
                        f"|offset_{axis}|={offset_abs:.1f} - half_size={feat_half:.1f} "
                        f"> parent_half={parent_half:.1f}"
                    )
                ))
                return
            if offset_abs + feat_half > parent_half + 0.1:
                issues.append(CoordIssue(
                    severity="WARNING", feature_id=fid,
                    check=f"offset_overhang_{axis}",
                    message=(
                        f"Subtractive feature opens past parent edge in {axis.upper()}: "
                        f"|offset_{axis}|={offset_abs:.1f} + half_size={feat_half:.1f} = "
                        f"{offset_abs + feat_half:.1f} > parent_half={parent_half:.1f}"
                    )
                ))
            return

        if offset_abs + feat_half > parent_half + 0.1:
            issues.append(CoordIssue(
                severity=severity, feature_id=fid,
                check=f"offset_bounds_{axis}",
                message=(
                    f"Feature exceeds parent in {axis.upper()}: |offset_{axis}|={offset_abs:.1f} + "
                    f"half_size={feat_half:.1f} = {offset_abs + feat_half:.1f} > "
                    f"parent_half={parent_half:.1f}"
                )
            ))

    # Check X offset
    if offset_x is not None:
        ox = abs(float(offset_x))
        _append_bound_issue("x", ox, feat_half_x, parent_half_x)

    # Check Y offset
    if offset_y is not None:
        oy = abs(float(offset_y))
        _append_bound_issue("y", oy, feat_half_y, parent_half_y)


def _check_offset_inside_pocket(
    fid: str, feat: dict, pocket_feat: dict,
    pocket_bbox: tuple[float, float, float] | None, issues: list
) -> None:
    """Verify a feature-in-feature child stays inside its pocket footprint.

    The resolver places the child in part-frame coordinates, so we must
    inverse-transform: subtract the pocket's offset and rotate back by
    -pocket.angle_deg to recover the child's pocket-local position. Then
    compare against the pocket's footprint (params.x × params.y).
    """
    # Pocket params use {x, y, depth} — _get_bbox requires {x, y, z}, so fall
    # back to reading the footprint directly when bbox lookup failed.
    if pocket_bbox is None:
        pocket_params = pocket_feat.get("params", {}) or {}
        try:
            pocket_w = float(pocket_params.get("x"))
            pocket_h = float(pocket_params.get("y"))
            pocket_d = float(pocket_params.get("depth") or pocket_params.get("z") or 0)
        except (TypeError, ValueError):
            return
        pocket_bbox = (pocket_w, pocket_h, pocket_d)
    placement = feat.get("placement") or {}
    pocket_placement = pocket_feat.get("placement") or {}
    if not isinstance(placement, dict) or not isinstance(pocket_placement, dict):
        return
    try:
        ox = float(placement.get("offset_x") or 0)
        oy = float(placement.get("offset_y") or 0)
        pox = float(pocket_placement.get("offset_x") or 0)
        poy = float(pocket_placement.get("offset_y") or 0)
        angle = float(pocket_placement.get("angle_deg") or 0)
    except (TypeError, ValueError):
        return
    dx = ox - pox
    dy = oy - poy
    if angle:
        rad = math.radians(-angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        local_x = dx * cos_a - dy * sin_a
        local_y = dx * sin_a + dy * cos_a
    else:
        local_x, local_y = dx, dy

    pocket_w, pocket_h, _ = pocket_bbox
    params = feat.get("params", {}) or {}
    ftype = feat.get("type", "")
    if "hole" in ftype and params.get("diameter"):
        feat_half_x = float(params["diameter"]) / 2
        feat_half_y = feat_half_x
    elif params.get("x") and params.get("y"):
        feat_half_x = float(params["x"]) / 2
        feat_half_y = float(params["y"]) / 2
    else:
        return

    def _append_pocket_bound_issue(axis: str, local_abs: float, feat_half: float, pocket_half: float) -> None:
        if feat_half > pocket_half + 0.1 and local_abs < 0.1:
            issues.append(CoordIssue(
                severity="ERROR", feature_id=fid,
                check=f"inside_pocket_{axis}",
                message=(
                    f"Feature is larger than pocket in {axis.upper()}: "
                    f"half_size={feat_half:.1f} > pocket_half={pocket_half:.1f}"
                )
            ))
            return
        if local_abs - feat_half > pocket_half + 0.1:
            issues.append(CoordIssue(
                severity="ERROR", feature_id=fid,
                check=f"inside_pocket_{axis}",
                message=(
                    f"Feature is fully outside pocket in {axis.upper()}: "
                    f"pocket-local |{axis}|={local_abs:.1f} - half_size={feat_half:.1f} "
                    f"> pocket_half={pocket_half:.1f}"
                )
            ))
            return
        if local_abs + feat_half > pocket_half + 0.1:
            issues.append(CoordIssue(
                severity="WARNING", feature_id=fid,
                check=f"inside_pocket_overhang_{axis}",
                message=(
                    f"Subtractive feature opens past pocket edge in {axis.upper()}: "
                    f"pocket-local |{axis}|={local_abs:.1f} + half_size={feat_half:.1f} "
                    f"> pocket_half={pocket_half:.1f}"
                )
            ))

    _append_pocket_bound_issue("x", abs(local_x), feat_half_x, pocket_w / 2)
    _append_pocket_bound_issue("y", abs(local_y), feat_half_y, pocket_h / 2)


def _check_slot_min_clearance(
    fid: str, feat: dict,
    parent_bbox: tuple[float, float, float] | None, issues: list
) -> None:
    """Check 11: Slot-Restwandstaerke gegen Bauteilkante.

    Berechnet die AABB der Slot-Aussenkontur auf der Placement-Face
    (`length` entlang Slot-Achse, `width` quer, `angle_deg`-rotiert; die
    Endradien zaehlen nicht ueber `length`/`width` hinaus, slot2D-Konvention)
    und meldet WARNING, wenn die Restkante zur naechsten Bauteilkante
    unter `_MIN_SLOT_REST_WALL_MM` faellt. Negative Werte = Ueberhang.

    Verwendet die Mittellinien-Position aus placement.offset_x/_y (Konv.
    21, Mittellinien-Bezug). Greift nur fuer slot-Features.
    """
    if parent_bbox is None:
        return
    placement = feat.get("placement") or {}
    if not isinstance(placement, dict):
        return
    params = feat.get("params") or {}
    length = params.get("length")
    width = params.get("width")
    if not (isinstance(length, (int, float)) and isinstance(width, (int, float))):
        return
    if length <= 0 or width <= 0:
        return

    angle_deg = float(placement.get("angle_deg", 0.0) or 0.0)
    offset_x = float(placement.get("offset_x", 0.0) or 0.0)
    offset_y = float(placement.get("offset_y", 0.0) or 0.0)
    face = placement.get("face", ">Z")

    face_half_x, face_half_y = _face_half_dims(parent_bbox, face)

    a = math.radians(angle_deg)
    cos_a, sin_a = abs(math.cos(a)), abs(math.sin(a))
    aabb_half_x = (length / 2) * cos_a + (width / 2) * sin_a
    aabb_half_y = (length / 2) * sin_a + (width / 2) * cos_a

    clearances = {
        "rechter":  face_half_x - offset_x - aabb_half_x,
        "linker":   face_half_x + offset_x - aabb_half_x,
        "oberer":   face_half_y - offset_y - aabb_half_y,
        "unterer":  face_half_y + offset_y - aabb_half_y,
    }
    min_side = min(clearances, key=lambda k: clearances[k])
    min_clearance = clearances[min_side]

    if min_clearance < _MIN_SLOT_REST_WALL_MM:
        issues.append(CoordIssue(
            severity="WARNING", feature_id=fid,
            check="slot_restwandstaerke",
            message=(
                f"Slot-Restwandstaerke an {min_side} Bauteilkante: "
                f"{min_clearance:.2f}mm "
                f"(Mindest {_MIN_SLOT_REST_WALL_MM}mm). "
                f"Slot-Center=({offset_x:.1f}, {offset_y:.1f}), "
                f"angle={angle_deg:.0f}°, length={length}, width={width}."
            ),
        ))
