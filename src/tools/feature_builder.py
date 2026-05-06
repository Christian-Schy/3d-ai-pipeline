"""
src/tools/feature_builder.py — Deterministic: normalized action → Feature JSON.

Takes the standardized output from NormalizerAgent and builds a complete
feature dict that the blueprint_resolver can process.

100% deterministic, no LLM. The vocabulary is fixed and small:
  typ:      bohrung | lochkreis | eckbohrungen | bohrungsreihe | nut | tasche | fase | rundung | aushoelung
  seite:    oben | unten | rechts | links | vorne | hinten
  position: zentriert | oben-rechts | oben-links | unten-rechts | unten-links | von_kanten | ...
  richtung: x | y | z
"""

from __future__ import annotations
import structlog

log = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# Type mapping: normalized typ → blueprint feature type
# ═══════════════════════════════════════════════════════════════════

_TYP_MAP = {
    "bohrung":        "hole_single",
    "lochkreis":      "hole_pattern_circular",
    "eckbohrungen":   "hole_pattern_grid",
    "bohrungsreihe":  "hole_pattern_linear",
    "nut":            "slot",
    "tasche":         "pocket_rect",
    "fase":           "chamfer",
    "rundung":        "fillet",
    "aushoelung":     "shell",
}


# ═══════════════════════════════════════════════════════════════════
# Position mapping: normalized position → alignment + edge_distances
# ═══════════════════════════════════════════════════════════════════

_POSITION_TO_ALIGNMENT = {
    "zentriert":    "centered",
    "zentral":      "centered",
    "oben-rechts":  "centered",  # edge_distances handle the actual position
    "oben-links":   "centered",
    "unten-rechts": "centered",
    "unten-links":  "centered",
    "von_kanten":   "centered",
    "oben":         "centered",
    "unten":        "centered",
    "rechts":       "centered",
    "links":        "centered",
}


_VERSATZ_KEYS = {
    "versatz_oben":   "top",
    "versatz_unten":  "bottom",
    "versatz_rechts": "right",
    "versatz_links":  "left",
    "versatz_vorne":  "front",
    "versatz_hinten": "back",
}


def _extract_center_offset(params: dict) -> dict | None:
    """Extract center-relative offsets ("versatz_*" keys) from params.

    versatz_<richtung>=N means "from center, N mm toward <richtung>".
    Returns a dict with direction keys (top/bottom/right/left/front/back).
    """
    offsets = {}
    for key, label in _VERSATZ_KEYS.items():
        val = params.get(key)
        if val is not None and isinstance(val, (int, float)):
            offsets[label] = val
    return offsets if offsets else None


_EDGE_TO_EDGE_KEYS = {
    "kante_oben":   "top",
    "kante_unten":  "bottom",
    "kante_rechts": "right",
    "kante_links":  "left",
    "kante_vorne":  "front",
    "kante_hinten": "back",
}


def _extract_pocket_edge_distances(params: dict) -> dict | None:
    """Extract explicit edge-to-edge distances ('kante_*' keys).

    Bedeutung: Feature-Kante zur Parent-Kante. Nur fuer rechteckige
    subtractive Features (pocket_rect, slot, cutout, groove) — bei
    Bohrungen ist die Konvention immer edge-to-center (abstand_*).
    Der Resolver subtrahiert child_half von der Distanz; die Pocket-
    Kante landet damit `kante_<dir>` mm von der Cube-Kante.
    """
    distances = {}
    for key, label in _EDGE_TO_EDGE_KEYS.items():
        val = params.get(key)
        if val is not None and isinstance(val, (int, float)):
            distances[label] = val
    return distances if distances else None


