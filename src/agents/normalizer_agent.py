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

import re

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.tools.feature_builder import build_feature
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_normalizer.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
NORMALIZER_PROMPT_TEMPLATE = _prompt.NORMALIZER_PROMPT_TEMPLATE


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

_CORNER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bobere\s+rechte\s+ecke\b"), "top_right"),
    (re.compile(r"\brechte\s+obere\s+ecke\b"), "top_right"),
    (re.compile(r"\bobere\s+linke\s+ecke\b"), "top_left"),
    (re.compile(r"\blinke\s+obere\s+ecke\b"), "top_left"),
    (re.compile(r"\buntere\s+rechte\s+ecke\b"), "bottom_right"),
    (re.compile(r"\brechte\s+untere\s+ecke\b"), "bottom_right"),
    (re.compile(r"\buntere\s+linke\s+ecke\b"), "bottom_left"),
    (re.compile(r"\blinke\s+untere\s+ecke\b"), "bottom_left"),
)

_CHILD_CORNER_RE = re.compile(
    r"\b(?P<corner>(?:obere|untere|rechte|linke)\s+"
    r"(?:rechte|linke|obere|untere)\s+ecke)\s+"
    r"(?:der|des)\s+(?:tasche|nut|bohrung|platte|features?)\b"
)

_CHILD_EDGE_RE = re.compile(
    r"\b(?P<edge>rechte|linke|obere|untere)\s+kante\s+"
    r"(?:der|des)\s+(?:tasche|nut|bohrung|platte|features?)\b"
)

_EDGE_WORD_TO_POINT: dict[str, str] = {
    "rechte": "right_edge",
    "linke": "left_edge",
    "obere": "top_edge",
    "untere": "bottom_edge",
}

_EDGE_ANCHOR_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:liegt\s+auf|auf)\s+(?:der\s+)?rechte[ern]?\s+kante\b"), "right_edge"),
    (re.compile(r"\b(?:liegt\s+auf|auf)\s+(?:der\s+)?linke[ern]?\s+kante\b"), "left_edge"),
    (re.compile(r"\b(?:liegt\s+auf|auf)\s+(?:der\s+)?obere[ern]?\s+kante\b"), "top_edge"),
    (re.compile(r"\b(?:liegt\s+auf|auf)\s+(?:der\s+)?untere[ern]?\s+kante\b"), "bottom_edge"),
)

# W4 (ADR 0014 §3) eliminated the LLM Normalizer call from `define_feature`.
# The pre-W4 helpers `_merge_param_hints`, `_reconcile_typ`,
# `_merge_direction_hint`, `_fill_direction_from_phrase` (plus
# `_DIRECTION_PHRASE_RE`, `_POSITIONING_PREFIXES`, `_CONVENTION_PREFIXES`)
# arbitrated between a classifier output and a second LLM parse. With
# only one source now, all of them are unused and removed.


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


def _normalize_phrase(text: str) -> str:
    return (
        (text or "")
        .lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )


def _corner_point_from_text(text: str) -> str | None:
    for pattern, point in _CORNER_PATTERNS:
        if pattern.search(text):
            return point
    return None


def _anchor_offset_from_params(params: dict) -> dict | None:
    offset = {}
    for param_key, anchor_key in _ANCHOR_OFFSET_PARAM_MAP.items():
        value = params.get(param_key)
        if not isinstance(value, (int, float)) or float(value) == 0:
            continue
        offset[anchor_key] = value
    return offset or None


def _infer_phrase_anchor(phrase: str) -> dict | None:
    """Detect a part-on-part anchor reference in the phrase.

    An anchor needs BOTH:
      - an explicit child reference: "Ecke der Tasche" / "Kante der Nut" /
        "obere Kante der Bohrung" (matched by _CHILD_CORNER_RE / _CHILD_EDGE_RE), AND
      - an explicit parent reference: "liegt auf der ... Kante" / "auf <corner> des
        Wuerfels" (matched by _EDGE_ANCHOR_PATTERNS or via " auf " after a child match).

    Bare corner mentions like "in der oberen rechten Ecke 22mm nach links versetzt"
    are POSITIONING — handled by the classifier (abstand_rechts/abstand_oben), NOT
    anchoring. Returning an anchor for those overrides the classifier's edge_distances
    with a position-less corner-snap (bug seen on T_kombo t08).
    """
    text = _normalize_phrase(phrase)
    if not text:
        return None

    child_point = "center"
    child_match = _CHILD_CORNER_RE.search(text)
    child_edge_match = None
    if child_match:
        child_point = _corner_point_from_text(child_match.group("corner")) or "center"
    else:
        child_edge_match = _CHILD_EDGE_RE.search(text)
        if child_edge_match:
            child_point = _EDGE_WORD_TO_POINT.get(child_edge_match.group("edge"), "center")

    # Parent-Verweis muss explizit sein. Drei legitime Signale:
    #   (a) _EDGE_ANCHOR_PATTERNS: "liegt auf der ... Kante" — parent klar.
    #   (b) child_match + " auf " im Text: "Ecke der Tasche auf <corner> des Wuerfels".
    # Eine blosse Ecken-Erwaehnung ohne (a) oder (b) ist KEIN Anker, sondern
    # Positionierung (Klassifizierer-Aufgabe). Vorher: Fallback
    # `_corner_point_from_text(text)` hat dafuer faelschlich einen Anker
    # fabriziert und damit edge_distances vom Klassifizierer ueberschrieben.
    parent_point = None
    for pattern, point in _EDGE_ANCHOR_PATTERNS:
        if pattern.search(text):
            parent_point = point
            break

    if parent_point is None and child_match and " auf " in text:
        after_anchor = text.split(" auf ", 1)[1]
        parent_point = _corner_point_from_text(after_anchor)

    if parent_point is None:
        return None
    return {"child_point": child_point, "parent_point": parent_point}


