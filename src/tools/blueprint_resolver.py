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
import re
import structlog
from dataclasses import dataclass

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

    resolved_features = {}
    for fid, feat in features.items():
        if not isinstance(feat, dict):
            resolved_features[fid] = feat
            continue
        try:
            resolved_features[fid] = _resolve_feature(fid, feat, features)
        except Exception as e:
            log.warning("resolver_feature_error", feature=fid, error=str(e))
            # Fallback: convert as-is with defaults
            resolved_features[fid] = _fallback_resolve(fid, feat)

    return {
        "description": semantic.get("description", ""),
        "build_order": semantic.get("build_order", []),
        "features": resolved_features,
    }


# ═══════════════════════════════════════════════════════════════════
# Step 1: Orientation Resolution
# ═══════════════════════════════════════════════════════════════════

def _resolve_orientation(params: dict, orientation: str, feat_type: str,
                         side: str = "") -> tuple[dict, str]:
    """Resolve orientation keyword into concrete params with swapped dimensions.

    For box-like types (x, y, z):
      "hochkant"/"aufrecht"/"stehend" → largest dim becomes Z
      "flach"/"liegend" → smallest dim becomes Z
      "AxB_liegt_auf" → dimensions rearranged so AxB is the contact face
                        (depends on side: oben→XY, rechts→YZ, hinten→XZ)
      "N_hoch" → dim closest to N becomes Z

    For cylinder types (diameter, height): orientation can flip axis
      "liegend" → cylinder on its side (swap diameter↔height conceptually)

    Args:
      side: placement side (oben/unten/rechts/links/vorne/hinten).
            Only used for AxB_liegt_auf to determine which dims form the contact face.

    Returns:
      (resolved_params, swap_type)

      swap_type indicates which axis was swapped with Z:
        "none"  — no swap (standard orientation)
        "x_z"   — X and Z were swapped
        "y_z"   — Y and Z were swapped
        "full"  — full reorder (AxB_liegt_auf, N_hoch)
    """
    resolved = dict(params)  # shallow copy
    orientation = orientation.lower().strip()

    if orientation in ("standard", "", "normal"):
        return resolved, "none"

    # Box-like: has x, y, z
    if all(k in resolved for k in ("x", "y", "z")):
        x, y, z = float(resolved["x"]), float(resolved["y"]), float(resolved["z"])
        dims = [x, y, z]

        if orientation in ("hochkant", "aufrecht", "stehend", "vertikal"):
            # Largest dimension becomes Z (height)
            max_dim = max(dims)
            if z != max_dim:
                # Find which dim is largest and swap with z
                if x == max_dim:
                    resolved["x"], resolved["z"] = z, x
                    return resolved, "x_z"
                elif y == max_dim:
                    resolved["y"], resolved["z"] = z, y
                    return resolved, "y_z"
            return resolved, "none"

        elif orientation in ("flach", "liegend", "horizontal"):
            # Smallest dimension becomes Z (height)
            min_dim = min(dims)
            if z != min_dim:
                if x == min_dim:
                    resolved["x"], resolved["z"] = z, x
                    return resolved, "x_z"
                elif y == min_dim:
                    resolved["y"], resolved["z"] = z, y
                    return resolved, "y_z"
            return resolved, "none"

        elif "_liegt_auf" in orientation:
            # "AxB_liegt_auf" → A and B become the contact face dimensions,
            # remaining dimension = depth (perpendicular to contact face).
            # Which dims form the contact face depends on the placement side:
            #   oben/unten (>Z/<Z): contact = X×Y, depth = Z
            #   rechts/links (>X/<X): contact = Y×Z, depth = X
            #   vorne/hinten (>Y/<Y): contact = X×Z, depth = Y
            match = re.match(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)_liegt_auf", orientation)
            if match:
                target_a = float(match.group(1))
                target_b = float(match.group(2))
                remaining = [d for d in dims]
                dim_a = _pop_closest(remaining, target_a)
                dim_b = _pop_closest(remaining, target_b)
                dim_depth = remaining[0] if remaining else x

                side_lower = (side or "").lower()
                if side_lower in ("oben", "unten"):
                    # Contact = X×Y, depth = Z
                    resolved["x"], resolved["y"], resolved["z"] = dim_a, dim_b, dim_depth
                elif side_lower in ("vorne", "hinten"):
                    # Contact = X×Z, depth = Y
                    resolved["x"], resolved["y"], resolved["z"] = dim_a, dim_depth, dim_b
                else:
                    # rechts/links or unknown: Contact = Y×Z, depth = X
                    resolved["x"], resolved["y"], resolved["z"] = dim_depth, dim_a, dim_b
                return resolved, "full"

        elif "_hoch" in orientation:
            # "80_hoch" → dimension closest to 80 becomes Z
            match = re.match(r"(\d+(?:\.\d+)?)_hoch", orientation)
            if match:
                target = float(match.group(1))
                remaining = list(dims)
                new_z = _pop_closest(remaining, target)
                resolved["x"], resolved["y"] = remaining[0], remaining[1]
                resolved["z"] = new_z
                return resolved, "full"

    # Cylinder: has diameter + height
    elif "diameter" in resolved and "height" in resolved:
        if orientation in ("liegend", "horizontal", "flach"):
            resolved["_orientation_hint"] = "horizontal"
        elif orientation in ("hochkant", "aufrecht", "stehend", "vertikal"):
            resolved["_orientation_hint"] = "vertical"  # default anyway

    return resolved, "none"