def _extract_edge_distances(position: str, params: dict) -> dict | None:
    """Extract edge_distances from position keyword + params.

    Konvention: edge-to-CENTER (Default). Center des Features ist
    `abstand_<dir>` mm von der Parent-Kante. Fuer edge-to-edge siehe
    `_extract_pocket_edge_distances` mit `kante_*` keys.
    """
    # Explicit distances from params
    distances = {}
    for key, label in [
        ("abstand_oben", "top"), ("abstand_unten", "bottom"),
        ("abstand_rechts", "right"), ("abstand_links", "left"),
        ("abstand_vorne", "front"), ("abstand_hinten", "back"),
        ("abstand_kante", None),  # generic "from all edges"
    ]:
        val = params.get(key)
        if val is not None and isinstance(val, (int, float)):
            if label:
                distances[label] = val
            else:
                # Generic edge distance → infer from position
                if position in ("oben-rechts", "unten-rechts", "unten-links", "oben-links"):
                    # Corner position: apply to both edges
                    mapping = {
                        "oben-rechts": {"top": val, "right": val},
                        "oben-links": {"top": val, "left": val},
                        "unten-rechts": {"bottom": val, "right": val},
                        "unten-links": {"bottom": val, "left": val},
                    }
                    distances.update(mapping.get(position, {}))
                else:
                    # Generic: all edges same distance (e.g. "Eckbohrungen")
                    distances = {"top": val, "bottom": val, "left": val, "right": val}

    # Position-based defaults (corner positions without explicit distances)
    if not distances and position in ("oben-rechts", "oben-links", "unten-rechts", "unten-links"):
        # No distances given — this means the position is descriptive
        # The resolver will handle "oben-rechts" via notes
        pass

    return distances if distances else None


def build_feature(normalized: dict, teil_id: str, action_idx: int) -> dict:
    """Build a complete feature dict from normalized action description.

    Args:
        normalized: Output from NormalizerAgent.normalize()
        teil_id: Parent part ID
        action_idx: Index for generating unique feature IDs

    Returns:
        dict: Complete feature ready for the blueprint
    """
    typ = normalized.get("typ", "")
    seite = normalized.get("seite", "oben")
    position = normalized.get("position", "zentriert")
    richtung = normalized.get("richtung", "")
    params = normalized.get("parameter", {})
    notes = normalized.get("notes", "")

    # Sometimes the normalizer puts richtung inside parameter instead of top-level
    if not richtung and "richtung" in params:
        richtung = str(params.pop("richtung")).lower()

    # Map typ to feature type
    feature_type = _TYP_MAP.get(typ)
    if not feature_type:
        log.warning("feature_builder_unknown_typ", typ=typ)
        feature_type = "hole_single"  # safe fallback

    # Generate feature ID
    feat_id = f"{typ}_{seite}_{action_idx}" if typ else f"feat_{action_idx}"

    # Build params based on type
    feature_params = _build_params(feature_type, params)

    # Build position
    alignment = _POSITION_TO_ALIGNMENT.get(position, "centered")
    edge_distances = _extract_edge_distances(position, params)
    pocket_edge_distances = _extract_pocket_edge_distances(params)
    center_offset = _extract_center_offset(params)

    # Build notes (direction info for slots/linear patterns)
    position_notes = _build_notes(feature_type, richtung, position, notes)

    # Determine operation
    if feature_type in ("chamfer", "fillet", "shell"):
        operation = "modify"
    else:
        operation = "subtract"

    # Pull rotation around the placement-face normal from the normalized
    # action params. Normalizer stores it under 'drehung' (German), so the
    # user saying "Tasche um 20 Grad gedreht" propagates here without an
    # extra prompt round-trip.
    angle_deg = 0.0
    for key in ("drehung", "winkel", "angle", "rotation"):
        val = params.get(key)
        if val is not None:
            try:
                angle_deg = float(val)
            except (TypeError, ValueError):
                pass
            if angle_deg:
                break

    position_dict = {
        "side": seite,
        "alignment": alignment,
        "edge_distances": edge_distances,
        "angle_deg": angle_deg,
        "notes": position_notes,
    }
    if center_offset:
        position_dict["center_offset"] = center_offset
    if pocket_edge_distances:
        # Edge-to-edge distances (Pocket-Kante zu Parent-Kante).
        # Resolver wendet child_half-Subtraktion an.
        position_dict["pocket_edge_distances"] = pocket_edge_distances

    return {
        "id": feat_id,
        "type": feature_type,
        "params": feature_params,
        "position": position_dict,
        "operation": operation,
    }


