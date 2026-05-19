"""Blueprint Resolver — Feature Resolution.

Per-feature glue: combines Step 1 (orientation), Step 2 (face), Step 3/3b
(offsets / anchor) and Step 4 (alignment upgrade) into one resolved
feature record. Handles three input modes (full-semantic / already-
resolved fix-mode / mixed) and the feature-in-feature pathway where a
child (e.g. a hole) is placed in the local frame of its parent feature
(e.g. a pocket).

Public symbols (intra-package):
    _resolve_feature             — main entry, called per feature
    _resolve_feature_in_feature  — hole-in-pocket et al.
    _resolve_with_part_frame     — fallback when parent placement missing
    _fallback_resolve            — minimal pass-through on exception
    _is_feature_parent           — predicate: parent has its own footprint
    _FEATURE_PARENT_TYPES        — set of feature types that may host children
"""

from __future__ import annotations

import math

import structlog

from .compose import _clean_zero, _compute_offsets, _upgrade_alignment_from_notes
from .face import _resolve_face
from .orientation import _resolve_orientation

log = structlog.get_logger()


_FEATURE_PARENT_TYPES = {
    "pocket_rect", "pocket_round", "cutout", "slot", "groove",
}


def _is_feature_parent(parent_id, all_features: dict) -> bool:
    """True when parent_id points at another feature with a footprint we
    can place children inside (e.g. a pocket).

    Used by the feature-in-feature pathway: hole-in-pocket needs the
    pocket's own footprint as the placement frame, not the part-face.
    """
    if not parent_id:
        return False
    parent = all_features.get(parent_id)
    if not isinstance(parent, dict):
        return False
    if parent.get("operation", "add") != "subtract":
        return False
    return parent.get("type", "").lower() in _FEATURE_PARENT_TYPES