def _pop_closest(dims: list[float], target: float) -> float:
    """Remove and return the dimension closest to target from dims list."""
    if not dims:
        return target
    best_idx = min(range(len(dims)), key=lambda i: abs(dims[i] - target))
    return dims.pop(best_idx)


# ═══════════════════════════════════════════════════════════════════
# Step 2: Face Calculation
# ═══════════════════════════════════════════════════════════════════

# Side keyword → CadQuery face selector
_SIDE_TO_FACE: dict[str, str] = {
    "oben":    ">Z",
    "top":     ">Z",
    "drauf":   ">Z",
    "unten":   "<Z",
    "bottom":  "<Z",
    "rechts":  ">X",
    "right":   ">X",
    "links":   "<X",
    "left":    "<X",
    "vorne":   "<Y",
    "front":   "<Y",
    "hinten":  ">Y",
    "back":    ">Y",
    "hinten":  ">Y",
    "zentriert": ">Z",  # default face for centered
    "centered":  ">Z",
}


def _resolve_face(side: str, parent_swap: str = "none") -> str:
    """Convert a side keyword to a CadQuery face selector.

    Convention: "oben" always means the original X×Y face of the part
    (as the user described it). After orientation swap, this face moves:
      - x_z swap: original >Z face becomes >X face (and <Z becomes <X)
      - y_z swap: original >Z face becomes >Y face (and <Z becomes <Y)

    So when a parent was reoriented, we remap the child's "oben"/"unten"
    to point at the face where the original X×Y surface ended up.
    """
    side_lower = side.lower().strip()
    face = _SIDE_TO_FACE.get(side_lower, ">Z")

    # If parent wasn't reoriented, no remapping needed
    if parent_swap == "none" or parent_swap == "full":
        return face

    # Remap faces based on which axis was swapped with Z
    # x_z swap: X↔Z → original top (>Z) is now right (>X), original bottom (<Z) is now left (<X)
    # y_z swap: Y↔Z → original top (>Z) is now back (>Y), original bottom (<Z) is now front (<Y)
    if parent_swap == "x_z":
        remap = {
            ">Z": ">X",   # "oben" → the original top face, now on right
            "<Z": "<X",   # "unten" → the original bottom face, now on left
            ">X": ">Z",   # "rechts" → was X, now Z (top of rotated part)
            "<X": "<Z",   # "links" → was -X, now -Z (bottom of rotated part)
            # Y faces unchanged
        }
    elif parent_swap == "y_z":
        remap = {
            ">Z": ">Y",   # "oben" → the original top face, now on back
            "<Z": "<Y",   # "unten" → the original bottom face, now on front
            ">Y": ">Z",   # "hinten" → was Y, now Z
            "<Y": "<Z",   # "vorne" → was -Y, now -Z
            # X faces unchanged
        }
    else:
        return face

    return remap.get(face, face)