def _build_params(feature_type: str, raw: dict) -> dict:
    """Build typed params dict from raw normalizer params."""

    if feature_type == "hole_single":
        return {
            "diameter": raw.get("durchmesser", raw.get("bohr_durchmesser", 5)),
            "depth": raw.get("tiefe"),
        }

    elif feature_type == "hole_pattern_circular":
        return {
            "bolt_circle_diameter": raw.get("kreis_durchmesser", 60),
            "count": raw.get("anzahl", 6),
            "hole_diameter": raw.get("bohr_durchmesser", raw.get("durchmesser", 10)),
            "depth": raw.get("tiefe"),
        }

    elif feature_type == "hole_pattern_grid":
        return {
            "count": raw.get("anzahl", 4),
            "inset": raw.get("abstand_kante", raw.get("abstand", 20)),
            "hole_diameter": raw.get("bohr_durchmesser", raw.get("durchmesser", 10)),
            "depth": raw.get("tiefe"),
        }

    elif feature_type == "hole_pattern_linear":
        return {
            "count": raw.get("anzahl", 4),
            "spacing": raw.get("abstand", 20),
            "hole_diameter": raw.get("bohr_durchmesser", raw.get("durchmesser", 5)),
            "depth": raw.get("tiefe"),
        }

    elif feature_type == "slot":
        return {
            "width": raw.get("breite", 5),
            "depth": raw.get("tiefe", 3),
            "length": raw.get("laenge"),
        }

    elif feature_type == "pocket_rect":
        return {
            "x": raw.get("laenge", 30),
            "y": raw.get("breite", 30),
            "depth": raw.get("tiefe", 5),
        }

    elif feature_type == "chamfer":
        return {
            "size": raw.get("groesse", 2),
            "edge_selector": _edge_selector(raw),
        }

    elif feature_type == "fillet":
        return {
            "radius": raw.get("radius", raw.get("groesse", 2)),
            "edge_selector": _edge_selector(raw),
        }

    elif feature_type == "shell":
        return {
            "thickness": raw.get("dicke", raw.get("wandstaerke", 2)),
            "face": raw.get("seite", ">Z"),
        }

    return {}


def _edge_selector(raw: dict) -> str:
    """Determine edge selector for chamfer/fillet from params."""
    kanten = raw.get("kanten", "")
    if isinstance(kanten, str):
        kanten = kanten.lower()
        if "alle_oberen" in kanten or "oben" in kanten:
            return "|Z"
        if "alle" in kanten:
            return "|Z"  # default to top edges
        if "vertikal" in kanten:
            return "|Z"
    return "|Z"


def _build_notes(feature_type: str, richtung: str, position: str, notes: str) -> str:
    """Build notes string — primarily for direction info."""
    parts = []

    # Direction for slots and linear patterns
    if richtung and feature_type in ("slot", "hole_pattern_linear"):
        parts.append(f"entlang {richtung.upper()}")

    # Position description for resolver hints
    if position and position not in ("zentriert", "zentral"):
        parts.append(position)

    # Extra notes
    if notes:
        parts.append(notes)

    return ", ".join(parts) if parts else ""


def build_teil_definition(teil: dict, normalized_actions: list[dict]) -> dict:
    """Build a complete teil definition from a teil and its normalized actions.

    Args:
        teil: Inventar teil entry (id, type, raw_params, beschreibung)
        normalized_actions: List of normalized action dicts from NormalizerAgent

    Returns:
        dict: Complete teil definition with features
    """
    teil_id = teil["id"]
    teil_type = teil.get("type", "box")
    raw_params = teil.get("raw_params", {})

    # Determine orientation from beschreibung
    beschreibung = teil.get("beschreibung", "").lower()
    if "hochkant" in beschreibung or "stehend" in beschreibung or "aufrecht" in beschreibung:
        orientation = "hochkant"
    elif "flach" in beschreibung or "liegend" in beschreibung:
        orientation = "flach"
    else:
        orientation = "standard"

    # Build features from normalized actions
    features = []
    for idx, norm in enumerate(normalized_actions):
        feat = build_feature(norm, teil_id, idx)
        features.append(feat)

    return {
        "id": teil_id,
        "type": teil_type,
        "params": raw_params,
        "orientation": orientation,
        "features": features,
    }
