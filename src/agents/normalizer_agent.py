"""
src/agents/normalizer_agent.py — per-action feature definition.

Public entry point: `NormalizerAgent.define_feature(klassifikation, teil)`
turns ONE classified action into ONE SemanticFeature ready for the
aggregator (ADR 0003 Stufe 3).

W4 (ADR 0014 §3): the per-action LLM Normalizer call is gone. The
classifier owns text understanding; everything from there to the feature
dict is deterministic (`_build_normalized_from_hints` → `build_feature`).
The legacy LLM `normalize()` method is kept here only so the
`tests/agent_regression/test_normalizer.py` suite can still validate its
behaviour as we sunset it; nothing in the pipeline call path invokes it.
The class name is unchanged for callsite compatibility — a later
cleanup pass renames it to something like `FeatureDefinierer`.
"""

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.tools.feature_builder import build_feature

log = structlog.get_logger()


# Classifier param-hint keys → build_feature param keys. Most keys match
# (durchmesser, tiefe, laenge, breite, groesse, anzahl, ...). The two
# below need translation:
#   rotation_deg → drehung   — build_feature reads `drehung`.
#   hoehe        → tiefe     — pocket users say "Hoehe", build_feature
#                              treats it as the cut depth.
# `richtung` is handled as a top-level field by `_build_normalized_from_hints`,
# not as a parameter.
_HINT_KEY_RENAME: dict[str, str] = {
    "rotation_deg": "drehung",
    "hoehe": "tiefe",
}

_SIDE_FACE_AXES: dict[str, tuple[str, str]] = {
    "oben": ("x", "y"),
    "unten": ("x", "y"),
    "rechts": ("y", "z"),
    "links": ("y", "z"),
    "vorne": ("x", "z"),
    "hinten": ("x", "z"),
}

_ANCHOR_OFFSET_PARAM_MAP: dict[str, str] = {
    "versatz_oben": "top",
    "versatz_unten": "bottom",
    "versatz_rechts": "right",
    "versatz_links": "left",
    "versatz_vorne": "front",
    "versatz_hinten": "back",
}

# W4 (ADR 0014 §3) eliminated the LLM Normalizer from `define_feature`;
# its merge/reconcile helpers are gone with it.
#
# W5 (ADR 0014 §7) eliminated the regex-on-raw-phrase anchor detection
# (`_apply_phrase_anchor`, `_infer_phrase_anchor`, `_CORNER_PATTERNS`,
# `_CHILD_CORNER_RE`, `_CHILD_EDGE_RE`, `_EDGE_ANCHOR_PATTERNS`,
# `_normalize_phrase`, `_corner_point_from_text`). The anchor is now an
# emitted classifier hint (`anker_kind` / `anker_eltern`); the
# deterministic `_apply_anchor_from_hints` below applies it.


def _axis_from_richtung(richtung: str) -> str | None:
    richtung_norm = (richtung or "").strip().lower().replace("_", "-")
    for axis in ("x", "y", "z"):
        if richtung_norm in {
            axis,
            f"{axis}-achse",
            f"{axis}achse",
            f"{axis}-axis",
            f"{axis}axis",
        }:
            return axis
    return None


def _part_dimension(raw_params: dict, axis: str) -> float | int | None:
    value = raw_params.get(axis)
    if value is None and axis in ("x", "y"):
        value = raw_params.get("diameter") or raw_params.get("durchmesser")
    if value is None and axis == "z":
        value = raw_params.get("height") or raw_params.get("hoehe")
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_full_slot_length(teil: dict, seite: str, richtung: str) -> float | int | None:
    """Infer the through/full slot length from the host part dimensions.

    The normalizer only identifies "slot along axis"; the deterministic path
    owns the parent-dimension default used by N_kombo when no explicit
    `laenge` is present.
    """
    raw_params = teil.get("raw_params") or {}
    face_axes = _SIDE_FACE_AXES.get((seite or "").lower(), ("x", "y"))
    axis = _axis_from_richtung(richtung) or face_axes[0]
    if axis not in face_axes:
        axis = face_axes[0]
    return _part_dimension(raw_params, axis)


def _fill_missing_slot_length(normalized: dict, teil: dict) -> None:
    """Default a missing slot length from the host part's axis dimension.

    Skipped when classifier emitted anfang_/ende_ endpoint hints — those
    are a stronger signal and `_resolve_slot_endpoints` (in feature_builder)
    will compute `laenge = |ende - anfang|` from them. Filling here first
    would lock in the parent-dim default before that runs.
    """
    params = normalized.get("parameter")
    if not isinstance(params, dict):
        return
    if params.get("laenge") is not None:
        return
    if any(k.startswith(("anfang_", "ende_")) for k in params):
        return
    inferred = _infer_full_slot_length(
        teil,
        normalized.get("seite", "oben"),
        normalized.get("richtung", ""),
    )
    if inferred is not None:
        params["laenge"] = inferred