# ═══════════════════════════════════════════════════════════════════
# Step 3: Offset Calculation
# ═══════════════════════════════════════════════════════════════════

def _get_face_dimensions(parent_params: dict, face: str) -> tuple[float, float]:
    """Get the (width, height) of a parent face in workplane coordinates.

    >Z/<Z face: width=parent.x, height=parent.y
    >X/<X face: width=parent.y, height=parent.z
    >Y/<Y face: width=parent.x, height=parent.z

    For cylinders: approximate as diameter x diameter (top) or diameter x height (side).
    """
    px = float(parent_params.get("x") or parent_params.get("diameter") or 100)
    py = float(parent_params.get("y") or parent_params.get("diameter") or 100)
    pz = float(parent_params.get("z") or parent_params.get("height") or 20)

    if face in (">Z", "<Z"):
        return (px, py)
    elif face in (">X", "<X"):
        return (py, pz)
    elif face in (">Y", "<Y"):
        return (px, pz)
    return (px, py)


def _get_child_face_size(child_params: dict, face: str) -> tuple[float, float]:
    """Get the (width, height) of a child part on the given face.

    Used for flush alignment calculations. Same logic as parent face dims
    but using the child's resolved (post-orientation) params.
    """
    cx = float(child_params.get("x") or child_params.get("diameter") or 0)
    cy = float(child_params.get("y") or child_params.get("diameter") or 0)
    cz = float(child_params.get("z") or child_params.get("height") or 0)

    if face in (">Z", "<Z"):
        return (cx, cy)
    elif face in (">X", "<X"):
        return (cy, cz)
    elif face in (">Y", "<Y"):
        return (cx, cz)
    return (cx, cy)


# Which edge-keywords map to which workplane axis and sign, per face.
# Workplane (wx, wy) conventions match _get_face_dimensions:
#   >Z/<Z: wx=world X, wy=world Y
#   >X/<X: wx=world Y, wy=world Z
#   >Y/<Y: wx=world X, wy=world Z
_EDGE_AXIS_MAP: dict[str, dict[str, tuple[str, int]]] = {
    ">Z": {
        "right": ("wx", +1), "left": ("wx", -1),
        "hinten": ("wy", +1), "back":  ("wy", +1), "top":    ("wy", +1),
        "vorne":  ("wy", -1), "front": ("wy", -1), "bottom": ("wy", -1),
    },
    "<Z": {
        "right": ("wx", +1), "left": ("wx", -1),
        "hinten": ("wy", +1), "back":  ("wy", +1), "top":    ("wy", +1),
        "vorne":  ("wy", -1), "front": ("wy", -1), "bottom": ("wy", -1),
    },
    ">X": {
        "hinten": ("wx", +1), "back":  ("wx", +1), "right": ("wx", +1),
        "vorne":  ("wx", -1), "front": ("wx", -1), "left":  ("wx", -1),
        "top":    ("wy", +1), "oben":  ("wy", +1),
        "bottom": ("wy", -1), "unten": ("wy", -1),
    },
    "<X": {
        "hinten": ("wx", +1), "back":  ("wx", +1), "right": ("wx", +1),
        "vorne":  ("wx", -1), "front": ("wx", -1), "left":  ("wx", -1),
        "top":    ("wy", +1), "oben":  ("wy", +1),
        "bottom": ("wy", -1), "unten": ("wy", -1),
    },
    ">Y": {
        "right": ("wx", +1), "left":  ("wx", -1),
        "top":   ("wy", +1), "oben":  ("wy", +1),
        "bottom":("wy", -1), "unten": ("wy", -1),
    },
    "<Y": {
        "right": ("wx", +1), "left":  ("wx", -1),
        "top":   ("wy", +1), "oben":  ("wy", +1),
        "bottom":("wy", -1), "unten": ("wy", -1),
    },
}


