"""
src/agents/normalizer_agent.py — Text normalization step.

Takes a free-text action description and converts it to a standardized
short-form using a fixed vocabulary. The KI only does text understanding —
no JSON schema, no spatial reasoning.

Output is plain text with key: value lines that the deterministic
FeatureBuilder can parse reliably.

Stufe 3 (ADR 0003) adds `define_feature(klassifikation, teil)` — the
new per-action entry point that takes the classified action from
AktionsKlassifizierer and returns one SemanticFeature with phrase
markers for the Aggregator (Stufe 4).
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


# Classifier emits a small typ-set; normalizer's vocabulary is broader and
# includes specific patterns (lochkreis, eckbohrungen, bohrungsreihe, ...).
# When both agree on the family, the normalizer's more specific typ wins.
# When they disagree across families OR the normalizer parsed "ignorieren",
# the classifier's coarse typ wins.
_NORMALIZER_FAMILY: dict[str, set[str]] = {
    "bohrung": {"bohrung", "lochkreis", "eckbohrungen", "bohrungsreihe"},
    "nut":     {"nut"},
    "tasche":  {"tasche", "aushoelung"},
    "fase":    {"fase"},
    "rundung": {"rundung"},
}


# Classifier param-hint keys → normalizer param keys.
# Most keys match (durchmesser, tiefe, laenge, breite, groesse, ...).
# `rotation_deg` needs translation: build_feature reads `drehung`.
# Pocket classifiers may receive user wording "Hoehe"; for subtractive
# features this is the cut depth and build_feature reads `tiefe`.
# `richtung` is handled as top-level normalized field, not as parameter.
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

_DIRECTION_PHRASE_RE = re.compile(
    r"\bentlang(?:\s+(?:der|die|den))?\s+"
    r"(?P<axis>[xyz])(?:\s*[- ]?\s*(?:achse|axis))?\b"
)


# Per-direction Bemassungs-Konventionen: A1 (abstand, edge-to-center),
# A2 (kante, edge-to-edge), A3 (versatz, center-relativ). Pro Richtung
# gilt genau eine. Der Klassifizierer entscheidet welche — wenn er fuer
# eine Richtung eine Konvention emittiert, sind die anderen beiden fuer
# dieselbe Richtung stale und muessen aus den Normalizer-Parses raus.
_CONVENTION_PREFIXES: tuple[str, ...] = ("abstand_", "versatz_", "kante_")


def _merge_param_hints(params: dict, hints: dict) -> None:
    """In-place: classifier hints win over normalizer parses.

    Rationale (ADR 0003 Stufe 5c): the classifier sees one focused phrase
    with explicit guidance for `abstand_*` / `versatz_*` / `kante_*` /
    `durchmesser` / `tiefe` / `rotation_deg`. The normalizer sees the same
    phrase but runs with think=false through a much larger prompt and
    occasionally (a) drops one of two edge-distance values to 0 or
    (b) parses the wrong Bemassungs-Konvention (`kante_links` where the
    classifier correctly read A1 `abstand_links`).

    Two-step merge:
      1. Konventions-Konflikt aufloesen: fuer jede Richtung, fuer die der
         Klassifizierer eine A1/A2/A3-Konvention emittiert, werden die
         konkurrierenden Konventions-Keys derselben Richtung aus `params`
         entfernt. Der Klassifizierer ist die Autoritaet fuer die
         Konventions-Wahl pro Achse — der Normalizer-Parse darf sie nicht
         ueberstimmen.
      2. Werte uebernehmen: jeder Hint ueberschreibt den Normalizer-Wert.

    Keys die der Klassifizierer NICHT emittiert bleiben wie der Normalizer
    sie setzte (z.B. position keyword, richtung).
    """
    if not isinstance(params, dict) or not isinstance(hints, dict):
        return

    # Step 1: clear conflicting convention-keys per direction.
    hint_directions: set[str] = set()
    for key in hints:
        for prefix in _CONVENTION_PREFIXES:
            if key.startswith(prefix) and hints.get(key) is not None:
                hint_directions.add(key[len(prefix):])
                break
    for direction in hint_directions:
        for prefix in _CONVENTION_PREFIXES:
            params.pop(prefix + direction, None)

    # Step 2: classifier hints overwrite.
    for key, val in hints.items():
        if val is None:
            continue
        if key == "richtung":
            continue
        target = _HINT_KEY_RENAME.get(key, key)
        params[target] = val


def _merge_direction_hint(normalized: dict, hints: dict) -> None:
    """Promote classifier axis hints to the normalizer's top-level field."""
    if not isinstance(normalized, dict) or not isinstance(hints, dict):
        return
    raw = hints.get("richtung")
    direction = _axis_from_richtung(str(raw or ""))
    if direction in {"x", "y", "z"}:
        normalized["richtung"] = direction


