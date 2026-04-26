"""
src/tools/position_builder.py — Deterministic: normalized position → semantic position dict.

Takes the standardized output from PositionNormalizerAgent and builds a
complete position + orientation dict for the semantic blueprint.

100% deterministic, no LLM. The vocabulary is fixed and small.

Same pattern as feature_builder.py but for part-on-part positioning.
"""

from __future__ import annotations
import re
import structlog

log = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# Ausrichtung → alignment mapping
# ═══════════════════════════════════════════════════════════════════

_AUSRICHTUNG_TO_ALIGNMENT = {
    "zentriert":              "centered",
    "zentral":                "centered",
    "buendig_oben":           "flush_top",
    "buendig_unten":          "flush_bottom",
    "buendig_rechts":         "flush_right",
    "buendig_links":          "flush_left",
    "buendig_oben_rechts":    "flush_right_top",
    "buendig_oben_links":     "flush_left_top",
    "buendig_unten_rechts":   "flush_right_bottom",
    "buendig_unten_links":    "flush_left_bottom",
    "von_kanten":             "centered",  # edge_distances will handle it
    "von_mitte":              "centered",  # center_offset will handle it
}


_VERSATZ_KEYS = {
    "versatz_oben":   "top",
    "versatz_unten":  "bottom",
    "versatz_rechts": "right",
    "versatz_links":  "left",
    "versatz_vorne":  "front",
    "versatz_hinten": "back",
}


# Anchor-point vocabulary that the resolver understands (same as SemanticAnchor).
_ANCHOR_POINT_KEYWORDS = {
    "center",
    "top_left", "top_right", "bottom_left", "bottom_right",
    "front_top_left", "front_top_right", "front_bottom_left", "front_bottom_right",
    "back_top_left", "back_top_right", "back_bottom_left", "back_bottom_right",
    "top_edge", "bottom_edge", "left_edge", "right_edge",
    "front_edge", "back_edge",
    "top_face", "bottom_face", "left_face", "right_face",
    "front_face", "back_face",
}


def build_position(normalized: dict) -> dict:
    """Build a semantic position dict from normalized position description.

    Args:
        normalized: Output from PositionNormalizerAgent.normalize()

    Returns:
        dict with: side, alignment, edge_distances, angle_deg, notes
    """
    seite = normalized.get("seite", "oben")
    ausrichtung = normalized.get("ausrichtung", "zentriert")
    abstand = normalized.get("abstand", {})
    winkel = normalized.get("winkel", 0)
    anker = normalized.get("anker", "")
    pre_rot_raw = normalized.get("pre_rotation", {})
    notes = normalized.get("notes", "")

    # Map ausrichtung to alignment
    alignment = _AUSRICHTUNG_TO_ALIGNMENT.get(ausrichtung, "centered")

    # Build edge_distances and center_offset from abstand (two distinct concepts)
    edge_distances = _build_edge_distances(abstand)
    center_offset = _build_center_offset(abstand)

    anchor = _build_anchor(anker, pre_rot_raw, abstand)

    result = {
        "side": seite,
        "alignment": alignment,
        "edge_distances": edge_distances,
        "angle_deg": float(winkel),
        "notes": notes,
    }
    # When anchor is set, versatz is consumed by anchor.offset — avoid double-apply.
    if center_offset and not anchor:
        result["center_offset"] = center_offset
    if anchor:
        result["anchor"] = anchor
    return result


def build_orientation(normalized: dict, teil_params: dict) -> str:
    """Determine orientation keyword from normalized position.

    Args:
        normalized: Output from PositionNormalizerAgent.normalize()
        teil_params: The raw params of the part (x, y, z)

    Returns:
        str: Orientation keyword (standard, hochkant, liegend, AxB_liegt_auf)
    """
    orientierung = normalized.get("orientierung", "standard")
    anliegende_flaeche = normalized.get("anliegende_flaeche", "keine")

    # If anliegende_flaeche is specified, derive orientation from it
    if anliegende_flaeche and anliegende_flaeche != "keine":
        orient = _orientation_from_contact_face(anliegende_flaeche, teil_params)
        if orient:
            return orient

    # Map text keywords to orientation values
    if orientierung in ("hochkant", "stehend", "aufrecht", "vertikal"):
        return "hochkant"
    elif orientierung in ("liegend", "flach", "horizontal"):
        return "liegend"

    return "standard"