def _apply_edge_distances(
    face: str,
    edge_distances: dict[str, float],
    parent_w: float,
    parent_h: float,
    child_w: float = 0.0,
    child_h: float = 0.0,
    is_box: bool = False,
) -> tuple[float, float]:
    """Compute (ox, oy) from edge distances, face-aware.

    Zero-valued entries are ignored (AI sometimes writes {"right": 0} meaning flush_right).
    Keywords not applicable to this face are skipped silently.
    """
    ox, oy, _, _ = _apply_edge_distances_axis(
        face, edge_distances, parent_w, parent_h, child_w, child_h, is_box
    )
    return ox, oy


def _apply_center_offset(
    face: str,
    center_offset: dict[str, float],
) -> tuple[float, float]:
    """Compute (ox, oy) from center-relative offsets ("versatz_*").

    versatz_<richtung>=N means "from center, N mm toward <richtung>".
    Face-aware: same axis/sign mapping as edge distances, but magnitude is
    the raw distance (no `half - dist` subtraction).
    """
    ox, oy, _, _ = _apply_center_offset_axis(face, center_offset)
    return ox, oy


def _apply_edge_distances_axis(
    face: str,
    edge_distances: dict[str, float],
    parent_w: float,
    parent_h: float,
    child_w: float = 0.0,
    child_h: float = 0.0,
    is_box: bool = False,
) -> tuple[float, float, bool, bool]:
    """Same as _apply_edge_distances but also reports which axis was set."""
    mapping = _EDGE_AXIS_MAP.get(face, _EDGE_AXIS_MAP[">Z"])
    ox, oy = 0.0, 0.0
    ox_set, oy_set = False, False

    for key, raw_val in edge_distances.items():
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            continue
        if val <= 0:
            continue
        axis_info = mapping.get(key.lower())
        if not axis_info:
            continue
        axis, sign = axis_info
        half = parent_w / 2 if axis == "wx" else parent_h / 2
        
        # For boxes, edge distance means edge-to-edge. For holes, it's edge-to-center.
        child_half = 0.0
        if is_box:
            child_half = child_w / 2 if axis == "wx" else child_h / 2
            
        val_signed = sign * (half - val - child_half)
        
        if axis == "wx" and not ox_set:
            ox, ox_set = val_signed, True
        elif axis == "wy" and not oy_set:
            oy, oy_set = val_signed, True

    return ox, oy, ox_set, oy_set


def _apply_center_offset_axis(
    face: str,
    center_offset: dict[str, float],
) -> tuple[float, float, bool, bool]:
    """Same as _apply_center_offset but also reports which axis was set."""
    mapping = _EDGE_AXIS_MAP.get(face, _EDGE_AXIS_MAP[">Z"])
    ox, oy = 0.0, 0.0
    ox_set, oy_set = False, False

    for key, raw_val in center_offset.items():
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            continue
        if val == 0:
            continue
        axis_info = mapping.get(key.lower())
        if not axis_info:
            continue
        axis, sign = axis_info
        val_signed = sign * val
        if axis == "wx" and not ox_set:
            ox, ox_set = val_signed, True
        elif axis == "wy" and not oy_set:
            oy, oy_set = val_signed, True

    return ox, oy, ox_set, oy_set


# ═══════════════════════════════════════════════════════════════════
# Step 3b: Anchor Resolution (child point on parent point)
# ═══════════════════════════════════════════════════════════════════

