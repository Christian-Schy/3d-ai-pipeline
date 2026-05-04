"""
src/agents/position_extractor_agent.py — Per-Teil Labeler.

Reads the per-teil text chunk produced by TextSplitterAgent and labels each
sentence as either placement (where the teil sits) or feature (what holes /
pockets / slots the teil has).

Input:  one teil's text (already split per part by TextSplitterAgent).
Output: {placement_sentences: [...], feature_sentences: [...]} per teil.

Rationale: tiny input + tiny task = fast and reliable on small models.
The previous version saw the full spec and tried to also do the per-teil split
in one giant call (140-line prompt, 800s runtime, frequent timeouts).
"""

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_position_extractor.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
POSITION_EXTRACTOR_TEMPLATE = _prompt.POSITION_EXTRACTOR_TEMPLATE


class PositionExtractorAgent(BaseAgent):
    """Labels sentences in a per-teil text as placement or feature."""

    name = "position_extractor"
    dspy_demo_fields = {
        "input_fields": ["teil_id", "teil_text"],
        # Output-Feld heisst "sentences" (NICHT "labels") — DSPy Example.labels
        # ist eine reservierte Methode und ueberschreibt das Feld bei Predict.
        "output_field": "sentences",
    }

    def __init__(self):
        cfg = get_config()
        self.model = getattr(cfg.models, "position_extractor",
                             getattr(cfg.models, "position_normalizer",
                                     cfg.models.inventar))
        super().__init__()

    def label(self, teil_id: str, teil_text: str) -> dict:
        """Label one teil's text into placement_sentences and feature_sentences.

        Args:
            teil_id: Identifier of the teil being labeled (for prompt context).
            teil_text: Per-teil text chunk from TextSplitterAgent.

        Returns:
            {"placement_sentences": [...], "feature_sentences": [...]}
        """
        prompt = POSITION_EXTRACTOR_TEMPLATE.format(
            teil_id=teil_id,
            teil_text=teil_text.strip(),
        )

        result = self.call_json(prompt, system=SYSTEM_PROMPT)
        return self._validate(result)

    def _validate(self, data: dict) -> dict:
        """Ensure both lists exist and contain only non-empty strings."""
        if not isinstance(data, dict):
            raise ValueError("PositionExtractor: result is not a dict")

        def _clean(key: str) -> list[str]:
            raw = data.get(key, [])
            if not isinstance(raw, list):
                return []
            return [s.strip() for s in raw if isinstance(s, str) and s.strip()]

        return {
            "placement_sentences": _clean("placement_sentences"),
            "feature_sentences": _clean("feature_sentences"),
        }
