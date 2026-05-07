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
# Only `rotation_deg` needs translation: build_feature reads `drehung`.
_HINT_KEY_RENAME: dict[str, str] = {"rotation_deg": "drehung"}


def _merge_param_hints(params: dict, hints: dict) -> None:
    """In-place: classifier hints win over normalizer parses.

    Rationale (ADR 0003 Stufe 5c): the classifier sees one focused phrase
    with explicit guidance for `abstand_*` / `versatz_*` / `durchmesser`
    / `tiefe` / `rotation_deg`. The normalizer sees the same phrase but
    runs with think=false through a much larger prompt and occasionally
    drops one of two edge-distance values to 0 (Bug 4 in Run 3db7d152).
    When the classifier explicitly emits a value, it overrides whatever
    the normalizer parsed. Keys the classifier did not emit stay as the
    normalizer set them (e.g. position keyword, richtung, kanten).
    """
    if not isinstance(params, dict) or not isinstance(hints, dict):
        return
    for key, val in hints.items():
        if val is None:
            continue
        target = _HINT_KEY_RENAME.get(key, key)
        params[target] = val


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


class NormalizerAgent(BaseAgent):
    """Normalizes free-text action descriptions into fixed-vocabulary short-form.

    Pipeline calls per single action -> 1 feature dict.
    Training target: data/dspy_optimized/normalizer_optimized.json
    """

    name = "normalizer"
    dspy_demo_fields = {
        "input_fields": ["beschreibung", "seite", "teil_type",
                         "teil_params", "specification"],
        "output_field": "feature",
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
        _merge_param_hints(params, klass_hints)

        # Deterministic SemanticFeature build. Returns None when both the
        # classifier and the normalizer rejected the phrase as a real
        # feature (typ in {"unbekannt", "ignorieren", ""}). The caller —
        # feature_definierer_node — drops None results so phantom features
        # never reach the aggregator.
        feature = build_feature(normalized, teil_id, phrase_idx)
        if feature is None:
            return None

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