# Face-local anchor keywords → (wx_factor, wy_factor) in [-0.5, +0.5] units.
# The resolver multiplies by face_w / face_h to get concrete coords.
#
# DEFAULT SEMANTICS (match user-stated rules):
#   center            → Mittelpunkt (0, 0)
#   top_left/right    → Ecke oben links/rechts  (-0.5/+0.5, +0.5)
#   bottom_left/right → Ecke unten links/rechts (-0.5/+0.5, -0.5)
#   *_edge            → Mitte der jeweiligen Kante
#
# When the Anchor-Agent says "linke Kante, 10mm von oben" it encodes that as
# eltern_punkt=top_left + eltern_abstand=unten:10  (NOT left_edge + down:10).
# That keeps this LUT simple: edge → midpoint, corner → corner, no special cases.
_ANCHOR_POINT_LUT: dict[str, tuple[float, float]] = {
    # Center (default when nothing specified)
    "center":        (0.0,  0.0),
    "zentrum":       (0.0,  0.0),
    "mitte":         (0.0,  0.0),
    "mittig":        (0.0,  0.0),
    # Face-local 2D corners
    "top_left":      (-0.5, +0.5),
    "top_right":     (+0.5, +0.5),
    "bottom_left":   (-0.5, -0.5),
    "bottom_right":  (+0.5, -0.5),
    "oben_links":    (-0.5, +0.5),
    "oben_rechts":   (+0.5, +0.5),
    "unten_links":   (-0.5, -0.5),
    "unten_rechts":  (+0.5, -0.5),
    # Face-local edge midpoints (Kante → Mittelpunkt der Kante)
    "top_edge":      ( 0.0, +0.5),
    "bottom_edge":   ( 0.0, -0.5),
    "left_edge":     (-0.5,  0.0),
    "right_edge":    (+0.5,  0.0),
    "obere_kante":   ( 0.0, +0.5),
    "untere_kante":  ( 0.0, -0.5),
    "linke_kante":   (-0.5,  0.0),
    "rechte_kante":  (+0.5,  0.0),
    # 3D corner keywords: resolver strips a leading depth prefix that does
    # not match the placement face axis (e.g. 'front_top_left' on >Z → 'top_left').
}

# Synonyms for the optional anchor.offset dict (up/down → top/bottom, etc.)
# Maps to keys that _EDGE_AXIS_MAP already understands.
_ANCHOR_OFFSET_ALIAS: dict[str, str] = {
    "up":         "top",
    "down":       "bottom",
    "forward":    "front",
    "backward":   "back",
    "vorwaerts":  "front",
    "rueckwaerts":"back",
    "hoch":       "top",
    "runter":     "bottom",
    "top":        "top",
    "bottom":     "bottom",
    "right":      "right",
    "left":       "left",
    "front":      "front",
    "back":       "back",
    "oben":       "top",
    "unten":      "bottom",
    "rechts":     "right",
    "links":      "left",
    "vorne":      "front",
    "hinten":     "back",
}


# Faces where the viewer's "right" corresponds to the NEGATIVE wx direction in the LUT.
# For these faces the Anchor-Agent uses face-viewer perspective (user convention),
# but the LUT is world-coordinate-based — so left↔right must be flipped.
#
# >X: viewer_right = +Y = wx+  ✓ no flip
# <X: viewer_right = -Y = wx-  ← flip left↔right
# >Y: viewer_right = -X = wx-  ← flip left↔right
# <Y: viewer_right = +X = wx+  ✓ no flip
# >Z / <Z: complex (tilted view) — handled separately when needed
_FACE_VIEWER_H_FLIP: set[str] = {"<X", ">Y"}

