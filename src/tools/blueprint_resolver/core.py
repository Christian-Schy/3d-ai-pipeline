"""
src/tools/blueprint_resolver.py — Converts Semantic Blueprint → Resolved Blueprint.

100% deterministic, no LLM. Handles:
  1. Orientation resolution: "hochkant" → dimension swap in params
  2. Face calculation: "rechts" → ">X" face selector
  3. Offset calculation: anchor / edge_distances / center_offset / alignment
     → numeric offset_x / offset_y (face-aware)
  4. Angle preservation: angle_deg passed through to resolved placement
  5. Anchor resolution: child-point-on-parent-point placement (corners, edges,
     centers) with optional pre_rotation (3D) passed through to the assembler

This is the ONLY place where dimension swaps and offset math happen.
The AI never computes these values.

═══════════════════════════════════════════════════════════════════
STRUKTUR (bei Aenderungen pflegen! Siehe CLAUDE.md)
═══════════════════════════════════════════════════════════════════
Public API:
  resolve_blueprint(semantic)      — semantic dict → resolved dict
                                     idempotent; pass-through fuer legacy
                                     blueprints ohne semantic-Felder
                                     ruft _topo_sort_features fuer parent-
                                     before-child Reihenfolge auf

Topo-Sort:
  _topo_sort_features              — Kahn's Algo auf parent-Kanten,
                                     Original-Order als Tiebreaker,
                                     Cycle-Detection → BlueprintResolverError
  BlueprintResolverError           — Cycle/Validation-Fehler im Resolver

Feature-in-Feature (Bohrung in Tasche):
  _FEATURE_PARENT_TYPES            — pocket_rect/pocket_round/cutout/slot/groove
  _is_feature_parent               — True wenn parent_id auf eingebettetes
                                     subtraktives Feature zeigt
  _resolve_feature_in_feature      — Pocket-Lokalframe: _compute_offsets in
                                     Pocket-Dims → rotate(pocket.angle_deg)
                                     → translate(pocket.offset_x/y);
                                     depth_reference=pocket_floor addiert
                                     pocket.depth zu child.depth
  _resolve_with_part_frame         — Fallback wenn Parent-Placement fehlt

Step 1 — Orientation:
  _resolve_orientation             — "hochkant"/"flach"/"NxM_liegt_auf" → dim-swap
  _pop_closest                     — Helper: Dimension aus Liste, nah an Target

Step 2 — Face:
  _SIDE_TO_FACE                    — side keyword → CadQuery face selector
  _resolve_face                    — plus Parent-Swap-Remap (z.B. oben→>X)

Step 3 — Offsets (face-aware):
  _get_face_dimensions             — Parent-Face (w, h) in Workplane-Koords
  _get_child_face_size             — Child-Face (w, h) fuer Flush/Anchor-Rechnung
  _EDGE_AXIS_MAP                   — Richtungskeyword → (wx/wy, sign) per Face
  _apply_edge_distances            — {"right":20} → (ox, oy)
  _apply_center_offset             — "versatz X mm nach links" → (ox, oy)

Step 3b — Anchor (child-point-on-parent-point):
  _ANCHOR_POINT_LUT                — keyword → (wx_factor, wy_factor) in [-0.5..+0.5]
  _ANCHOR_OFFSET_ALIAS             — up/down/forward/backward → top/bottom/front/back
  _normalize_anchor_point          — 3D-Keyword → 2D-Projektion auf Face
  _anchor_point_in_face            — keyword + face_dims → (wx, wy) konkret
  _apply_anchor                    — {child_point, parent_point, offset} → (ox, oy)
                                     Default center-auf-center (0, 0)
                                     Optional anchor.offset wird additiv angehaengt

Step 3c — Kombinator:
  _compute_offsets                 — Prioritaet: anchor > edge_distances
                                     > center_offset > alignment+side

Step 4 — Alignment-Upgrade:
  _upgrade_alignment_from_notes    — "buendig"/"flush" aus notes → alignment

Feature-Resolution:
  _resolve_feature                 — kombiniert alle Steps, liefert ResolvedFeature
                                     unterstuetzt 3 Modi: semantic / already-resolved /
                                     mixed (fix-mode-Output)
  _fallback_resolve                — Notfall-Defaults bei Exception
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import math

import structlog

from .anchor import _apply_anchor
from .face import _SIDE_TO_FACE, _resolve_face
from .offsets import (
    _EDGE_AXIS_MAP,
    _apply_center_offset,
    _apply_center_offset_axis,
    _apply_edge_distances,
    _apply_edge_distances_axis,
    _get_child_face_size,
    _get_face_dimensions,
)
from .orientation import _pop_closest, _resolve_orientation

log = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

def resolve_blueprint(semantic: dict) -> dict:
    """Convert a semantic blueprint dict to a resolved blueprint dict.

    Input:  semantic blueprint with orientation + position (side/alignment/edge_distances)
    Output: resolved blueprint with placement (face/offset_x/offset_y) and swapped params

    If the blueprint is already resolved (has 'placement'), returns it unchanged.
    """
    features = semantic.get("features", {})
    if not features:
        return semantic

    # Check if ANY feature has semantic fields (orientation or position.side).
    # If none do AND all have placement → true legacy, pass through.
    # If mixed (fix-mode: AI returned placement but lost orientation) → resolve anyway.
    has_any_semantic = False
    has_any_placement = False
    for feat in features.values():
        if not isinstance(feat, dict):
            continue
        if "orientation" in feat:
            has_any_semantic = True
        pos = feat.get("position", {})
        if isinstance(pos, dict) and "side" in pos:
            has_any_semantic = True
        if "placement" in feat and feat.get("placement") is not None:
            has_any_placement = True

    if not has_any_semantic and has_any_placement:
        # True legacy blueprint — all features have placement, none have semantic fields
        return semantic

    # Topo-sort the build_order so parents resolve before children.
    # Required for feature-in-feature placement (hole inside pocket) where
    # the child's offsets depend on the parent's resolved placement.
    original_order = semantic.get("build_order", []) or list(features.keys())
    sorted_order = _topo_sort_features(original_order, features)

    resolved_features = {}
    for fid in sorted_order:
        feat = features.get(fid)
        if not isinstance(feat, dict):
            if feat is not None:
                resolved_features[fid] = feat
            continue
        try:
            # Pass already-resolved features so feature-parent lookups succeed.
            resolved_features[fid] = _resolve_feature(
                fid, feat, features, resolved_features
            )
        except Exception as e:
            log.warning("resolver_feature_error", feature=fid, error=str(e))
            # Fallback: convert as-is with defaults
            resolved_features[fid] = _fallback_resolve(fid, feat)

    return {
        "description": semantic.get("description", ""),
        "build_order": sorted_order,
        "features": resolved_features,
    }


def _topo_sort_features(original_order: list[str], features: dict) -> list[str]:
    """Sort feature IDs so every parent comes before its children.

    Uses Kahn's algorithm with the original LLM-provided order as the
    tie-breaker, so the result is stable when no parent constraints force
    a reorder. Features whose `parent` references something not in
    `features` are treated as roots (in-degree 0) — no silent loss.

    Raises BlueprintResolverError on cycle detection so the pipeline
    surfaces the problem rather than producing wrong geometry.
    """
    feat_ids = list(features.keys())
    # Preserve original_order ordering for IDs present in features;
    # append any feature missing from original_order at the end.
    seen = set()
    primary: list[str] = []
    for fid in original_order:
        if fid in features and fid not in seen:
            primary.append(fid)
            seen.add(fid)
    for fid in feat_ids:
        if fid not in seen:
            primary.append(fid)
            seen.add(fid)

    # Compute in-degree (each feature has at most one parent in our schema).
    in_degree: dict[str, int] = {fid: 0 for fid in primary}
    children: dict[str, list[str]] = {fid: [] for fid in primary}
    for fid in primary:
        feat = features.get(fid, {})
        parent = feat.get("parent") if isinstance(feat, dict) else None
        if parent and parent in in_degree:
            in_degree[fid] = 1
            children[parent].append(fid)

    # Tie-break by primary order: pop the first ready node in primary order.
    primary_index = {fid: i for i, fid in enumerate(primary)}
    ready = sorted(
        [fid for fid, deg in in_degree.items() if deg == 0],
        key=lambda f: primary_index[f],
    )
    sorted_out: list[str] = []
    while ready:
        fid = ready.pop(0)
        sorted_out.append(fid)
        for child in children.get(fid, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                # Insert into ready while preserving primary-order tiebreak.
                idx = 0
                ci = primary_index[child]
                while idx < len(ready) and primary_index[ready[idx]] < ci:
                    idx += 1
                ready.insert(idx, child)

    if len(sorted_out) != len(primary):
        cycle = [fid for fid in primary if fid not in sorted_out]
        raise BlueprintResolverError(
            f"Cycle in feature parent graph: {cycle}"
        )
    return sorted_out


class BlueprintResolverError(Exception):
    """Raised when the resolver cannot produce a valid resolved blueprint."""


# ═══════════════════════════════════════════════════════════════════
# Step 1: Orientation Resolution
# ═══════════════════════════════════════════════════════════════════

# _resolve_orientation + _pop_closest are now imported from .orientation
# at the top of this file (see imports above).


# ═══════════════════════════════════════════════════════════════════
# Step 2: Face Calculation
# ═══════════════════════════════════════════════════════════════════

# _SIDE_TO_FACE + _resolve_face are now imported from .face at the top
# of this file (see imports above).


# ═══════════════════════════════════════════════════════════════════
# Step 3: Offset Calculation
# ═══════════════════════════════════════════════════════════════════

# All Step-3 helpers (_get_face_dimensions, _get_child_face_size,
# _EDGE_AXIS_MAP, _apply_edge_distances{,_axis}, _apply_center_offset{,_axis})
# are now imported from .offsets at the top of this file.





def _compute_offsets(
    alignment: str,
    edge_distances: dict[str, float] | None,
    parent_params: dict,
    child_params: dict,
    face: str,
    center_offset: dict[str, float] | None = None,
    anchor: dict | None = None,
    angle_deg: float = 0.0,
    feat_type: str = "",
    pocket_edge_distances: dict[str, float] | None = None,
) -> tuple[float, float]:
    """Compute numeric offset_x, offset_y from anchor / edges / center offsets / alignment.

    Priority (highest first, per axis):
      1. anchor: {child_point, parent_point, offset}  → point-on-point placement
      2a. pocket_edge_distances: {"right": 20}        → Feature-Edge 20mm
                                                        from Parent-Edge (edge-to-edge)
      2b. edge_distances:        {"right": 20}        → Feature-Center 20mm
                                                        from Parent-Edge (edge-to-center, default)
      3. center_offset:  {"left": 10}                 → from center 10mm toward left
      4. alignment keywords: flush_right, flush_top, centered, ...

    Per axis ist pocket_edge UND edge gleichberechtigt: 2a gewinnt ueber 2b
    auf derselben Achse, aber das LLM sollte ohnehin nur einen pro Achse
    emittieren. Mischformen ueber zwei Achsen (z.B. abstand_oben +
    kante_links) sind unterstuetzt und liefern pro Achse die richtige Mathe.

    All face-aware (world axis depends on which face the feature sits on).
    angle_deg is forwarded to _apply_anchor so the anchored corner stays pinned
    after the assembler's face-rotation step.
    """
    parent_w, parent_h = _get_face_dimensions(parent_params, face)
    child_w, child_h = _get_child_face_size(
        child_params, face, angle_deg=angle_deg, feat_type=feat_type
    )

    ox, oy = 0.0, 0.0

    # Priority 1: Anchor (explicit point-to-point mapping)
    if anchor:
        return _apply_anchor(face, anchor, parent_params, child_params, angle_deg)

    # Alignment sets the baseline for both axes; edge_distances / center_offset
    # may override the individual axis they address.
    alignment_lower = alignment.lower().strip()

    ox_from_alignment = 0.0
    oy_from_alignment = 0.0
    ox_has_alignment = False
    oy_has_alignment = False
    if "right" in alignment_lower:
        ox_from_alignment = +(parent_w / 2 - child_w / 2) if child_w > 0 else 0.0
        ox_has_alignment = True
    elif "left" in alignment_lower:
        ox_from_alignment = -(parent_w / 2 - child_w / 2) if child_w > 0 else 0.0
        ox_has_alignment = True
    if "top" in alignment_lower:
        oy_from_alignment = +(parent_h / 2 - child_h / 2) if child_h > 0 else 0.0
        oy_has_alignment = True
    elif "bottom" in alignment_lower:
        oy_from_alignment = -(parent_h / 2 - child_h / 2) if child_h > 0 else 0.0
        oy_has_alignment = True

    ox = ox_from_alignment
    oy = oy_from_alignment

    # Priority 2b: edge_distances (DEFAULT edge-to-CENTER) per-axis
    ox_from_edges = oy_from_edges = 0.0
    ox_edge_set = oy_edge_set = False
    if edge_distances:
        non_zero = {k: v for k, v in edge_distances.items()
                    if isinstance(v, (int, float)) and float(v) > 0}
        if non_zero:
            # Default convention: edge-to-CENTER. "Tasche 20mm von rechts"
            # means the user wants the pocket CENTER 20mm from the parent
            # edge — same mental model as "Bohrung 20mm von rechts". For
            # additive plates/boxes (world-frame children) we still need
            # edge-to-edge, hence the is_box check.
            _HOLE_LIKE_PREFIXES = ("hole", "slot", "groove", "pocket", "cutout",
                                   "chamfer", "fillet", "bevel", "recess")
            ftype_lower = (feat_type or "").lower()
            is_hole_like = any(ftype_lower.startswith(p) or ftype_lower == p
                               for p in _HOLE_LIKE_PREFIXES)
            is_box = child_w > 0 and child_h > 0 and not is_hole_like

            # Slot/Groove: Mittellinien-Bezug auf beiden Achsen (ISO 129-1,
            # siehe docs/conventions/21_nut_slot_din.md). Slot ist
            # hole-like → is_box=False → edge-to-CENTER (Mittellinie) auf
            # beiden Achsen, ohne child_half-Subtraktion. Keine per-Achse-
            # Sonderbehandlung. Restwandstaerken-Intent wird ueber
            # `pocket_edge_distances` (`kante_*`) explizit ausgedrueckt.
            is_box_wx = is_box_wy = None

            # DIN-Konvention 24 fuer hole_pattern_linear: A1 (`abstand_*`)
            # bezieht sich auf die outermost-Hole, nicht den Pattern-Center.
            # Direction-Achse = edge-to-EDGE (Pattern-Span subtrahieren),
            # perpendicular = edge-to-CENTER (Default).
            if ftype_lower == "hole_pattern_linear" and (child_w > 0 or child_h > 0):
                direction = str(child_params.get("direction") or "x").lower()
                if direction == "y":
                    is_box_wx, is_box_wy = False, True
                else:
                    is_box_wx, is_box_wy = True, False

            # DIN-Konvention 24 fuer hole_pattern_grid: A1 bezieht sich auf
            # die outermost-Hole — beide Achsen edge-to-EDGE (Pattern-Span
            # subtrahieren). Greift nur beim expliziten Schema, wo
            # _get_child_face_size eine Footprint > 0 liefert.
            if ftype_lower == "hole_pattern_grid" and (child_w > 0 or child_h > 0):
                is_box_wx, is_box_wy = True, True

            ox_e, oy_e, ox_edge_set, oy_edge_set = _apply_edge_distances_axis(
                face, non_zero, parent_w, parent_h, child_w, child_h, is_box,
                is_box_wx=is_box_wx, is_box_wy=is_box_wy,
            )
            ox_from_edges, oy_from_edges = ox_e, oy_e

    # Priority 2a: pocket_edge_distances (EXPLICIT edge-to-EDGE) per-axis
    # Forciert is_box=True, also wird child_half abgezogen → Feature-Kante
    # zur Parent-Kante. Ueberschreibt edge_distances auf derselben Achse.
    ox_from_pocket_edges = oy_from_pocket_edges = 0.0
    ox_pocket_set = oy_pocket_set = False
    if pocket_edge_distances:
        # `kante_<dir>: 0` ist semantisch valide — "buendig anliegend",
        # also Feature-Kante exakt auf der Parent-Kante. Nur fuer
        # `pocket_edge_distances` (edge-to-EDGE) erlaubt; bei
        # `edge_distances` (edge-to-CENTER) bleibt `> 0` Pflicht, weil
        # `0` dort hiesse "Center auf Kante" und das Feature halb
        # ausserhalb des Bauteils saesse.
        non_zero = {k: v for k, v in pocket_edge_distances.items()
                    if isinstance(v, (int, float)) and float(v) >= 0}
        if non_zero:
            ox_p, oy_p, ox_pocket_set, oy_pocket_set = _apply_edge_distances_axis(
                face, non_zero, parent_w, parent_h, child_w, child_h,
                is_box=True,
            )
            ox_from_pocket_edges, oy_from_pocket_edges = ox_p, oy_p

    # Priority 3: Center offsets — per-axis override (only if no edge on that axis)
    ox_from_center = oy_from_center = 0.0
    ox_center_set = oy_center_set = False
    if center_offset:
        non_zero = {k: v for k, v in center_offset.items()
                    if isinstance(v, (int, float)) and float(v) != 0}
        if non_zero:
            ox_c, oy_c, ox_center_set, oy_center_set = _apply_center_offset_axis(
                face, non_zero
            )
            ox_from_center, oy_from_center = ox_c, oy_c

    # Compose per-axis: pocket_edge > edge > alignment as the BASE position.
    # Bug 4 (Run e3ddd2d0 tasche_rechts_22): when both an edge_distance AND
    # a center_offset are emitted on the same axis (User-Phrasing
    # "...25mm entfernt 10mm nach rechts versetzt"), the user's intent is
    # additive — first place by the edge, THEN nudge by the offset. Old
    # behavior: edge wins, center silently dropped → 10mm lost.
    # New behavior: center_offset acts as an additive delta on top of the
    # edge-based base; only "promotes" to a standalone axis value when no
    # edge field set the axis.
    if ox_pocket_set:
        ox = ox_from_pocket_edges
    elif ox_edge_set:
        ox = ox_from_edges
    elif ox_center_set:
        ox = ox_from_center
    # else: keep ox_from_alignment (already assigned)
    if oy_pocket_set:
        oy = oy_from_pocket_edges
    elif oy_edge_set:
        oy = oy_from_edges
    elif oy_center_set:
        oy = oy_from_center

    # Additive center_offset on top of edge-based base — only apply when
    # an edge / pocket_edge already set THIS axis (otherwise the value
    # was already promoted via the elif chain above).
    if ox_center_set and (ox_pocket_set or ox_edge_set):
        ox += ox_from_center
    if oy_center_set and (oy_pocket_set or oy_edge_set):
        oy += oy_from_center

    return (_clean_zero(round(ox, 4)), _clean_zero(round(oy, 4)))


def _clean_zero(v: float) -> float:
    """Convert -0.0 to 0.0."""
    return 0.0 if v == 0.0 else v


# ═══════════════════════════════════════════════════════════════════
# Step 4: Alignment Upgrade from Notes
# ═══════════════════════════════════════════════════════════════════

def _upgrade_alignment_from_notes(alignment: str, notes: str,
                                  has_edge_distances: bool = False) -> str:
    """Upgrade alignment if notes contain flush/bündig hints.

    The Assembly agent sometimes puts alignment info in notes instead of
    the alignment field. This extracts it so _compute_offsets handles it.

    Examples:
      "Untere Kante bündig" → flush_bottom
      "Oben bündig"         → flush_top
      "Rechts bündig"       → flush_right
      "Links bündig"        → flush_left

    NOTE: Only triggers on explicit flush markers ("bündig", "flush",
    "anliegend"). A bare directional word like "oben-links" is NOT enough
    — that's just a positional hint, not a flush instruction.

    NOTE: Skipped entirely if edge_distances is present, because the user
    has already specified custom positioning. Flush + edge_distances would
    double-position and yield wrong offsets (see runs.jsonl 66cf6877).
    """
    if not notes:
        return alignment

    # Only upgrade if alignment is still generic "centered"
    if alignment.lower() not in ("centered", "zentriert"):
        return alignment

    # If user already specified custom positioning via edge_distances,
    # don't downgrade it to flush.
    if has_edge_distances:
        return alignment

    nl = notes.lower()
    # Require an explicit flush keyword — not just a directional hint.
    if not any(kw in nl for kw in ("bündig", "buendig", "flush", "anliegend")):
        return alignment

    if "unten" in nl or "untere" in nl or "bottom" in nl:
        return "flush_bottom"
    if "oben" in nl or "obere" in nl or "top" in nl:
        return "flush_top"
    if "rechts" in nl or "right" in nl:
        return "flush_right"
    if "links" in nl or "left" in nl:
        return "flush_left"

    return alignment


# ═══════════════════════════════════════════════════════════════════
# Feature Resolution (combines all steps)
# ═══════════════════════════════════════════════════════════════════

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
