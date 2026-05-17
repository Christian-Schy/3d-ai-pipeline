"""Type-specific classifier sub-agents (ADR 0006 Phase B).

These agents are not wired into the runtime graph yet. They mirror the
AktionsKlassifizierer public contract so Phase C can route to them behind a
fallback flag without changing downstream nodes:

    splitter phrase -> {typ, seite, beschreibung, teil_id, phrase_idx,
                        parent_phrase_idx, parameter_hints}

Each sub-agent owns one narrow prompt and one DSPy artifact name.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import structlog

from src.agents.base import BaseAgent
from src.agents.demo_retriever import get_demo_retriever
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_VALID_SEITEN = {"oben", "unten", "rechts", "links", "vorne", "hinten"}

_POSITION_HINT_KEYS = {
    "abstand_oben", "abstand_unten", "abstand_rechts", "abstand_links",
    "abstand_vorne", "abstand_hinten",
    "kante_oben", "kante_unten", "kante_rechts", "kante_links",
    "kante_vorne", "kante_hinten",
    "versatz_oben", "versatz_unten", "versatz_rechts", "versatz_links",
    "versatz_vorne", "versatz_hinten",
}

# Anker-Schema (ADR 0014 W5/W5b): die Anker-Erkennung lebt im eigenen
# Mikro-Agenten `AnchorClassifier` (unten), NICHT in den typ-Klassifizierern
# — die Anker-Disambiguierung als zusaetzliche parallele Aufgabe hat das
# kleine Modell ueberlastet (pocket/slot Hang, ADR 0014 §13). Die
# typ-Klassifizierer emittieren KEINE anker_*-Hints; der AnchorClassifier
# mergt seine Hints orchestrierungsseitig dazu (planning_action_nodes).
_ANCHOR_POINTS = {
    "top_left", "top_right", "bottom_left", "bottom_right",
    "top_edge", "bottom_edge", "left_edge", "right_edge",
    "center",
}

_ANCHOR_ALIAS = {
    "oben_rechts": "top_right", "oben_links": "top_left",
    "unten_rechts": "bottom_right", "unten_links": "bottom_left",
    "rechte_obere": "top_right", "linke_obere": "top_left",
    "rechte_untere": "bottom_right", "linke_untere": "bottom_left",
    "obere_kante": "top_edge", "untere_kante": "bottom_edge",
    "rechte_kante": "right_edge", "linke_kante": "left_edge",
    "mitte": "center", "zentrum": "center",
}


def _coerce_number(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip().lower().replace("mm", "").replace(",", ".")
        try:
            parsed = float(text)
        except ValueError:
            return None
        return int(parsed) if abs(parsed - int(parsed)) < 1e-6 else parsed
    return None


def _normalize_direction(value: object) -> str | None:
    text = str(value or "").strip().lower()
    text = text.replace("_", "-").replace(" ", "")
    for axis in ("x", "y", "z"):
        if text in {axis, f"{axis}-achse", f"{axis}achse", f"{axis}-axis", f"{axis}axis"}:
            return axis
    return None


def _normalize_anchor_point(value: object) -> str | None:
    """Normalize anchor-point hint to the canonical English enum.

    Accepts the canonical tokens (top_right / right_edge / center) plus
    common German phrasings: "obere rechte ecke", "rechte obere ecke",
    "oben rechts", "rechte kante", "mitte". Spaces / hyphens / underscores
    are interchangeable. Returns None for anything outside
    `_ANCHOR_POINTS` so the LLM cannot silently inject garbage.
    """
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if text in _ANCHOR_POINTS:
        return text
    if text in _ANCHOR_ALIAS:
        return _ANCHOR_ALIAS[text]

    # Pattern-based: tokenize, ignore "ecke" filler, look for a vertical +
    # horizontal direction (corner) or a single direction + "kante" (edge).
    parts = [p for p in text.split("_") if p and p != "ecke"]
    vert = next((p for p in parts if p in ("obere", "oben", "untere", "unten")), None)
    horiz = next((p for p in parts if p in ("rechte", "rechts", "linke", "links")), None)
    if vert and horiz:
        v = "top" if vert.startswith("ob") else "bottom"
        h = "right" if horiz.startswith("rech") else "left"
        return f"{v}_{h}"
    if "kante" in parts:
        for p in parts:
            if p in ("obere", "oben"):
                return "top_edge"
            if p in ("untere", "unten"):
                return "bottom_edge"
            if p in ("rechte", "rechts"):
                return "right_edge"
            if p in ("linke", "links"):
                return "left_edge"
    return None


class ClassifierSubAgent(BaseAgent):
    """Base implementation for ADR-0006 type-specific classifiers."""

    prompt_file: ClassVar[str]
    default_typ: ClassVar[str] = "unbekannt"
    allowed_typs: ClassVar[set[str]] = set()
    allowed_hint_keys: ClassVar[set[str]] = set()

    dspy_demo_fields = {
        "input_fields": ["phrase", "teil_type", "teil_params", "parent_phrase"],
        "output_field": "klassifikation",
    }

    def __init__(self) -> None:
        cfg = get_config()
        self.model = getattr(cfg.models, self.name, cfg.models.aktions_klassifizierer)
        prompt_mod = load_prompt(self.prompt_file)
        self.system_prompt = prompt_mod.SYSTEM_PROMPT
        self.template = prompt_mod.CLASSIFIER_TEMPLATE
        super().__init__()

    def classify(
        self,
        phrase_entry: dict[str, Any],
        teil: dict[str, Any],
        parent_phrase: str | None = None,
    ) -> dict[str, Any]:
        prompt = self._build_user_prompt(phrase_entry, teil, parent_phrase)
        demos = self._retrieve_demos(phrase_entry.get("phrase", ""))
        try:
            raw = self.call_json(prompt, system=self.system_prompt, demos=demos)
        except Exception as e:
            log.warning(
                "classifier_sub_agent_call_failed",
                agent=self.name,
                phrase=phrase_entry.get("phrase", "")[:80],
                error=str(e)[:200],
            )
            raw = {}
        return self._build_result(phrase_entry, raw)

    def _retrieve_demos(self, phrase: str) -> list[tuple[str, str]] | None:
        """W6 (ADR 0014): KNN-retrieved few-shot demos for this phrase.

        Returns the K most relevant demos from the agent's full curated
        pool (`{agent}_demo_pool.json`, hybrid dense+BM25). Returns None
        when no pool exists — `call_json` then falls back to the
        agent-wide BootstrapFewShot demos.
        """
        fields = self.dspy_demo_fields or {}
        retriever = get_demo_retriever(
            self.name,
            fields.get("input_fields", []),
            fields.get("output_field", ""),
        )
        if retriever is None:
            return None
        return retriever.retrieve(phrase, k=8)

    def _build_user_prompt(
        self,
        phrase_entry: dict[str, Any],
        teil: dict[str, Any],
        parent_phrase: str | None,
    ) -> str:
        teil_params = teil.get("raw_params") or {}
        return self.template.format(
            teil_type=teil.get("type", "box"),
            teil_params=json.dumps(teil_params, ensure_ascii=False),
            parent_phrase=parent_phrase if parent_phrase else "(keine)",
            phrase=phrase_entry.get("phrase", ""),
        )

    def _build_result(
        self,
        phrase_entry: dict[str, Any],
        llm_out: dict[str, Any],
    ) -> dict[str, Any]:
        typ = (llm_out.get("typ") or "").strip().lower()
        if typ not in self.allowed_typs:
            typ = self._fallback_typ(phrase_entry.get("phrase", ""))

        seite = (llm_out.get("seite") or "").strip().lower()
        if seite not in _VALID_SEITEN:
            seite = "oben"

        hints = llm_out.get("parameter_hints")
        if not isinstance(hints, dict):
            hints = {}

        return {
            "typ": typ,
            "seite": seite,
            "beschreibung": phrase_entry.get("phrase", ""),
            "teil_id": phrase_entry.get("teil_id", ""),
            "phrase_idx": phrase_entry.get("phrase_idx", 0),
            "parent_phrase_idx": phrase_entry.get("parent_phrase_idx"),
            "parameter_hints": self._clean_hints(hints),
        }

    def _fallback_typ(self, phrase: str) -> str:
        return self.default_typ

    def _clean_hints(self, hints: dict[str, object]) -> dict[str, object]:
        cleaned: dict[str, object] = {}
        for key, value in hints.items():
            key = str(key).strip().lower()
            if key not in self.allowed_hint_keys:
                continue
            if key == "richtung":
                direction = _normalize_direction(value)
                if direction:
                    cleaned[key] = direction
                continue
            number = _coerce_number(value)
            if number is not None:
                cleaned[key] = number
        return cleaned


class HoleClassifier(ClassifierSubAgent):
    name = "hole_classifier"
    prompt_file = "prompt_classifier_hole.py"
    default_typ = "bohrung"
    allowed_typs = {"bohrung"}
    allowed_hint_keys = {
        "durchmesser", "tiefe",
        *_POSITION_HINT_KEYS,
    }


class PocketClassifier(ClassifierSubAgent):
    name = "pocket_classifier"
    prompt_file = "prompt_classifier_pocket.py"
    default_typ = "tasche"
    allowed_typs = {"tasche"}
    allowed_hint_keys = {
        "laenge", "breite", "hoehe", "tiefe", "rotation_deg",
        *_POSITION_HINT_KEYS,
    }


# Slot Anfangs-/Endpunkt-Keys (Konvention 21 N04). Der Klassifizierer
# extrahiert die zwei Endpunkt-Distanzen; feature_builder rechnet daraus
# laenge + abstand (deterministisch).
_SLOT_ENDPOINT_KEYS = {
    f"{prefix}_{direction}"
    for prefix in ("anfang", "ende")
    for direction in ("oben", "unten", "rechts", "links", "vorne", "hinten")
}


class SlotClassifier(ClassifierSubAgent):
    name = "slot_classifier"
    prompt_file = "prompt_classifier_slot.py"
    default_typ = "nut"
    allowed_typs = {"nut"}
    allowed_hint_keys = {
        "laenge", "breite", "tiefe", "richtung", "rotation_deg",
        *_POSITION_HINT_KEYS,
        *_SLOT_ENDPOINT_KEYS,
    }


class GridClassifier(ClassifierSubAgent):
    """ADR 0009 — Raster-Lochmuster + Eckbohrungen.

    Trennt explizites Raster (`rows`/`cols`/`rasterabstand` bei genanntem
    Rasterabstand) von Eckbohrungen (`anzahl`/`abstand_kante` bei Randabstand).
    Beide Arme laufen downstream auf feature_type=hole_pattern_grid; der
    typ-Name ist daher in beiden Faellen `eckbohrungen` (ADR 0014 W3 —
    spezifischer typ direkt aus dem Klassifizierer).
    """

    name = "grid_classifier"
    prompt_file = "prompt_classifier_grid.py"
    default_typ = "eckbohrungen"
    allowed_typs = {"eckbohrungen"}
    allowed_hint_keys = {
        "durchmesser", "bohr_durchmesser", "tiefe", "anzahl",
        "rows", "cols", "rasterabstand", "rasterabstand_x", "rasterabstand_y",
        "abstand_kante", "rotation_deg",
        *_POSITION_HINT_KEYS,
    }


class CircularClassifier(ClassifierSubAgent):
    """ADR 0009 — Kreis-Lochmuster (Lochkreis / Teilkreis).

    W3 (ADR 0014): emittiert direkt typ=lochkreis — Normalizer raffiniert nicht mehr.
    """

    name = "circular_classifier"
    prompt_file = "prompt_classifier_circular.py"
    default_typ = "lochkreis"
    allowed_typs = {"lochkreis"}
    allowed_hint_keys = {
        "durchmesser", "bohr_durchmesser", "tiefe", "anzahl",
        "kreis_durchmesser",
        *_POSITION_HINT_KEYS,
    }


class LinearClassifier(ClassifierSubAgent):
    """ADR 0009 — Linear-Lochmuster (Bohrungsreihe / Lochreihe).

    W3 (ADR 0014): emittiert direkt typ=bohrungsreihe — Normalizer raffiniert nicht mehr.
    """

    name = "linear_classifier"
    prompt_file = "prompt_classifier_linear.py"
    default_typ = "bohrungsreihe"
    allowed_typs = {"bohrungsreihe"}
    allowed_hint_keys = {
        "durchmesser", "bohr_durchmesser", "tiefe", "anzahl",
        "abstand", "richtung", "rotation_deg",
        *_POSITION_HINT_KEYS,
    }


class EdgeFeatureClassifier(ClassifierSubAgent):
    name = "edge_feature_classifier"
    prompt_file = "prompt_classifier_edge_feature.py"
    default_typ = "unbekannt"
    allowed_typs = {"fase", "rundung"}
    allowed_hint_keys = {"groesse", "radius", "kantenlaenge"}

    def _fallback_typ(self, phrase: str) -> str:
        text = (phrase or "").lower()
        if any(word in text for word in ("rundung", "abrund", "radius", "fillet")):
            return "rundung"
        if any(word in text for word in ("fase", "chamfer")):
            return "fase"
        return self.default_typ


class AnchorClassifier(BaseAgent):
    """ADR 0014 W5b — Anker-Mikro-Klassifizierer.

    EINE Aufgabe: erkennt, ob eine Aktions-Phrase einen Anker auf das
    Parent-Bauteil enthaelt. Ausgegliedert aus den typ-Klassifizierern,
    weil die Anker-Disambiguierung dort als zusaetzliche parallele
    Aufgabe das kleine Modell ueberlastet hat (pocket/slot Hang).

    Kein typ, keine seite, keine Masse — nur anker_kind / anker_eltern.
    `classify_anchor(phrase)` gibt {} zurueck, wenn kein Anker erkannt
    wird (der Normalfall) — sonst {anker_eltern[, anker_kind]}.
    """

    name = "anchor_classifier"
    # Prompt-only; bekommt erst per spaeterem Training eigene Demos.
    dspy_demo_fields = None

    def __init__(self) -> None:
        cfg = get_config()
        self.model = getattr(cfg.models, "anchor_classifier",
                             cfg.models.aktions_klassifizierer)
        prompt_mod = load_prompt("prompt_classifier_anchor.py")
        self.system_prompt = prompt_mod.SYSTEM_PROMPT
        self.template = prompt_mod.ANCHOR_TEMPLATE
        super().__init__()

    def classify_anchor(self, phrase: str) -> dict[str, str]:
        """Return {anker_eltern[, anker_kind]} or {} when no anchor.

        An anchor requires `anker_eltern` (the parent-side point). A lone
        `anker_kind` without a parent is dropped — that matches the
        convention rule "ohne anker_eltern wird anker_kind ignoriert".
        """
        prompt = self.template.format(phrase=phrase or "")
        try:
            raw = self.call_json(prompt, system=self.system_prompt)
        except Exception as e:  # noqa: BLE001
            log.warning("anchor_classifier_call_failed",
                        phrase=(phrase or "")[:80], error=str(e)[:200])
            return {}
        if not isinstance(raw, dict):
            return {}

        parent = _normalize_anchor_point(raw.get("anker_eltern"))
        if not parent:
            return {}
        out: dict[str, str] = {"anker_eltern": parent}
        kind = _normalize_anchor_point(raw.get("anker_kind"))
        if kind:
            out["anker_kind"] = kind
        return out


CLASSIFIER_SUB_AGENT_CLASSES = {
    "hole_classifier": HoleClassifier,
    "pocket_classifier": PocketClassifier,
    "slot_classifier": SlotClassifier,
    "grid_classifier": GridClassifier,
    "circular_classifier": CircularClassifier,
    "linear_classifier": LinearClassifier,
    "edge_feature_classifier": EdgeFeatureClassifier,
}


def build_classifier_sub_agent(name: str) -> ClassifierSubAgent:
    cls = CLASSIFIER_SUB_AGENT_CLASSES.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown classifier sub-agent '{name}'. "
            f"Known: {sorted(CLASSIFIER_SUB_AGENT_CLASSES)}"
        )
    return cls()