_H_FLIP_MAP: dict[str, str] = {
    "top_left":      "top_right",
    "top_right":     "top_left",
    "bottom_left":   "bottom_right",
    "bottom_right":  "bottom_left",
    "left_edge":     "right_edge",
    "right_edge":    "left_edge",
    "oben_links":    "oben_rechts",
    "oben_rechts":   "oben_links",
    "unten_links":   "unten_rechts",
    "unten_rechts":  "unten_links",
    "linke_kante":   "rechte_kante",
    "rechte_kante":  "linke_kante",
}


def _normalize_anchor_point(keyword: str, face: str) -> str:
    """Map a (possibly 3D) anchor keyword to a face-local 2D keyword.

    Applies two transformations:
    1. Strips 3D prefix that doesn't match the placement face axis
       ('front_top_left' on '>Z' → 'top_left').
    2. For faces where the viewer's right = LUT left (<X, >Y), flips
       left↔right so the agent's face-viewer vocabulary maps correctly.

    Unknown keywords fall through unchanged and end up resolving to 'center'.
    """
    kw = (keyword or "").lower().strip()
    if kw in _ANCHOR_POINT_LUT:
        # Apply horizontal flip for faces where viewer convention is mirrored
        if face in _FACE_VIEWER_H_FLIP:
            kw = _H_FLIP_MAP.get(kw, kw)
        return kw
    parts = kw.split("_")
    if len(parts) >= 2:
        head = parts[0]
        rest = "_".join(parts[1:])
        if head in ("front", "back") and face not in (">Y", "<Y"):
            if rest in _ANCHOR_POINT_LUT:
                # Apply horizontal flip after stripping 3D prefix
                if face in _FACE_VIEWER_H_FLIP:
                    return _H_FLIP_MAP.get(rest, rest)
                return rest
        if head in ("top", "bottom") and face not in (">Z", "<Z"):
            if rest in _ANCHOR_POINT_LUT:
                if face in _FACE_VIEWER_H_FLIP:
                    return _H_FLIP_MAP.get(rest, rest)
                return rest
    return kw


def _anchor_point_in_face(
    keyword: str, face: str, face_w: float, face_h: float
) -> tuple[float, float]:
    """Resolve an anchor keyword to (wx, wy) coords in the face workplane.

    Face workplane origin = face center. wx = face width axis, wy = face height axis.
    Unknown keywords fall back to center (0, 0) — keeps default behavior safe.
    """
    norm = _normalize_anchor_point(keyword, face)
    fx, fy = _ANCHOR_POINT_LUT.get(norm, (0.0, 0.0))
    return (fx * face_w, fy * face_h)


