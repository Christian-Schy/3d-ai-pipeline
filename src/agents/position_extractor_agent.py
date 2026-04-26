"""
src/agents/position_extractor_agent.py — Pre-digest step for position normalization.

Analogous to InventarAgent, but extracts per-part position descriptions
instead of per-part actions. Runs between inventar and teil_definierer.

The output feeds PositionNormalizerAgent: each child part gets a short,
focused position sentence instead of the full spec with all noise.

Rationale: Inventar works well because it pre-digests the spec. The same
pattern applied to positioning makes the per-part PositionNormalizer's
job simpler — text understanding focused on one teil at a time.
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
    """Filters per-teil position sentences from the full specification."""

    name = "position_extractor"

    def __init__(self):
        cfg = get_config()
        self.model = getattr(cfg.models, "position_extractor",
                             getattr(cfg.models, "position_normalizer",
                                     cfg.models.inventar))
        super().__init__()

    def extract(self, specification: str, teile: list[dict]) -> dict:
        """Extract per-teil position descriptions.

        Args:
            specification: Full user spec (output of interpreter).
            teile: Inventar teile list.

        Returns:
            dict with "positionen": list of {teil_id, parent_hint, beschreibung}.
            Child teile only — the first/root teil gets no entry.
        """
        if len(teile) < 2:
            return {"positionen": []}

        teile_lines = []
        for t in teile:
            params_str = ", ".join(f"{k}={v}" for k, v in t.get("raw_params", {}).items())
            teile_lines.append(f"  {t['id']}: {t.get('type', 'box')} ({params_str})")

        prompt = POSITION_EXTRACTOR_TEMPLATE.format(
            specification=specification,
            teile_liste="\n".join(teile_lines),
        )

        result = self.call_json(prompt, system=SYSTEM_PROMPT)
        return self._validate(result, teile)

    def _validate(self, data: dict, teile: list[dict]) -> dict:
        """Ensure structure + reference integrity."""
        if not isinstance(data, dict):
            raise ValueError("PositionExtractor: result is not a dict")

        positionen = data.get("positionen", [])
        if not isinstance(positionen, list):
            positionen = []

        teil_ids = {t["id"] for t in teile}
        root_id = teile[0]["id"] if teile else ""

        cleaned = []
        for p in positionen:
            if not isinstance(p, dict):
                continue
            tid = p.get("teil_id", "")
            if tid not in teil_ids:
                self.log.warning("position_extractor_unknown_teil_id", teil_id=tid)
                continue
            if tid == root_id:
                # Root has no position — ignore any hallucinated entry for it
                continue
            beschreibung = str(p.get("beschreibung", "")).strip()
            if not beschreibung:
                continue
            parent_hint = p.get("parent_hint", "")
            if parent_hint and parent_hint not in teil_ids:
                parent_hint = ""
            cleaned.append({
                "teil_id": tid,
                "parent_hint": parent_hint,
                "beschreibung": beschreibung,
            })

        return {"positionen": cleaned}