def _resolve_feature(
    fid: str,
    feat: dict,
    all_features: dict,
    resolved_features: dict | None = None,
) -> dict:
    """Resolve a single semantic feature → resolved feature.

    Handles three cases:
    1. Semantic format (has orientation + position) → full resolution
    2. Already-resolved format (has placement, no position) → keep placement, apply orientation only
    3. Mixed (fix-mode output) → best-effort

    resolved_features: features already resolved in this run, keyed by fid.
    Required for feature-parent placement (e.g. hole-in-pocket) so the
    parent's resolved placement can be used as the child's local frame.
    """
    if resolved_features is None:
        resolved_features = {}
    feat_type = feat.get("type", "box")
    operation = feat.get("operation", "add")
    parent_id = feat.get("parent")
    orientation = feat.get("orientation", "standard")
    position = feat.get("position", {})
    if not isinstance(position, dict):
        position = {}
    existing_placement = feat.get("placement")

    # Step 1: Resolve orientation → swap dimensions in params
    # Pass side so AxB_liegt_auf knows which dims form the contact face
    raw_params = feat.get("params", {})
    side_for_orient = position.get("side", "") if position else ""
    resolved_params, _own_swap = _resolve_orientation(
        raw_params, orientation, feat_type, side=side_for_orient)

    # Root feature: no placement needed
    if parent_id is None:
        return {
            "id": fid,
            "type": feat_type,
            "params": resolved_params,
            "parent": None,
            "placement": None,
            "operation": operation,
            "notes": feat.get("notes", ""),
        }

    # If feature already has placement and NO semantic position → keep existing placement.
    # This handles fix-mode where the AI returned resolved format.
    # We still apply orientation resolution to params (step 1 above).
    has_semantic_position = "side" in position
    if existing_placement and not has_semantic_position:
        # Preserve existing placement, but ensure angle_deg + pre_rotation exist
        if isinstance(existing_placement, dict):
            existing_placement.setdefault("angle_deg", 0.0)
            existing_placement.setdefault("pre_rotation", None)
        return {
            "id": fid,
            "type": feat_type,
            "params": resolved_params,
            "parent": parent_id,
            "placement": existing_placement,
            "operation": operation,
            "notes": feat.get("notes", ""),
        }

    # Feature-in-feature pathway (e.g. hole inside a pocket).
    # Parent is a subtractive feature with its own footprint; the child's
    # offsets are computed in the parent's LOCAL frame and then transformed
    # back into the part-face frame via the parent's placement (rotation +
    # translation). The depth is also adjusted so a hole said to be 5mm deep
    # "in the pocket floor" actually drills 5mm BELOW the pocket floor
    # (= pocket.depth + child.depth from the part-top face).
    if _is_feature_parent(parent_id, all_features):
        return _resolve_feature_in_feature(
            fid, feat, feat_type, operation, parent_id,
            resolved_params, position, all_features, resolved_features,
        )

    # Child feature: compute placement from semantic position
    parent_feat = all_features.get(parent_id, {})
    parent_params = parent_feat.get("params", {})
    # If parent was also reoriented, we need its resolved params AND swap type
    parent_orientation = parent_feat.get("orientation", "standard")
    resolved_parent_params, parent_swap = _resolve_orientation(
        parent_params, parent_orientation, parent_feat.get("type", "box")
    )

    # Step 2: Face from side keyword
    # Convention: "oben" = the original X×Y face of the parent.
    # After parent reorientation, that face may have moved — remap accordingly.
    side = position.get("side", "oben")
    face = _resolve_face(side, parent_swap=parent_swap)

    # Step 3: Offsets from alignment + edge_distances
    # Upgrade alignment from notes if the AI put flush hints in notes instead
    alignment = position.get("alignment", "centered")
    notes_text = position.get("notes", "") or feat.get("notes", "") or ""
    edge_distances = position.get("edge_distances")
    pocket_edge_distances = position.get("pocket_edge_distances")
    alignment = _upgrade_alignment_from_notes(
        alignment, notes_text,
        has_edge_distances=bool(edge_distances) or bool(pocket_edge_distances),
    )
    # Legacy-Grid (count + inset) ist inhaerent zentriert — inset deckt den
    # Kantenabstand, edge_distances wuerden das Raster verschieben. Beim
    # expliziten Grid (rows/cols/spacing) gilt dagegen DIN-Konvention 24
    # A1: edge_distances platzieren die outermost-Hole — sie bleiben.
    # center_offset und anchor wirken in beiden Faellen.
    if feat.get("type") in ("hole_pattern_grid",):
        _grid_params = feat.get("params", {}) or {}
        _is_explicit_grid = bool(
            _grid_params.get("rows") and _grid_params.get("cols")
        )
        if not _is_explicit_grid:
            if edge_distances:
                edge_distances = None
            if pocket_edge_distances:
                pocket_edge_distances = None
    center_offset = position.get("center_offset")
    anchor = position.get("anchor")
    if anchor is not None and not isinstance(anchor, dict):
        anchor = None  # malformed input — ignore gracefully
    # Step 4: Angle (needed before offset so anchor can compensate for rotation)
    angle_deg = float(position.get("angle_deg", 0.0))

    offset_x, offset_y = _compute_offsets(
        alignment, edge_distances,
        resolved_parent_params, resolved_params, face,
        center_offset=center_offset,
        anchor=anchor,
        angle_deg=angle_deg,
        feat_type=feat_type,
        pocket_edge_distances=pocket_edge_distances,
    )
    pre_rotation = anchor.get("pre_rotation") if isinstance(anchor, dict) else None
    # Tolerate malformed pre_rotation (must be a dict with numeric x/y/z)
    if pre_rotation is not None and not isinstance(pre_rotation, dict):
        pre_rotation = None

    placement = {
        "face": face,
        "alignment": alignment,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "angle_deg": angle_deg,
        "pre_rotation": pre_rotation,
        "notes": position.get("notes", ""),
    }

    return {
        "id": fid,
        "type": feat_type,
        "params": resolved_params,
        "parent": parent_id,
        "placement": placement,
        "operation": operation,
        "notes": feat.get("notes", ""),
    }


