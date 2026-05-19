"""Generates ``NAME = value`` constant declarations from a feature tree.

Two kinds of constants are emitted:
  - Dimension constants (``FEAT_X``, ``FEAT_DIAMETER``, ...) for every numeric
    parameter on a feature.
  - Offset constants (``FEAT_OFFSET_X``, ``FEAT_OFFSET_Y``) pre-computed from
    placement alignment / position so the Coder doesn't have to do arithmetic.

For slots/grooves we additionally emit a ``FEAT_LENGTH`` (defaulted to the
parent dimension when null) and a ``FEAT_ANGLE`` (used for slot2D), so the
generated function gets all the information it needs as plain constants.
"""

import re

from src.graph.feature_tree import FeatureEntry, FeatureTree

from .naming import detect_slot_axis, prefix_for

_SLOT_TYPES = ("slot", "groove")

_OFFSET_RE = re.compile(r"offset\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")

# Maps an alignment keyword to (x_sign, y_sign) where sign in {-1, 0, 1}.
# 0 means "this axis isn't moved by this alignment".
_ALIGNMENT_SIGNS: dict[str, tuple[int, int]] = {
    "flush_right": (+1, 0),
    "flush_left": (-1, 0),
    "flush_top": (0, +1),
    "flush_bottom": (0, -1),
    "flush_right_top": (+1, +1),
    "corner_TR": (+1, +1),
    "flush_right_bottom": (+1, -1),
    "corner_BR": (+1, -1),
    "flush_left_top": (-1, +1),
    "corner_TL": (-1, +1),
    "flush_left_bottom": (-1, -1),
    "corner_BL": (-1, -1),
}


def generate_param_constants(ft: FeatureTree) -> list[str]:
    """Emit dimension + offset constants for every feature in build order."""
    lines: list[str] = []
    for fid in ft.build_order:
        feature = ft.features.get(fid)
        if not feature:
            continue

        block: list[str] = []
        block.extend(_emit_dimension_constants(ft, feature))
        block.extend(_emit_offset_constants(ft, feature))
        if block:
            lines.extend(block)
            lines.append("")  # blank line between feature blocks
    return lines


# ────────────────────────────────────────────────────────────────────
# Dimension constants
# ────────────────────────────────────────────────────────────────────

def _emit_dimension_constants(ft: FeatureTree, feature: FeatureEntry) -> list[str]:
    prefix = prefix_for(feature.id)
    is_slot = feature.type.lower() in _SLOT_TYPES
    out: list[str] = []

    for k, v in (feature.params or {}).items():
        if isinstance(v, (int, float)) and v > 0:
            out.append(f"{prefix}_{k.upper()} = {v}")
            if is_slot and k == "length":
                axis = detect_slot_axis(feature)
                angle = 90 if axis == "Y" else 0
                out.append(f"{prefix}_ANGLE = {angle}  # slot2D angle: {angle}° = along {axis}-axis")
        elif v is None and k == "length":
            # Legacy: fires for any length=null param, not just slots.
            out.extend(_emit_slot_length_fallback(ft, feature, prefix))

    return out


def _emit_slot_length_fallback(ft: FeatureTree, feature: FeatureEntry, prefix: str) -> list[str]:
    """Slot/groove with length=null → length := full parent dimension along slot axis.

    Tries the requested axis first; if that parent dim is missing, falls back
    to the other axis. Otherwise emits nothing.
    """
    parent_feat = ft.features.get(feature.parent) if feature.parent else None
    parent_params = (parent_feat.params or {}) if parent_feat else {}
    parent_prefix = prefix_for(feature.parent) if feature.parent else ""

    axis = detect_slot_axis(feature)
    primary_dim = "y" if axis == "Y" else "x"
    primary_axis = axis
    fallback_dim = "x" if axis == "Y" else "y"
    fallback_axis = "X" if axis == "Y" else "Y"

    for dim, dim_axis in ((primary_dim, primary_axis), (fallback_dim, fallback_axis)):
        if parent_params.get(dim):
            parent_dim_val = float(parent_params[dim])
            parent_dim_name = (
                f"{parent_prefix}_{dim.upper()}" if parent_prefix else str(parent_dim_val)
            )
            angle = 90 if dim_axis == "Y" else 0
            return [
                f"{prefix}_LENGTH = {parent_dim_name}  # full parent {dim_axis} (Nut entlang {dim_axis})",
                f"{prefix}_ANGLE = {angle}  # slot2D angle: {angle}° = along {dim_axis}-axis"
                + ("" if dim_axis == "Y" else " (default)"),
            ]
    return []


