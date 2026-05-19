"""
src/tools/coordinate_validator/ — Regelbasierter Koordinaten- und Dimensions-Check.

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
  11. Slot-Restwandstaerke gegen Bauteilkante
  12. Pattern-Kind-Bohrungen gegen Bauteilrand

Nur für Feature-Tree-Blueprints. CSG-Trees werden übersprungen.

Package layout:
  core.py        — Public API (run_coordinate_check, format_issues_for_planner)
                   + per-feature dispatcher (_check_feature)
  issue.py       — CoordIssue record
  geometry.py    — _get_bbox, _face_half_dims
  build_order.py — Check 9 (build_order sorting + in-place fix)
  bounds.py      — Check 8 + pocket containment + Check 11 (slot clearance)
  patterns.py    — Check 10 + Check 12 (hole-pattern checks)
"""

from __future__ import annotations

import structlog

from .bounds import (
    _check_offset_bounds,
    _check_offset_inside_pocket,
    _check_slot_min_clearance,
)
from .build_order import _check_build_order_sorting
from .dimension_checks import (
    _check_bolt_circle,
    _check_depth_vs_material,
    _check_dimensions_positive,
    _check_feature_fits_parent,
    _check_wall_thickness,
)
from .geometry import _get_bbox
from .issue import CoordIssue
from .patterns import _check_pattern_child_bounds, _check_pattern_spacing

log = structlog.get_logger()


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
    """Run all per-feature checks — thin dispatcher.

    Resolves the per-feature context (parent, feature-in-feature root) once,
    then routes to the individual `_check_*` handlers with the appropriate
    ftype gating. Called inside a try/except in run_coordinate_check.
    """
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

    _check_dimensions_positive(fid, params, issues)  # Check 6

    # Skip further geometry checks if no parent (root feature)
    if parent_id is None:
        return

    parent_feat = features.get(parent_id, {})
    parent_bbox = _get_bbox(parent_feat)

    # bbox of the part to validate depth/bounds against — the root-owning
    # part for feature-in-feature children, else the immediate parent.
    if has_feature_parent and root_parent_id:
        root_feat = features.get(root_parent_id, {})
        root_bbox = _get_bbox(root_feat)
    else:
        root_feat = parent_feat
        root_bbox = parent_bbox

    # Check 1: feature smaller than parent — only for subtractive features!
    # Additive features (union/add) are allowed to be larger than their parent.
    operation = feat.get("operation", "add")
    is_subtractive = operation in ("subtract", "cut") or "hole" in ftype or ftype in (
        "pocket_rect", "pocket_round", "slot", "cutout"
    )
    if is_subtractive:
        _check_feature_fits_parent(
            fid, ftype, parent_id, parent_bbox, _get_bbox(feat), issues
        )

    # Check 2: hole depth vs parent material
    if "hole" in ftype or ftype in ("pocket_rect", "pocket_round", "slot", "cutout"):
        depth_label = root_parent_id if (has_feature_parent and root_parent_id) else parent_id
        _check_depth_vs_material(fid, params, root_bbox, depth_label, issues)

    # Check 4: bolt circle geometry
    if ftype == "hole_pattern_circular" or "circle" in ftype:
        _check_bolt_circle(fid, params, parent_bbox, issues)

    # Check 5: min wall thickness for holes
    if "hole" in ftype:
        _check_wall_thickness(fid, params, parent_bbox, parent_id, issues)

    # Check 8: offset bounds — feature center + half-size must be inside parent.
    # Feature-in-feature: offsets are in part-frame, so check against the
    # root part instead of the immediate (pocket) parent.
    if has_feature_parent and root_parent_id:
        _check_offset_bounds(fid, feat, root_feat, root_bbox, issues)
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
        _check_slot_min_clearance(fid, feat, root_bbox, issues)

    # Check 12: Pattern-Kind-Bohrungen gegen Bauteilrand. Iteriert die
    # Bohrungen im Pattern (Grid/Linear/Kreis) und meldet WARNING pro
    # ueberhaengender Bohrung. Pattern-Rotation (Grid/Linear) wird
    # angewandt; Kreis-Pattern ist rotations-invariant.
    if ftype.startswith("hole_pattern_"):
        _check_pattern_child_bounds(fid, feat, root_bbox, issues)


def format_issues_for_planner(issues: list[CoordIssue]) -> str:
    """Format coordinate issues as a text block for the Planner to fix."""
    lines = ["Coordinate-Validator found these issues (fix before continuing):"]
    for issue in issues:
        lines.append(issue.as_text())
    return "\n".join(lines)
