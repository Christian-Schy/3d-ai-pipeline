"""Step 3 — Offset Calculation (face-aware).

Computes (offset_x, offset_y) from positioning hints relative to a face.
The four hint kinds map to different APIs:

  edge_distances ("abstand_*")        → _apply_edge_distances
  pocket_edge_distances ("kante_*")   → _apply_edge_distances (is_box=True)
  center_offset ("versatz_*")         → _apply_center_offset

The `_axis` variants additionally report which workplane axis was set,
needed by the compose step (`_compute_offsets`) to combine multiple
hint kinds without losing the second axis.

Face-dim helpers:
  _get_face_dimensions  — parent face (w, h)
  _get_child_face_size  — child footprint on the face (pattern/slot/box)
"""

from __future__ import annotations

import math


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


def _get_child_face_size(
    child_params: dict,
    face: str,
    angle_deg: float = 0.0,
    feat_type: str = "",
) -> tuple[float, float]:
    """Get the (width, height) of a child part on the given face.

    Two kinds of children to distinguish:

    1. **Subtractive face-local features** (pocket, slot, ...) — pocket
       params carry `{x, y, depth}` where `x` / `y` are already the
       face-local horizontal / vertical extents and `depth` is perpendicular
       into the face. Slots carry `{width, length, depth}` and need the
       same face-local footprint for edge-to-edge placement:
       angle=0 => length x width, angle=90 => width x length. Side-face
       axis-remapping must NOT be applied here, otherwise the side-face
       would read child_h from a non-existent `z` field (returns 0) and
       pocket_edge_distances would silently fall back to edge-to-CENTER on
       the vertical axis (Run e3ddd2d0: tasche_vorne_5 landed at oy=90
       instead of 75 — 15mm too high).
       Detection: presence of `depth` and absence of `z`.

    2. **3D additive parts** (boxes) — `params` carry `{x, y, z}` which
       are world-aligned. Side faces remap (cy, cz) etc. — same logic
       as `_get_face_dimensions`.
    """
    ftype_lower = (feat_type or "").lower()

    # Pattern-Footprint (DIN-Konvention 24: A1-Bezug = outermost-Hole,
    # nicht Pattern-Center). Linear: Footprint nur entlang direction-Achse.
    # Grid (explizites Schema rows/cols/spacing): Footprint auf beiden
    # Achsen. Grid-Legacy (count+inset) ohne rows/cols → (0,0): inset
    # deckt die A1-Konvention direkt ab. Kreis bleibt edge-to-center.
    if ftype_lower == "hole_pattern_linear":
        try:
            count = int(child_params.get("count") or 0)
            spacing = float(child_params.get("spacing") or 0)
        except (TypeError, ValueError):
            count, spacing = 0, 0.0
        direction = str(child_params.get("direction") or "x").lower()
        span = max(0.0, (count - 1) * spacing) if count > 1 else 0.0
        if direction == "y":
            return (0.0, span)
        return (span, 0.0)

    if ftype_lower == "hole_pattern_grid":
        try:
            rows = int(child_params.get("rows") or 0)
            cols = int(child_params.get("cols") or 0)
            iso = child_params.get("spacing")
            sx = float(child_params.get("spacing_x") or iso or 0)
            sy = float(child_params.get("spacing_y") or iso or 0)
        except (TypeError, ValueError):
            rows, cols, sx, sy = 0, 0, 0.0, 0.0
        span_x = max(0.0, (cols - 1) * sx) if cols > 1 else 0.0
        span_y = max(0.0, (rows - 1) * sy) if rows > 1 else 0.0
        return (span_x, span_y)

    is_slot = ftype_lower == "slot" or (
        "width" in child_params and "length" in child_params
    )

    if is_slot:
        width = float(child_params.get("width") or child_params.get("breite") or 0)
        length = float(child_params.get("length") or child_params.get("laenge") or 0)
        if width > 0 and length > 0:
            # Slot template convention: angle=0 cuts along face-X,
            # angle=90 cuts along face-Y. For non-right angles use the
            # axis-aligned footprint so edge placement remains conservative.
            a = abs(float(angle_deg or 0.0)) % 180.0
            if math.isclose(a, 0.0, abs_tol=1e-6) or math.isclose(a, 180.0, abs_tol=1e-6):
                return (length, width)
            if math.isclose(a, 90.0, abs_tol=1e-6):
                return (width, length)
            rad = math.radians(a)
            return (
                abs(length * math.cos(rad)) + abs(width * math.sin(rad)),
                abs(length * math.sin(rad)) + abs(width * math.cos(rad)),
            )

    cx = float(child_params.get("x") or child_params.get("diameter") or 0)
    cy = float(child_params.get("y") or child_params.get("diameter") or 0)
    cz = float(child_params.get("z") or child_params.get("height") or 0)

    is_face_local = ("depth" in child_params) and ("z" not in child_params)
    if is_face_local:
        return (cx, cy)

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
    is_box_wx: bool | None = None,
    is_box_wy: bool | None = None,
) -> tuple[float, float, bool, bool]:
    """Same as _apply_edge_distances but also reports which axis was set.

    is_box_wx / is_box_wy override `is_box` per workplane axis. Used by
    pattern placement where an A1 edge distance can intentionally refer to
    the outermost child hole on one or both axes. Slots stay hole-like here:
    `edge_distances` positions their centerline on both axes; explicit
    `pocket_edge_distances` is the opt-in edge-to-edge path.
    """
    if is_box_wx is None:
        is_box_wx = is_box
    if is_box_wy is None:
        is_box_wy = is_box

    mapping = _EDGE_AXIS_MAP.get(face, _EDGE_AXIS_MAP[">Z"])
    ox, oy = 0.0, 0.0
    ox_set, oy_set = False, False

    for key, raw_val in edge_distances.items():
        try:
            val = float(raw_val)
        except (TypeError, ValueError):
            continue
        if val < 0:
            continue
        axis_info = mapping.get(key.lower())
        if not axis_info:
            continue
        axis, sign = axis_info
        half = parent_w / 2 if axis == "wx" else parent_h / 2

        is_box_for_axis = is_box_wx if axis == "wx" else is_box_wy
        # `val == 0` ist nur in edge-to-EDGE-Mode (is_box) semantisch
        # valide ("buendig anliegend" — Feature-Kante auf Parent-Kante).
        # In edge-to-CENTER-Mode hiesse `0`, dass das Feature-Center auf
        # der Kante saesse (halb ausserhalb) — also filtern.
        if val == 0 and not is_box_for_axis:
            continue
        child_half = 0.0
        if is_box_for_axis:
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