# ────────────────────────────────────────────────────────────────────
# Offset constants
# ────────────────────────────────────────────────────────────────────

def _emit_offset_constants(ft: FeatureTree, feature: FeatureEntry) -> list[str]:
    placement = feature.placement
    if not placement or not feature.parent:
        return []

    parent = ft.features.get(feature.parent)
    pp = (parent.params or {}) if parent else {}
    fp = feature.params or {}
    pw = float(pp.get("x") or 0)
    pl = float(pp.get("y") or 0)
    fw = float(fp.get("x") or 0)
    fl = float(fp.get("y") or 0)

    # Resolution order: explicit numeric → alignment → offset(...) string →
    # corner_* string → "center" sentinel.
    offset_x = float(placement.offset_x) if placement.offset_x is not None else None
    offset_y = float(placement.offset_y) if placement.offset_y is not None else None

    alignment = placement.alignment or ""
    if alignment and alignment not in ("centered", ""):
        ax, ay = _alignment_to_offsets(alignment, pw, pl, fw, fl)
        if ax is not None:
            offset_x = ax
        if ay is not None:
            offset_y = ay

    pos = placement.position
    if offset_x is None and offset_y is None and pos:
        m = _OFFSET_RE.match(str(pos))
        if m:
            offset_x = float(m.group(1))
            offset_y = float(m.group(2))

    if offset_x is None and pos in ("corner_TR", "corner_TL", "corner_BR", "corner_BL"):
        if pw and fw:
            offset_x = (pw / 2 - fw / 2) if "R" in pos else -(pw / 2 - fw / 2)
        if pl and fl:
            offset_y = (pl / 2 - fl / 2) if "T" in pos else -(pl / 2 - fl / 2)

    if offset_x is None and offset_y is None and pos == "center":
        offset_x, offset_y = 0.0, 0.0

    # Symmetry: if one axis resolved, default the other to 0 so generated
    # code never references a missing constant.
    if offset_x is not None and offset_y is None:
        offset_y = 0.0
    elif offset_y is not None and offset_x is None:
        offset_x = 0.0

    prefix = prefix_for(feature.id)
    out: list[str] = []
    if offset_x is not None:
        out.append(f"{prefix}_OFFSET_X = {round(offset_x, 4)}")
    if offset_y is not None:
        out.append(f"{prefix}_OFFSET_Y = {round(offset_y, 4)}")
    return out


def _alignment_to_offsets(
    alignment: str, pw: float, pl: float, fw: float, fl: float,
) -> tuple[float | None, float | None]:
    """Translate a flush_*/corner_* alignment keyword to (offset_x, offset_y).

    Returns None for an axis that the keyword doesn't touch. For combined
    alignments (e.g. corner_TR), BOTH axes must have valid dims or neither
    is computed — matches the legacy all-or-nothing guard.
    """
    signs = _ALIGNMENT_SIGNS.get(alignment)
    if not signs:
        return (None, None)
    sx, sy = signs

    if sx and sy:
        if not (pw and fw and pl and fl):
            return (None, None)
        return (sx * (pw / 2 - fw / 2), sy * (pl / 2 - fl / 2))

    ox = sx * (pw / 2 - fw / 2) if sx and pw and fw else None
    oy = sy * (pl / 2 - fl / 2) if sy and pl and fl else None
    return (ox, oy)