def _resolve_feature_in_feature(
    fid: str,
    feat: dict,
    feat_type: str,
    operation: str,
    parent_id: str,
    resolved_params: dict,
    position: dict,
    all_features: dict,
    resolved_features: dict,
) -> dict:
    """Place a feature inside another feature (e.g. hole inside pocket).

    The pocket's footprint defines a local 2D frame on the placement face:
      - origin = pocket center on that face
      - axes   = pocket-local X/Y (rotated by pocket.placement.angle_deg)
      - extent = pocket.params.x × pocket.params.y

    All position fields (alignment, edge_distances, center_offset, anchor)
    are evaluated in this local frame via the same _compute_offsets logic
    used for part-on-part placement. The result is then rotated by
    pocket.angle_deg and translated by pocket.offset_x/_y so it lands in
    part-face coordinates.

    Depth is adjusted via depth_reference: when 'pocket_floor' (or 'auto'
    with a pocket parent), child.depth is added to pocket.depth so the
    drill cuts from the part top through the pocket and the requested
    extra depth into the floor.
    """
    parent_resolved = resolved_features.get(parent_id)
    parent_feat = all_features.get(parent_id, {})
    if not isinstance(parent_resolved, dict) or parent_resolved.get("placement") is None:
        # Parent must be resolved first — topo-sort should have ensured this.
        # If it didn't (cycle, malformed input), fall back to part-frame.
        log.warning(
            "feature_parent_unresolved",
            feature=fid, parent=parent_id,
        )
        # Bail out to standard part-parent path by simulating part_params.
        return _resolve_with_part_frame(
            fid, feat, feat_type, operation, parent_id,
            resolved_params, position, parent_feat,
        )

    parent_placement = parent_resolved["placement"]
    face = parent_placement.get("face", ">Z")
    parent_pocket_params = parent_resolved.get("params") or parent_feat.get("params", {})
    pocket_w = float(parent_pocket_params.get("x") or 0)
    pocket_h = float(parent_pocket_params.get("y") or 0)
    pocket_depth = float(parent_pocket_params.get("depth") or 0)
    pocket_angle = float(parent_placement.get("angle_deg") or 0.0)

    # Build a synthetic "parent params" dict that _compute_offsets can read.
    # On the placement face the pocket's footprint is x×y, so we feed those
    # as parent dims regardless of which face it sits on.
    fake_parent_params = {"x": pocket_w, "y": pocket_h, "z": pocket_depth}

    alignment = position.get("alignment", "centered")
    notes_text = position.get("notes", "") or feat.get("notes", "") or ""
    edge_distances = position.get("edge_distances")
    pocket_edge_distances = position.get("pocket_edge_distances")
    alignment = _upgrade_alignment_from_notes(
        alignment, notes_text,
        has_edge_distances=bool(edge_distances) or bool(pocket_edge_distances),
    )
    if feat.get("type") in ("hole_pattern_grid",):
        _grid_params = feat.get("params", {}) or {}
        _is_explicit_grid = bool(
            _grid_params.get("rows") and _grid_params.get("cols")
        )
        if not _is_explicit_grid:
            if edge_distances:
                edge_distances = None
            if pocket_edge_distances:
                pocket_edge_distances = None
    center_offset = position.get("center_offset")
    anchor = position.get("anchor")
    if anchor is not None and not isinstance(anchor, dict):
        anchor = None
    child_angle = float(position.get("angle_deg", 0.0))

    # 1) Resolve in pocket-local frame (parent dims = pocket footprint).
    # Trick: feed face=">Z" so _get_face_dimensions reads x,y from
    # fake_parent_params consistently, regardless of the pocket's real face.
    # The rotation back to the real face happens via the assembler.
    local_ox, local_oy = _compute_offsets(
        alignment, edge_distances,
        fake_parent_params, resolved_params, ">Z",
        center_offset=center_offset,
        anchor=anchor,
        angle_deg=child_angle,
        feat_type=feat_type,
        pocket_edge_distances=pocket_edge_distances,
    )

    # 2) Rotate the local offset by the pocket's own angle so children
    # follow when the pocket itself is rotated on its face.
    if pocket_angle:
        rad = math.radians(pocket_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        rot_ox = local_ox * cos_a - local_oy * sin_a
        rot_oy = local_ox * sin_a + local_oy * cos_a
    else:
        rot_ox, rot_oy = local_ox, local_oy

    # 3) Translate into the parent face's frame.
    final_ox = float(parent_placement.get("offset_x") or 0) + rot_ox
    final_oy = float(parent_placement.get("offset_y") or 0) + rot_oy

    # 4) Depth-reference handling. Default 'auto' = pocket_floor when parent
    # is a pocket. Adds pocket_depth to child.depth so the cut starts at
    # the part-top face and reaches pocket_floor + child.depth.
    depth_ref = position.get("depth_reference", "auto")
    final_params = dict(resolved_params)
    if depth_ref in ("auto", "pocket_floor"):
        child_depth = final_params.get("depth")
        if child_depth is not None:
            try:
                child_depth_f = float(child_depth)
            except (TypeError, ValueError):
                child_depth_f = None
            if child_depth_f is not None and child_depth_f > 0:
                # Stash original for debugging / round-trip.
                final_params["depth_local"] = child_depth_f
                final_params["depth"] = round(child_depth_f + pocket_depth, 6)
                final_params["depth_reference_applied"] = "pocket_floor"

    # 5) Compose final angle: child face-angle plus pocket face-angle so
    # the child's local axes follow the pocket on the same face.
    final_angle = (child_angle + pocket_angle) % 360.0
    if final_angle == 0.0:
        final_angle = 0.0

    pre_rotation = anchor.get("pre_rotation") if isinstance(anchor, dict) else None
    if pre_rotation is not None and not isinstance(pre_rotation, dict):
        pre_rotation = None

    placement = {
        "face": face,
        "alignment": alignment,
        "offset_x": _clean_zero(round(final_ox, 4)),
        "offset_y": _clean_zero(round(final_oy, 4)),
        "angle_deg": final_angle,
        "pre_rotation": pre_rotation,
        "notes": position.get("notes", ""),
        "feature_parent": parent_id,
    }

    return {
        "id": fid,
        "type": feat_type,
        "params": final_params,
        "parent": parent_id,
        "placement": placement,
        "operation": operation,
        "notes": feat.get("notes", ""),
    }


def _resolve_with_part_frame(
    fid, feat, feat_type, operation, parent_id,
    resolved_params, position, parent_feat,
):
    """Fallback: resolve a feature-in-feature as if its parent were the
    part-root — used when the parent's placement is missing/unresolvable.
    """
    parent_params = parent_feat.get("params", {})
    parent_orientation = parent_feat.get("orientation", "standard")
    resolved_parent_params, parent_swap = _resolve_orientation(
        parent_params, parent_orientation, parent_feat.get("type", "box")
    )
    side = position.get("side", "oben")
    face = _resolve_face(side, parent_swap=parent_swap)
    alignment = position.get("alignment", "centered")
    edge_distances = position.get("edge_distances")
    center_offset = position.get("center_offset")
    anchor = position.get("anchor")
    if anchor is not None and not isinstance(anchor, dict):
        anchor = None
    angle_deg = float(position.get("angle_deg", 0.0))
    offset_x, offset_y = _compute_offsets(
        alignment, edge_distances,
        resolved_parent_params, resolved_params, face,
        center_offset=center_offset,
        anchor=anchor,
        angle_deg=angle_deg,
        feat_type=feat_type,
    )
    placement = {
        "face": face,
        "alignment": alignment,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "angle_deg": angle_deg,
        "pre_rotation": None,
        "notes": position.get("notes", ""),
    }
    return {
        "id": fid,
        "type": feat_type,
        "params": resolved_params,
        "parent": parent_id,
        "placement": placement,
        "operation": operation,
        "notes": feat.get("notes", ""),
    }


def _fallback_resolve(fid: str, feat: dict) -> dict:
    """Minimal fallback: preserve what we can, add defaults."""
    return {
        "id": fid,
        "type": feat.get("type", "box"),
        "params": feat.get("params", {}),
        "parent": feat.get("parent"),
        "placement": feat.get("placement", {
            "face": ">Z",
            "alignment": "centered",
            "offset_x": 0.0,
            "offset_y": 0.0,
            "angle_deg": 0.0,
            "pre_rotation": None,
            "notes": "",
        }),
        "operation": feat.get("operation", "add"),
        "notes": feat.get("notes", ""),
    }