def _orientation_from_contact_face(face_desc: str, params: dict) -> str | None:
    """Derive orientation from contact face description.

    Emits "AxB_liegt_auf" format so the resolver can deterministically
    map the two contact dimensions to X/Y and the remaining dim to Z.

    Example: "20x100" on 20x40x100 → "20x100_liegt_auf"
             resolver produces x=20, y=100, z=40 (40 becomes height)

    Returns orientation keyword or None if can't determine.
    """
    # Parse "AxB" pattern (accept "x", "×", " x ", etc.)
    match = re.match(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)", face_desc)
    if not match:
        if "schmal" in face_desc:
            return "hochkant"
        return None

    a = float(match.group(1))
    b = float(match.group(2))

    x = float(params.get("x", 0))
    y = float(params.get("y", 0))
    z = float(params.get("z", 0))

    if not all([x, y, z]):
        return None

    # Verify the contact face actually matches two of the three dimensions.
    dims = [x, y, z]
    contact = sorted([a, b])
    for i in range(3):
        remaining = sorted([dims[j] for j in range(3) if j != i])
        if all(abs(r - c) < 0.1 for r, c in zip(remaining, contact)):
            # Emit AxB_liegt_auf with integer formatting when possible
            def _fmt(v: float) -> str:
                return str(int(v)) if abs(v - int(v)) < 1e-6 else str(v)
            return f"{_fmt(a)}x{_fmt(b)}_liegt_auf"

    # Fallback: contact face doesn't match any dim pair cleanly
    return None


def _dims_close(a: list[float], b: list[float]) -> bool:
    """Check if two dimension lists match (order-independent, within tolerance)."""
    if len(a) != len(b):
        return False
    a_sorted = sorted(a)
    b_sorted = sorted(b)
    return all(abs(x - y) < 0.1 for x, y in zip(a_sorted, b_sorted))


def _build_edge_distances(abstand: dict) -> dict | None:
    """Convert abstand dict to edge_distances dict (from-edge semantics)."""
    if not abstand:
        return None

    mapping = {
        "abstand_oben": "top",
        "abstand_unten": "bottom",
        "abstand_rechts": "right",
        "abstand_links": "left",
        "abstand_vorne": "front",
        "abstand_hinten": "back",
    }

    distances = {}
    for key, label in mapping.items():
        val = abstand.get(key)
        if val is not None and isinstance(val, (int, float)):
            distances[label] = val

    return distances if distances else None


def _build_anchor(anker: str, pre_rot_raw: dict, abstand: dict) -> dict | None:
    """Build SemanticAnchor dict from normalizer output.

    anker: "child_point_auf_parent_point" (e.g. "top_left_auf_left_edge")
    pre_rot_raw: {x: deg, y: deg, z: deg} parsed from pre_rotation line
    abstand: same abstand dict — only versatz_* keys feed anchor.offset
             (edge_distances semantics don't apply to anchor cases)

    Returns None when no anchor info present.
    """
    has_anchor = bool(anker) and "_auf_" in anker
    has_pre_rot = any(
        isinstance(v, (int, float)) and float(v) != 0.0
        for v in (pre_rot_raw or {}).values()
    )
    if not has_anchor and not has_pre_rot:
        return None

    result: dict = {}

    if has_anchor:
        child, _, parent = anker.partition("_auf_")
        child = child.strip()
        parent = parent.strip()
        if child in _ANCHOR_POINT_KEYWORDS and parent in _ANCHOR_POINT_KEYWORDS:
            result["child_point"] = child
            result["parent_point"] = parent
        else:
            log.warning("position_builder_unknown_anchor_point",
                        child=child, parent=parent)
            result["child_point"] = "center"
            result["parent_point"] = "center"
    else:
        result["child_point"] = "center"
        result["parent_point"] = "center"

    if has_pre_rot:
        pr: dict = {}
        for axis in ("x", "y", "z"):
            val = pre_rot_raw.get(axis)
            if isinstance(val, (int, float)) and float(val) != 0.0:
                pr[axis] = float(val)
        if pr:
            result["pre_rotation"] = pr

    # Anchor.offset uses directional keywords (up/down/left/right/forward/backward).
    # When anchor is set, abstand describes a shift AWAY from the named edge:
    #   "10mm von oben nach unten versetzt" → abstand_oben=10 → offset.down=10
    # So both versatz_* (center-shift vocab) and abstand_* (from-edge vocab)
    # collapse to the same directional offset in anchor mode.
    offset: dict = {}
    versatz_map = {
        "versatz_oben": "up",
        "versatz_unten": "down",
        "versatz_rechts": "right",
        "versatz_links": "left",
        "versatz_vorne": "forward",
        "versatz_hinten": "backward",
    }
    abstand_map = {
        "abstand_oben": "down",       # "10mm von oben" → shift 10 down
        "abstand_unten": "up",
        "abstand_rechts": "left",
        "abstand_links": "right",
        "abstand_vorne": "backward",
        "abstand_hinten": "forward",
    }
    if has_anchor:  # only claim versatz/abstand when anchor is set
        for key, label in versatz_map.items():
            val = abstand.get(key)
            if isinstance(val, (int, float)) and float(val) != 0.0:
                offset[label] = float(val)
        for key, label in abstand_map.items():
            val = abstand.get(key)
            if isinstance(val, (int, float)) and float(val) != 0.0:
                offset.setdefault(label, float(val))
    if offset:
        result["offset"] = offset

    return result


def _build_center_offset(abstand: dict) -> dict | None:
    """Convert abstand dict to center_offset dict (from-center semantics)."""
    if not abstand:
        return None

    offsets = {}
    for key, label in _VERSATZ_KEYS.items():
        val = abstand.get(key)
        if val is not None and isinstance(val, (int, float)):
            offsets[label] = val

    return offsets if offsets else None