def _apply_anchor(
    face: str,
    anchor: dict,
    parent_params: dict,
    child_params: dict,
    angle_deg: float = 0.0,
) -> tuple[float, float]:
    """Compute (ox, oy) so the child's anchor point lands on the parent's anchor point.

    offset = parent_anchor_point - rotate(child_anchor_point, angle_deg)

    When angle_deg is non-zero the assembler rotates the child body BEFORE translating.
    So to keep the anchor corner pinned to the target after rotation, we pre-rotate
    the child's anchor offset by the same angle and back-solve for the center position:
        center + rotate(child_offset, angle_deg) = parent_anchor
        center = parent_anchor - rotate(child_offset, angle_deg)
        ox     = parent_wx - rotated_child_wx

    Plus an optional `offset` dict inside the anchor (e.g. {"down": 10}) that adds
    a face-relative translation after the anchor alignment.

    Defaults (child_point='center', parent_point='center', no offset) produce
    (0, 0) — identical to the legacy 'centered' alignment. That way setting
    anchor={} preserves existing behavior.
    """
    parent_w, parent_h = _get_face_dimensions(parent_params, face)
    child_w, child_h = _get_child_face_size(child_params, face)

    child_pt = anchor.get("child_point", "center")
    parent_pt = anchor.get("parent_point", "center")

    child_wx, child_wy = _anchor_point_in_face(child_pt, face, child_w, child_h)
    parent_wx, parent_wy = _anchor_point_in_face(parent_pt, face, parent_w, parent_h)

    # Rotate child anchor offset by angle_deg so the corner lands on target AFTER rotation
    if angle_deg != 0.0:
        a = math.radians(angle_deg)
        child_wx, child_wy = (
            child_wx * math.cos(a) - child_wy * math.sin(a),
            child_wx * math.sin(a) + child_wy * math.cos(a),
        )

    ox = parent_wx - child_wx
    oy = parent_wy - child_wy

    extra = anchor.get("offset") or {}
    if extra:
        normed: dict[str, float] = {}
        for k, v in extra.items():
            try:
                fval = float(v)
            except (TypeError, ValueError):
                continue
            if fval == 0:
                continue
            canon = _ANCHOR_OFFSET_ALIAS.get(str(k).lower(), str(k).lower())
            normed[canon] = fval
        if normed:
            ex, ey = _apply_center_offset(face, normed)
            ox += ex
            oy += ey

    return (_clean_zero(round(ox, 4)), _clean_zero(round(oy, 4)))


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
) -> tuple[float, float]:
    """Compute numeric offset_x, offset_y from anchor / edges / center offsets / alignment.

    Priority (highest first):
      1. anchor: {child_point, parent_point, offset}  → point-on-point placement
      2. edge_distances: {"right": 20}                → 20mm from right edge
      3. center_offset:  {"left": 10}                 → from center 10mm toward left
      4. alignment keywords: flush_right, flush_top, centered, ...

    All four are face-aware (world axis depends on which face the feature sits on).
    angle_deg is forwarded to _apply_anchor so the anchored corner stays pinned
    after the assembler's face-rotation step.
    """
    parent_w, parent_h = _get_face_dimensions(parent_params, face)
    child_w, child_h = _get_child_face_size(child_params, face)

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

    # Priority 2: Edge distances — per-axis override on top of alignment
    ox_from_edges = oy_from_edges = 0.0
    ox_edge_set = oy_edge_set = False
    if edge_distances:
        non_zero = {k: v for k, v in edge_distances.items()
                    if isinstance(v, (int, float)) and float(v) > 0}
        if non_zero:
            # Boxes need edge-to-edge distance (child half subtracted).
            # Holes/slots/pockets: "from edge Xmm" always means edge→center, no subtraction.
            _HOLE_LIKE = {"hole_single", "hole_pattern_grid", "slot", "pocket",
                          "chamfer", "fillet", "bevel", "recess"}
            is_box = child_w > 0 and child_h > 0 and feat_type not in _HOLE_LIKE
            ox_e, oy_e, ox_edge_set, oy_edge_set = _apply_edge_distances_axis(
                face, non_zero, parent_w, parent_h, child_w, child_h, is_box
            )
            ox_from_edges, oy_from_edges = ox_e, oy_e

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

    # Compose per-axis: edge > center > alignment
    if ox_edge_set:
        ox = ox_from_edges
    elif ox_center_set:
        ox = ox_from_center
    # else: keep ox_from_alignment (already assigned)
    if oy_edge_set:
        oy = oy_from_edges
    elif oy_center_set:
        oy = oy_from_center

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

def _resolve_feature(fid: str, feat: dict, all_features: dict) -> dict:
    """Resolve a single semantic feature → resolved feature.

    Handles three cases:
    1. Semantic format (has orientation + position) → full resolution
    2. Already-resolved format (has placement, no position) → keep placement, apply orientation only
    3. Mixed (fix-mode output) → best-effort
    """
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
    alignment = _upgrade_alignment_from_notes(
        alignment, notes_text,
        has_edge_distances=bool(edge_distances),
    )
    # Grid patterns (rarray) are inherently centered — inset handles the
    # edge distance, so edge_distances would shift the whole grid off-center.
    # Explicit center_offset and anchor still work for deliberate shifting.
    if feat.get("type") in ("hole_pattern_grid",) and edge_distances:
        edge_distances = None
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
