"""
src/tools/coordinate_validator.py — Regelbasierter Koordinaten- und Dimensions-Check.

Läuft NACH dem Planner, VOR dem Plan Validator.
Prüft rein mathematisch ob die Feature-Tree-Geometrie physikalisch Sinn ergibt.
Kein LLM — deterministisch, schnell, kostenlos.

Prüfungen:
  1. Feature kleiner als sein Parent (Bounding Box)
  2. Bohrung nicht tiefer als verfügbares Material
  3. Feature ragt nicht vollständig aus Parent-BBox heraus
  4. Lochkreis: circle_d/2 + hole_d/2 < Parent-Hälfte
  5. Wandstärke bei Bohrungen ≥ 2mm
  6. Alle Dimensionen > 0
  7. build_order: Parent vor Child
  8. Offset-Bounds: Feature-Zentrum + Radius innerhalb Parent
  9. Build-Order-Sortierung: Additive Features vor subtraktiven
  10. Hole-Pattern-Spacing: Passt das Raster in den Parent?

Nur für Feature-Tree-Blueprints. CSG-Trees werden übersprungen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass
class CoordIssue:
    severity: str          # "ERROR" or "WARNING"
    feature_id: str
    check: str
    message: str

    def as_text(self) -> str:
        return f"  [{self.severity}] {self.feature_id} — {self.check}: {self.message}"


# Mindest-Restwandstaerke (mm) zwischen Slot-Aussenkontur und Bauteilkante.
# Wird als WARNING gemeldet (nicht ERROR) — Konstrukteur kann eine knappe
# Restkante bewusst wollen (z.B. Soll-Bruch). docs/conventions/21_nut_slot_din.md.
_MIN_SLOT_REST_WALL_MM = 0.5


def _get_bbox(feature: dict) -> tuple[float, float, float] | None:
    """Returns (x, y, z) dimensions of a feature, or None if not determinable."""
    params = feature.get("params", {})
    ftype = feature.get("type", "")

    # Explicit box dimensions (all three must be non-None numbers)
    if all(params.get(k) is not None for k in ("x", "y", "z")):
        try:
            return (float(params["x"]), float(params["y"]), float(params["z"]))
        except (TypeError, ValueError):
            pass

    # Cylinder / hole → approximate as bounding box
    if params.get("diameter") is not None and "depth" in params:
        try:
            d = float(params["diameter"])
            depth = params.get("depth")
            z = float(depth) if depth is not None else None
            if d > 0 and z:
                return (d, d, z)
        except (TypeError, ValueError):
            pass

    # hole_pattern_circular → use circle_diameter as bounding
    if params.get("circle_diameter") is not None and params.get("diameter") is not None:
        try:
            cd = float(params["circle_diameter"])
            depth_val = params.get("depth", 1) or 1
            return (cd * 2, cd * 2, float(depth_val))
        except (TypeError, ValueError):
            pass

    return None


def run_coordinate_check(blueprint: dict) -> list[CoordIssue]:
    """Run all coordinate/dimension checks on a Feature Tree blueprint.

    Returns a list of CoordIssue objects. Empty list = all checks passed.
    Only runs on Feature Tree blueprints (has build_order + features dict).
    """
    from src.graph.feature_tree import FeatureTree

    if not FeatureTree.is_feature_tree(blueprint):
        return []  # CSG-Tree: skip, handled by old quick_check

    features: dict = blueprint.get("features", {})
    build_order: list = blueprint.get("build_order", [])
    issues: list[CoordIssue] = []

    # ─── Check 7: build_order integrity (parent before child) ───
    seen_ids: set[str] = set()
    for fid in build_order:
        feat = features.get(fid, {})
        parent = feat.get("parent")
        if parent and parent not in seen_ids:
            issues.append(CoordIssue(
                severity="ERROR", feature_id=fid,
                check="build_order",
                message=f"Parent '{parent}' not in build_order before '{fid}'"
            ))
        seen_ids.add(fid)

    # ─── Check 9: build_order sorting — adds before subtracts per parent ───
    _check_build_order_sorting(build_order, features, issues)

    # ─── Per-feature checks ───
    for fid in build_order:
        try:
            _check_feature(fid, features, issues)
        except Exception as _e:
            log.warning("coordinate_check_feature_error", feature=fid, error=str(_e))

    log.info("coordinate_check_done",
             features=len(build_order),
             issues=len(issues),
             errors=sum(1 for i in issues if i.severity == "ERROR"))
    return issues


def _resolve_root_parent_id(fid: str, features: dict) -> str | None:
    """Walk the parent chain upward, skipping subtractive ancestors.

    Mirrors src.codegen.assembler.assembly._resolve_part_root. Returns the ID of
    the body-owning ancestor (root part or add-feature) or None.
    Used so feature-in-feature children (hole-in-pocket) are validated
    against the actual containing part, not their pocket parent — depth
    and offset bounds need the part dimensions to make sense.
    """
    visited: set[str] = set()
    feat = features.get(fid)
    current = feat.get("parent") if isinstance(feat, dict) else None
    while current is not None:
        if current in visited:
            return None
        visited.add(current)
        parent_feat = features.get(current)
        if not isinstance(parent_feat, dict):
            return None
        op = parent_feat.get("operation", "add").lower()
        if parent_feat.get("parent") is None or op in ("add", "union"):
            return current
        current = parent_feat.get("parent")
    return None


def _check_feature(fid: str, features: dict, issues: list) -> None:
    """Run all per-feature checks. Called inside a try/except in run_coordinate_check."""
    feat = features.get(fid)
    if not isinstance(feat, dict):
        return

    params = feat.get("params") or {}
    ftype = feat.get("type", "unknown")
    parent_id = feat.get("parent")
    placement = feat.get("placement") or {}
    # Feature-in-feature: when the resolver placed this feature inside
    # another feature (e.g. hole-in-pocket), depth/offset checks need
    # the root-owning part as reference, not the immediate pocket parent.
    has_feature_parent = (
        isinstance(placement, dict)
        and placement.get("feature_parent") is not None
    )
    root_parent_id = _resolve_root_parent_id(fid, features) if has_feature_parent else None

    # Check 6: all dimensions > 0
    for key, val in params.items():
        if val is None:
            continue  # null depth = through-hole, valid
        try:
            f = float(val)
            if f < 0:
                issues.append(CoordIssue(
                    severity="ERROR", feature_id=fid,
                    check="dimensions_positive",
                    message=f"Parameter '{key}' is negative: {val}"
                ))
        except (TypeError, ValueError):
            pass

    # Skip further geometry checks if no parent (root feature)
    if parent_id is None:
        return

    parent_feat = features.get(parent_id, {})
    parent_bbox = _get_bbox(parent_feat)
    my_bbox = _get_bbox(feat)

    # Check 1: feature smaller than parent — only for subtractive features!
    # Additive features (union/add) are allowed to be larger than their parent.
    operation = feat.get("operation", "add")
    is_subtractive = operation in ("subtract", "cut") or "hole" in ftype or ftype in (
        "pocket_rect", "pocket_round", "slot", "cutout"
    )
    if parent_bbox and my_bbox and is_subtractive:
        px, py, pz = parent_bbox
        fx, fy, fz = my_bbox
        if fx > px * 1.05 and fy > py * 1.05:
            issues.append(CoordIssue(
                severity="WARNING", feature_id=fid,
                check="feature_fits_parent",
                message=(
                    f"{ftype} ({fx}×{fy}) is larger than parent '{parent_id}' "
                    f"({px}×{py}) in both X and Y"
                )
            ))

    # Check 2: hole depth vs parent material
    if "hole" in ftype or ftype in ("pocket_rect", "pocket_round", "slot", "cutout"):
        depth = params.get("depth")
        # For feature-in-feature children, the depth was already adjusted by
        # the resolver to span pocket+hole; check against the root-owning
        # part's height, not the pocket's own depth.
        if has_feature_parent and root_parent_id:
            depth_parent_feat = features.get(root_parent_id, {})
            depth_parent_bbox = _get_bbox(depth_parent_feat)
            depth_parent_label = root_parent_id
        else:
            depth_parent_bbox = parent_bbox
            depth_parent_label = parent_id
        if depth is not None and depth_parent_bbox:
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

    # Check 4: bolt circle geometry
    if ftype in ("hole_pattern_circular",) or "circle" in ftype:
        cd = params.get("circle_diameter")
        hd = params.get("diameter")
        if cd and hd and parent_bbox:
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

    # Check 5: min wall thickness for holes
    if "hole" in ftype:
        hd = params.get("diameter")
        if hd and parent_bbox:
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

    # Check 8: offset bounds — feature center + half-size must be inside parent.
    # Feature-in-feature: offsets are in part-frame, so check against the
    # root part instead of the immediate (pocket) parent.
    if has_feature_parent and root_parent_id:
        bounds_parent_feat = features.get(root_parent_id, {})
        bounds_parent_bbox = _get_bbox(bounds_parent_feat)
        _check_offset_bounds(fid, feat, bounds_parent_feat, bounds_parent_bbox, issues)
        # Plus: feature must stay inside its IMMEDIATE pocket parent's footprint.
        _check_offset_inside_pocket(fid, feat, parent_feat, parent_bbox, issues)
    else:
        _check_offset_bounds(fid, feat, parent_feat, parent_bbox, issues)

    # Check 10: hole pattern spacing fits parent
    if ftype == "hole_pattern_grid":
        _check_pattern_spacing(fid, params, parent_bbox, parent_id, issues)

    # Check 11: Slot-Restwandstaerke (Mittellinien-Konvention,
    # docs/conventions/21_nut_slot_din.md). Warnt wenn die Slot-Aussen-
    # kontur (length×width-AABB, angle-rotiert) naeher als
    # _MIN_SLOT_REST_WALL_MM an einer Bauteilkante liegt. Negative Werte
    # = Ueberhang.
    if ftype == "slot":
        if has_feature_parent and root_parent_id:
            slot_parent_bbox = _get_bbox(features.get(root_parent_id, {}))
        else:
            slot_parent_bbox = parent_bbox
        _check_slot_min_clearance(fid, feat, slot_parent_bbox, issues)

    # Check 12: Pattern-Kind-Bohrungen gegen Bauteilrand. Iteriert die
    # Bohrungen im Pattern (Grid/Linear/Kreis) und meldet WARNING pro
    # ueberhaengender Bohrung. Pattern-Rotation (Grid/Linear) wird
    # angewandt; Kreis-Pattern ist rotations-invariant.
    if ftype.startswith("hole_pattern_"):
        if has_feature_parent and root_parent_id:
            pat_parent_bbox = _get_bbox(features.get(root_parent_id, {}))
        else:
            pat_parent_bbox = parent_bbox
        _check_pattern_child_bounds(fid, feat, pat_parent_bbox, issues)


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

    px, py, pz = parent_bbox

    # Determine the feature's half-size in X and Y on the placement face
    face = placement.get("face", ">Z")
    if face in (">Z", "<Z"):
        parent_half_x, parent_half_y = px / 2, py / 2
    elif face in (">X", "<X"):
        parent_half_x, parent_half_y = py / 2, pz / 2
    elif face in (">Y", "<Y"):
        parent_half_x, parent_half_y = px / 2, pz / 2
    else:
        parent_half_x, parent_half_y = px / 2, py / 2

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
        feat_half_x = float(params["width"]) / 2
        feat_half_y = float(params["length"]) / 2
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


def _check_build_order_sorting(
    build_order: list, features: dict, issues: list
) -> None:
    """Check 9: All additive features should come before subtractive ones per parent.

    If a hole is built before an add (pad/extrusion), the hole won't go through
    the added material. This is a common Planner error.

    Rather than just warning, this FIXES the build_order in-place by sorting:
    additive operations first, then subtractive.
    """
    _SUBTRACTIVE_TYPES = {
        "hole", "hole_pattern_grid", "hole_pattern_circular",
        "pocket_rect", "pocket_round", "slot", "cutout",
        "chamfer", "fillet",
    }

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

    px, py, pz = parent_bbox
    if face in (">Z", "<Z"):
        face_half_x, face_half_y = px / 2, py / 2
    elif face in (">X", "<X"):
        face_half_x, face_half_y = py / 2, pz / 2
    elif face in (">Y", "<Y"):
        face_half_x, face_half_y = px / 2, pz / 2
    else:
        face_half_x, face_half_y = px / 2, py / 2

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


def _pattern_child_offsets(ftype: str, params: dict) -> list[tuple[float, float]]:
    """Kind-Bohrungs-Offsets pro Pattern in pattern-lokalen Koordinaten
    (zentriert auf 0,0). Liefert leere Liste bei fehlenden Params.

    - Grid: rows×cols Raster mit spacing_x/spacing_y.
    - Linear: count Bohrungen entlang `direction` ("x"/"y") mit spacing.
    - Circular: count Bohrungen auf pitch_diameter, optional start_angle_deg.
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
            pitch = float(params.get("pitch_diameter") or 0)
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

    diameter = params.get("diameter")
    if not isinstance(diameter, (int, float)) or diameter <= 0:
        return
    radius = float(diameter) / 2

    children = _pattern_child_offsets(ftype, params)
    if not children:
        return

    offset_x = float(placement.get("offset_x", 0.0) or 0.0)
    offset_y = float(placement.get("offset_y", 0.0) or 0.0)
    angle_deg = float(placement.get("angle_deg", 0.0) or 0.0)
    face = placement.get("face", ">Z")

    px, py, pz = parent_bbox
    if face in (">Z", "<Z"):
        face_half_x, face_half_y = px / 2, py / 2
    elif face in (">X", "<X"):
        face_half_x, face_half_y = py / 2, pz / 2
    elif face in (">Y", "<Y"):
        face_half_x, face_half_y = px / 2, pz / 2
    else:
        face_half_x, face_half_y = px / 2, py / 2

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
    count_x = params.get("count_x") or params.get("x_count")
    count_y = params.get("count_y") or params.get("y_count")
    diameter = params.get("diameter")

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


def format_issues_for_planner(issues: list[CoordIssue]) -> str:
    """Format coordinate issues as a text block for the Planner to fix."""
    lines = ["Coordinate-Validator found these issues (fix before continuing):"]
    for issue in issues:
        lines.append(issue.as_text())
    return "\n".join(lines)