def _anchor_offset_from_params(params: dict) -> dict | None:
    """Translate versatz_<richtung> params to anchor.offset {top/bottom/...}."""
    offset = {}
    for param_key, anchor_key in _ANCHOR_OFFSET_PARAM_MAP.items():
        value = params.get(param_key)
        if not isinstance(value, (int, float)) or float(value) == 0:
            continue
        offset[anchor_key] = value
    return offset or None


def _apply_anchor_from_hints(feature: dict, hints: dict, params: dict) -> None:
    """W5: build feature.position.anchor from classifier hints.

    Replaces the pre-W5 `_apply_phrase_anchor` regex on the raw phrase.
    The classifier emits `anker_kind` / `anker_eltern` (already filtered
    to `_ANCHOR_POINTS` enums in classifier_sub_agents._clean_hints);
    here we just assemble the anchor dict and let it override the
    coordinate-based position fields.
    """
    if not isinstance(hints, dict):
        return
    parent = hints.get("anker_eltern")
    if not parent:
        return
    child = hints.get("anker_kind") or "center"
    anchor = {"child_point": child, "parent_point": parent}
    offset = _anchor_offset_from_params(params)
    if offset:
        anchor["offset"] = offset

    position = feature.setdefault("position", {})
    position["anchor"] = anchor
    position.pop("center_offset", None)
    position.pop("edge_distances", None)
    position.pop("pocket_edge_distances", None)


# ──────────────────────────────────────────────────────────────────────
# W4 (ADR 0014 §3) — deterministic Klassifizierer → build_feature path.
# Replaces the per-action LLM Normalizer call. The Klassifizierer is now
# the ONE Textverstaendnis-Schritt; everything below is rule-mapping.
# ──────────────────────────────────────────────────────────────────────

# Slot-Endpunkt-Achse: Endpunkt-Edge → Slot-Achse. Wird genutzt, wenn der
# slot_classifier eine Phrase mit anfang_/ende_ schickt aber kein richtung.
_ENDPOINT_DIR_TO_AXIS: dict[str, str] = {
    "links": "x", "rechts": "x",
    "vorne": "y", "hinten": "y",
    "oben": "z", "unten": "z",
}


def _derive_position_keyword(hints: dict) -> str:
    """Map classifier hints to the legacy `position` token build_feature reads.

    feature_builder uses `position` mainly to recognize Eckbohrungen layouts
    (corner-token + generic `abstand_kante` → distribute to two edges).
    Bei direkter Versatz-Bemassung (abstand_<dir>) macht es keinen
    Unterschied, weil der Resolver die Werte aus dem parameter-Dict liest.
    """
    ns = next((d for d in ("oben", "unten") if f"abstand_{d}" in hints), None)
    ew = next((d for d in ("rechts", "links") if f"abstand_{d}" in hints), None)
    if ns and ew:
        return f"{ns}-{ew}"
    has_edge_key = any(
        k.startswith(("abstand_", "kante_", "anfang_", "ende_")) for k in hints
    )
    if has_edge_key:
        return "von_kanten"
    if any(k.startswith("versatz_") for k in hints):
        return "von_mitte"
    return "zentriert"


def _derive_richtung_from_endpoints(hints: dict) -> str:
    """Slot-Achse aus Endpunkt-Edges ableiten (anfang_/ende_ <edge>).

    Wenn der slot_classifier zwei Endpunkte an `links`/`rechts` emittiert,
    verlaeuft der Slot entlang X (analog `vorne/hinten` → Y, `oben/unten` → Z).
    Saubere Voll-Bestimmtheit fuer den N04-Endpunkt-Modus auch ohne explizites
    "entlang X" im Text.
    """
    for d, axis in _ENDPOINT_DIR_TO_AXIS.items():
        if f"anfang_{d}" in hints or f"ende_{d}" in hints:
            return axis
    return ""


