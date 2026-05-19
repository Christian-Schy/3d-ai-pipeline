"""src/agents/aktions_klassifizierer.py — Stage 2 of the per-action chain.

Classifies a SINGLE action phrase (delivered by the deterministic
aktions_splitter) into a structured entry that the feature_definierer
uses as input. See docs/decisions/0003-inventar-feature-definierer-pro-aktion.md.

Replaces the monolithic Inventar Step B mega-call (one LLM call per teil
with ALL actions) with one tiny call per action — much smaller cognitive
load, no clumping of nested actions, parallelizable.

The structural fields {teil_id, phrase_idx, parent_phrase_idx} come 1:1
from the splitter and are NOT touched by the LLM. The classifier only
fills in {typ, seite, parameter_hints}; the splitter's `phrase` becomes
the entry's `beschreibung`.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_aktions_klassifizierer.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
AKTIONS_KLASSIFIZIERER_TEMPLATE = _prompt.AKTIONS_KLASSIFIZIERER_TEMPLATE
FEW_SHOT_EXAMPLES = _prompt.FEW_SHOT_EXAMPLES


_VALID_TYPEN = {"tasche", "bohrung", "nut", "fase", "rundung"}
_VALID_SEITEN = {"oben", "unten", "rechts", "links", "vorne", "hinten"}


class AktionsKlassifizierer(BaseAgent):
    """Classifies one action phrase into {typ, seite, parameter_hints}."""

    name = "aktions_klassifizierer"

    dspy_demo_fields = {
        "input_fields": ["phrase", "teil_type", "teil_params", "parent_phrase"],
        "output_field": "klassifikation",
    }

    def __init__(self) -> None:
        cfg = get_config()
        # Falls back to inventar model if 'aktions_klassifizierer' not in config.
        self.model = getattr(
            cfg.models, "aktions_klassifizierer", cfg.models.inventar
        )
        super().__init__()

        # Seed the few-shot demo list with static examples if no DSPy
        # training data is present yet. DSPy demos (if any) take precedence.
        if not self._dspy_demos:
            self._dspy_demos = [
                self._format_demo(ex) for ex in FEW_SHOT_EXAMPLES
            ]

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def classify(
        self,
        phrase_entry: dict[str, Any],
        teil: dict[str, Any],
        parent_phrase: str | None = None,
    ) -> dict[str, Any]:
        """Classify one action phrase from the splitter.

        Args:
            phrase_entry: A dict from aktions_splitter.split_spec_into_aktionen
                with keys: phrase, teil_id, phrase_idx, parent_phrase_idx.
            teil: The teil this action belongs to (from Inventar Step A).
                Used as context for the LLM (type + raw_params).
            parent_phrase: For nested children, the parent's original phrase
                text — lets the LLM inherit `seite` if the child does not
                state one explicitly. None for top-level actions.

        Returns:
            Enriched action dict matching the contract in ADR 0003:
                {typ, seite, beschreibung, teil_id, phrase_idx,
                 parent_phrase_idx, parameter_hints}
            Robust to malformed LLM output — falls back to safe defaults.
        """
        prompt = self._build_user_prompt(phrase_entry, teil, parent_phrase)

        try:
            raw = self.call_json(prompt, system=SYSTEM_PROMPT)
        except Exception as e:
            log.warning("aktions_klassifizierer_call_failed",
                        phrase=phrase_entry.get("phrase", "")[:80],
                        error=str(e)[:200])
            raw = {}

        return self._build_result(phrase_entry, raw)

    # ──────────────────────────────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        phrase_entry: dict[str, Any],
        teil: dict[str, Any],
        parent_phrase: str | None,
    ) -> str:
        teil_params = teil.get("raw_params") or {}
        return AKTIONS_KLASSIFIZIERER_TEMPLATE.format(
            teil_type=teil.get("type", "box"),
            teil_params=json.dumps(teil_params, ensure_ascii=False),
            parent_phrase=parent_phrase if parent_phrase else "(keine)",
            phrase=phrase_entry.get("phrase", ""),
        )

    @classmethod
    def _format_demo(cls, ex: dict[str, Any]) -> tuple[str, str]:
        """Format a static example into a (user, assistant) message pair
        compatible with BaseAgent's few-shot demo injection."""
        user = AKTIONS_KLASSIFIZIERER_TEMPLATE.format(
            teil_type=ex.get("teil_type", "box"),
            teil_params=json.dumps(
                ex.get("teil_params", {}), ensure_ascii=False
            ),
            parent_phrase=ex.get("parent_phrase", "(keine)"),
            phrase=ex.get("phrase", ""),
        )
        assistant = json.dumps(ex["output"], ensure_ascii=False)
        return user, assistant

    @staticmethod
    def _build_result(
        phrase_entry: dict[str, Any],
        llm_out: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge the splitter's structural fields with the LLM's
        classification, validate, and apply safe defaults.

        Splitter fields (teil_id, phrase_idx, parent_phrase_idx) are
        passed through unchanged. The phrase becomes `beschreibung`.
        """
        typ = (llm_out.get("typ") or "").strip().lower()
        if typ not in _VALID_TYPEN:
            typ = "unbekannt"

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
            "parameter_hints": hints,
        }
