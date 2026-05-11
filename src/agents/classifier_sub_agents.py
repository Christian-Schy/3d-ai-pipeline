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
        try:
            raw = self.call_json(prompt, system=self.system_prompt)
        except Exception as e:
            log.warning(
                "classifier_sub_agent_call_failed",
                agent=self.name,
                phrase=phrase_entry.get("phrase", "")[:80],
                error=str(e)[:200],
            )
            raw = {}
        return self._build_result(phrase_entry, raw)

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


class SlotClassifier(ClassifierSubAgent):
    name = "slot_classifier"
    prompt_file = "prompt_classifier_slot.py"
    default_typ = "nut"
    allowed_typs = {"nut"}
    allowed_hint_keys = {
        "laenge", "breite", "tiefe", "richtung", "rotation_deg",
        *_POSITION_HINT_KEYS,
    }


class PatternClassifier(ClassifierSubAgent):
    name = "pattern_classifier"
    prompt_file = "prompt_classifier_pattern.py"
    default_typ = "bohrung"
    allowed_typs = {"bohrung"}
    allowed_hint_keys = {
        "durchmesser", "bohr_durchmesser", "tiefe", "anzahl",
        "kreis_durchmesser", "abstand", "abstand_kante", "richtung",
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


CLASSIFIER_SUB_AGENT_CLASSES = {
    "hole_classifier": HoleClassifier,
    "pocket_classifier": PocketClassifier,
    "slot_classifier": SlotClassifier,
    "pattern_classifier": PatternClassifier,
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