def _build_normalized_from_hints(klassifikation: dict) -> dict:
    """W4: build the feature_builder-input dict from a classifier output alone.

    Replaces the per-action LLM Normalizer call. The classifier
    (`parameter_hints`) is the sole source of truth; positioning,
    direction, parameter sizes and the `position` token are derived
    deterministically.

    Output shape matches what `build_feature()` expects:
        {typ, seite, position, richtung, parameter, notes}
    """
    typ = (klassifikation.get("typ") or "").lower()
    seite = (klassifikation.get("seite") or "oben").lower()
    hints = klassifikation.get("parameter_hints") or {}
    if not isinstance(hints, dict):
        hints = {}

    params: dict = {}
    richtung = ""
    for key, val in hints.items():
        if val is None:
            continue
        k = str(key).strip().lower()
        if k == "richtung":
            axis = _axis_from_richtung(str(val))
            if axis:
                richtung = axis
            continue
        target = _HINT_KEY_RENAME.get(k, k)
        params[target] = val

    if not richtung and typ == "nut":
        richtung = _derive_richtung_from_endpoints(hints)

    return {
        "typ": typ,
        "seite": seite,
        "position": _derive_position_keyword(hints),
        "richtung": richtung,
        "parameter": params,
        "notes": "",
    }


class NormalizerAgent(BaseAgent):
    """Per-action feature definition (W4/W5: no LLM, deterministic only).

    The class name and `name = "normalizer"` are preserved purely so the
    pipeline registry and existing callsites keep working. There is no
    `normalize()` LLM method anymore; the only entry point is
    `define_feature(klassifikation, teil)`, which is rule-only — the
    `BaseAgent`-provided model/demos infrastructure is left in place but
    not consumed by any code path here.
    """

    name = "normalizer"
    # W4/W5: no LLM call survives — no demos to load.
    dspy_demo_fields = None

    def __init__(self):
        cfg = get_config()
        # Model attribute stays so callers reading `agent.model` keep working,
        # but it is no longer used to make any LLM call from this class.
        self.model = getattr(cfg.models, "normalizer", cfg.models.inventar)
        super().__init__()

    def define_feature(
        self,
        klassifikation: dict,
        teil: dict,
        feature_text: str = "",
    ) -> dict | None:
        """Build ONE SemanticFeature from ONE classified action.

        Stufe 3 of ADR 0003. Replaces the implicit (normalize → build_feature)
        chain with a single per-action entry point that returns a feature
        carrying `_phrase_idx` / `_parent_phrase_idx` markers — the Aggregator
        (Stufe 4) uses those to wire `parent` for nested children.

        Args:
            klassifikation: Output from AktionsKlassifizierer.classify(): dict
                with keys typ, seite, beschreibung, teil_id, phrase_idx,
                parent_phrase_idx, parameter_hints.
            teil: Inventar Step A teil (id, type, raw_params).
            feature_text: Optional richer spec context (per-teil text or full
                spec). Defaults to the phrase itself when empty.

        Returns:
            SemanticFeature dict per ADR 0003 contract:
                {id, type, params, position, parent, operation,
                 _phrase_idx, _parent_phrase_idx}

        W4 (ADR 0014 §3) eliminated the per-action LLM Normalizer call;
        the classifier output flows straight through
        `_build_normalized_from_hints` into the deterministic
        `build_feature`. W5 (ADR 0014 §7) removed the last regex on the
        raw phrase by moving anchor detection into the classifier — the
        `anker_kind` / `anker_eltern` hints feed
        `_apply_anchor_from_hints`. The `feature_text` parameter is kept
        in the signature for callsite compatibility but is no longer read.
        """
        del feature_text  # no longer consumed — kept in signature for callers
        teil_id = teil.get("id", "")
        phrase_idx = klassifikation.get("phrase_idx", 0)
        parent_phrase_idx = klassifikation.get("parent_phrase_idx")
        hints = klassifikation.get("parameter_hints") or {}

        normalized = _build_normalized_from_hints(klassifikation)

        if normalized.get("typ") == "nut":
            _fill_missing_slot_length(normalized, teil)

        # Deterministic SemanticFeature build. Returns None for sentinel typs
        # ({"", "ignorieren", "unbekannt"}) — the caller drops None so phantom
        # features never reach the aggregator.
        feature = build_feature(normalized, teil_id, phrase_idx)
        if feature is None:
            return None

        _apply_anchor_from_hints(feature, hints, normalized["parameter"])

        # Default parent: the host teil. Aggregator (Stufe 4) overrides with
        # the pocket's feature_id for nested children.
        feature["parent"] = teil_id
        feature["_teil_id"] = teil_id
        feature["_phrase_idx"] = phrase_idx
        feature["_parent_phrase_idx"] = parent_phrase_idx
        return feature