def _reconcile_typ(classifier_typ: str, normalizer_typ: str) -> str:
    """Pick the typ to use for build_feature.

    - classifier "unbekannt"/"" → trust normalizer
    - normalizer "ignorieren" or different family → trust classifier
    - same family → trust normalizer (more specific)
    """
    classifier_typ = (classifier_typ or "").lower()
    normalizer_typ = (normalizer_typ or "").lower()
    if classifier_typ not in _NORMALIZER_FAMILY:
        return normalizer_typ
    if normalizer_typ in _NORMALIZER_FAMILY[classifier_typ]:
        return normalizer_typ
    return classifier_typ


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
    params = normalized.get("parameter")
    if not isinstance(params, dict):
        return
    if params.get("laenge") is not None:
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


def _infer_direction_from_phrase(phrase: str) -> str | None:
    text = _normalize_phrase(phrase)
    match = _DIRECTION_PHRASE_RE.search(text)
    if not match:
        return None
    return _axis_from_richtung(match.group("axis"))


def _fill_direction_from_phrase(normalized: dict, phrase: str) -> None:
    if normalized.get("richtung"):
        return
    if normalized.get("typ") not in {"nut", "bohrungsreihe"}:
        return
    direction = _infer_direction_from_phrase(phrase)
    if direction:
        normalized["richtung"] = direction


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
    text = _normalize_phrase(phrase)
    if not text:
        return None

    child_point = "center"
    child_match = _CHILD_CORNER_RE.search(text)
    if child_match:
        child_point = _corner_point_from_text(child_match.group("corner")) or "center"
    else:
        child_edge_match = _CHILD_EDGE_RE.search(text)
        if child_edge_match:
            child_point = _EDGE_WORD_TO_POINT.get(child_edge_match.group("edge"), "center")

    parent_point = None
    for pattern, point in _EDGE_ANCHOR_PATTERNS:
        if pattern.search(text):
            parent_point = point
            break

    if parent_point is None:
        if child_match and " auf " in text:
            after_anchor = text.split(" auf ", 1)[1]
            parent_point = _corner_point_from_text(after_anchor)
        else:
            parent_point = _corner_point_from_text(text)

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
        """
        beschreibung = klassifikation.get("beschreibung", "")
        seite = klassifikation.get("seite", "oben")
        teil_id = teil.get("id", "")
        phrase_idx = klassifikation.get("phrase_idx", 0)
        parent_phrase_idx = klassifikation.get("parent_phrase_idx")
        klass_typ = (klassifikation.get("typ") or "").lower()
        klass_hints = klassifikation.get("parameter_hints") or {}

        # LLM call (existing per-action normalize)
        spec_context = feature_text or beschreibung
        normalized = self.normalize(beschreibung, seite, spec_context)

        # Reconcile typ — classifier wins when families diverge or normalizer
        # rejected the phrase as placement.
        chosen_typ = _reconcile_typ(klass_typ, normalized.get("typ", ""))
        if chosen_typ != normalized.get("typ"):
            self.log.info(
                "define_feature_typ_override",
                normalizer_typ=normalized.get("typ"),
                klassifizierer_typ=klass_typ,
                chosen=chosen_typ,
                phrase=beschreibung[:80],
            )
            normalized["typ"] = chosen_typ

        # Trust the classifier's seite verbatim (already validated in Stufe 2).
        if klassifikation.get("seite"):
            normalized["seite"] = klassifikation["seite"]

        # Fold classifier hints into normalizer params (gaps only).
        params = normalized.setdefault("parameter", {})
        _merge_direction_hint(normalized, klass_hints)
        _fill_direction_from_phrase(normalized, beschreibung)
        _merge_param_hints(params, klass_hints)
        if normalized.get("typ") == "nut":
            _fill_missing_slot_length(normalized, teil)

        # Deterministic SemanticFeature build. Returns None when both the
        # classifier and the normalizer rejected the phrase as a real
        # feature (typ in {"unbekannt", "ignorieren", ""}). The caller —
        # feature_definierer_node — drops None results so phantom features
        # never reach the aggregator.
        feature = build_feature(normalized, teil_id, phrase_idx)
        if feature is None:
            return None
        _apply_phrase_anchor(feature, beschreibung, params)

        # Default parent: the host teil. Aggregator (Stufe 4) overrides with
        # the pocket's feature_id for nested children.
        feature["parent"] = teil_id

        # Markers for the Aggregator. _teil_id stays a stable grouping key
        # even after the Aggregator rewrites `parent` for nested children.
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