def _apply_phrase_anchor(feature: dict, phrase: str, params: dict) -> None:
    anchor = _infer_phrase_anchor(phrase)
    if not anchor:
        return
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
    """Normalizes free-text action descriptions into fixed-vocabulary short-form.

    Pipeline calls per single action -> 1 feature dict.
    Training target: data/dspy_optimized/normalizer_optimized.json
    """

    name = "normalizer"
    dspy_demo_fields = {
        "input_fields": ["beschreibung", "seite", "teil_type",
                         "teil_params", "specification"],
        "output_field": "normalisierung",
    }

    def __init__(self):
        cfg = get_config()
        # Use the same model as inventar (both are LLM-text-normalization tasks)
        self.model = getattr(cfg.models, "normalizer", cfg.models.inventar)
        super().__init__()

    def normalize(self, beschreibung: str, seite: str,
                  specification: str) -> dict:
        """Normalize one action description.

        Args:
            beschreibung: Free-text action from inventar.aktionen
            seite: The side from inventar (oben/unten/rechts/links/vorne/hinten)
            specification: Original user spec for context

        Returns:
            dict with parsed fields: typ, seite, position, richtung, parameter, notes
        """
        prompt = NORMALIZER_PROMPT_TEMPLATE.format(
            beschreibung=beschreibung,
            seite=seite or "oben",
            specification=specification,
        )

        raw = self.call(prompt, system=SYSTEM_PROMPT, json_mode=False)
        self._last_raw_response = raw
        return self._parse(raw, seite)

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

        W4 (ADR 0014 §3): the per-action LLM Normalizer call is gone. The
        classifier output is fed straight into `_build_normalized_from_hints`
        and from there into the deterministic `build_feature`. One
        Textverstaendnis-Schritt per action, rest deterministic. The
        `feature_text` parameter is kept for callsite compatibility but
        is no longer needed.
        """
        del feature_text  # no longer consumed — kept in signature for callers
        beschreibung = klassifikation.get("beschreibung", "")
        teil_id = teil.get("id", "")
        phrase_idx = klassifikation.get("phrase_idx", 0)
        parent_phrase_idx = klassifikation.get("parent_phrase_idx")

        normalized = _build_normalized_from_hints(klassifikation)

        if normalized.get("typ") == "nut":
            _fill_missing_slot_length(normalized, teil)

        # Deterministic SemanticFeature build. Returns None for sentinel typs
        # ({"", "ignorieren", "unbekannt"}) — the caller drops None so phantom
        # features never reach the aggregator.
        feature = build_feature(normalized, teil_id, phrase_idx)
        if feature is None:
            return None

        # W5 cleanup target: _apply_phrase_anchor uses regex on the raw
        # phrase text. It stays here as a transitional helper until the
        # anchor detection moves into the classifier (ADR 0014 §7 W5).
        _apply_phrase_anchor(feature, beschreibung, normalized["parameter"])

        # Default parent: the host teil. Aggregator (Stufe 4) overrides with
        # the pocket's feature_id for nested children.
        feature["parent"] = teil_id
        feature["_teil_id"] = teil_id
        feature["_phrase_idx"] = phrase_idx
        feature["_parent_phrase_idx"] = parent_phrase_idx
        return feature

    def _parse(self, raw: str, fallback_seite: str) -> dict:
        """Parse the normalized text output into a dict.

        Stops at the second 'typ:' line — prevents multi-feature LLM responses
        from bleeding into the wrong action slot.
        """
        result = {
            "typ": "",
            "seite": fallback_seite or "oben",
            "position": "zentriert",
            "richtung": "",
            "parameter": {},
            "notes": "",
        }

        typ_seen = False
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower()
            val = val.strip()

            if key == "typ":
                if typ_seen:
                    # Second feature block starts — stop here
                    break
                typ_seen = True
                result["typ"] = val.lower()
            elif key == "seite":
                result["seite"] = val.lower()
            elif key == "position":
                result["position"] = val.lower()
            elif key == "richtung":
                result["richtung"] = val.lower()
            elif key == "notes":
                result["notes"] = val
            elif key == "parameter":
                result["parameter"] = self._parse_params(val)

        # Validate seite against allowed values
        valid_seiten = {"oben", "unten", "rechts", "links", "vorne", "hinten"}
        if result["seite"] not in valid_seiten:
            self.log.warning("normalizer_invalid_seite",
                             seite=result["seite"], fallback=fallback_seite)
            result["seite"] = fallback_seite or "oben"

        return result

    def _parse_params(self, text: str) -> dict:
        """Parse 'key=val, key=val' into a dict."""
        params = {}
        for part in text.split(","):
            part = part.strip()
            if "=" not in part:
                continue
            k, _, v = part.partition("=")
            k = k.strip().lower()
            v = v.strip()
            # Try to convert to number
            if v.lower() in ("durch", "durchgaengig", "null", "none"):
                params[k] = None
            else:
                try:
                    params[k] = float(v) if "." in v else int(v)
                except ValueError:
                    params[k] = v
        return params
