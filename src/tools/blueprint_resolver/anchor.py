"""Step 3b — Anchor Resolution (child-point-on-parent-point).

Maps `anchor.child_point` / `anchor.parent_point` keywords (corners, edges,
centers) to face-local coordinates and computes the resulting offset such
that the child's anchor point lands on the parent's anchor point.

Supports:
- `child_point` / `parent_point`: corners, edge midpoints, edge-endpoints
- `angle_deg`: pre-rotates the child anchor offset so the corner stays
  pinned AFTER the assembler applies face rotation
- `anchor.offset`: optional face-relative translation after anchor alignment
"""

from __future__ import annotations

import math

from .offsets import (
    _apply_center_offset,
    _get_child_face_size,
    _get_face_dimensions,
)

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
    # Edge endpoints — for "Ecke an Kante"-Phrasen wie "rechte untere Ecke
    # auf der rechten Kante" (Bug 7, ADR 0004). Koordinaten = Ecke, aber
    # Benennung macht das Endpunkt-Anpeilen explizit.
    "right_edge_top":     (+0.5, +0.5),
    "right_edge_bottom":  (+0.5, -0.5),
    "left_edge_top":      (-0.5, +0.5),
    "left_edge_bottom":   (-0.5, -0.5),
    "top_edge_left":      (-0.5, +0.5),
    "top_edge_right":     (+0.5, +0.5),
    "bottom_edge_left":   (-0.5, -0.5),
    "bottom_edge_right":  (+0.5, -0.5),
    "rechte_kante_oben":  (+0.5, +0.5),
    "rechte_kante_unten": (+0.5, -0.5),
    "linke_kante_oben":   (-0.5, +0.5),
    "linke_kante_unten":  (-0.5, -0.5),
    "obere_kante_links":  (-0.5, +0.5),
    "obere_kante_rechts": (+0.5, +0.5),
    "untere_kante_links": (-0.5, -0.5),
    "untere_kante_rechts":(+0.5, -0.5),
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
    # Edge endpoints (Bug 7, ADR 0004) — left↔right flip on viewer-mirrored faces
    "right_edge_top":      "left_edge_top",
    "right_edge_bottom":   "left_edge_bottom",
    "left_edge_top":       "right_edge_top",
    "left_edge_bottom":    "right_edge_bottom",
    "top_edge_left":       "top_edge_right",
    "top_edge_right":      "top_edge_left",
    "bottom_edge_left":    "bottom_edge_right",
    "bottom_edge_right":   "bottom_edge_left",
    "rechte_kante_oben":   "linke_kante_oben",
    "rechte_kante_unten":  "linke_kante_unten",
    "linke_kante_oben":    "rechte_kante_oben",
    "linke_kante_unten":   "rechte_kante_unten",
    "obere_kante_links":   "obere_kante_rechts",
    "obere_kante_rechts":  "obere_kante_links",
    "untere_kante_links":  "untere_kante_rechts",
    "untere_kante_rechts": "untere_kante_links",
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
        if face in _FACE_VIEWER_H_FLIP:
            kw = _H_FLIP_MAP.get(kw, kw)
        return kw
    parts = kw.split("_")
    if len(parts) >= 2:
        head = parts[0]
        rest = "_".join(parts[1:])
        if (
            head in ("front", "back")
            and face not in (">Y", "<Y")
            and rest in _ANCHOR_POINT_LUT
        ):
            if face in _FACE_VIEWER_H_FLIP:
                return _H_FLIP_MAP.get(rest, rest)
            return rest
        if (
            head in ("top", "bottom")
            and face not in (">Z", "<Z")
            and rest in _ANCHOR_POINT_LUT
        ):
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


def _clean_zero(v: float) -> float:
    """Convert -0.0 to 0.0."""
    return 0.0 if v == 0.0 else v


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
