"""Blueprint Resolver — Step 3c + Step 4: compose offsets and upgrade alignment.

The compose step is the per-axis combinator that decides which positional
signal wins (anchor > pocket_edge > edge > center > alignment) and how
multiple signals are layered (e.g. edge as base, center as additive
delta). Step 4 lifts flush hints out of free-text notes into the
alignment field so the compose step can act on them.

Public symbols (intra-package):
    _compute_offsets               — main combinator (face-aware)
    _clean_zero                    — convert -0.0 to 0.0
    _upgrade_alignment_from_notes  — promote flush hints out of notes
"""

from __future__ import annotations

from .anchor import _apply_anchor
from .offsets import (
    _apply_center_offset_axis,
    _apply_edge_distances_axis,
    _get_child_face_size,
    _get_face_dimensions,
)


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
