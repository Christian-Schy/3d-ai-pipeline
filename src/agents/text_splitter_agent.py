"""
src/agents/text_splitter_agent.py — Text-Splitter (Textzerpflücker).

Reads the full specification and the inventar part list, then splits the text
into one focused text segment per part. Each segment contains only the words
relevant to that specific part, so downstream agents don't get confused by
descriptions of other parts.

One LLM call for all parts at once.
"""

import json
import re
import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_text_splitter.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
TEMPLATE = _prompt.TEXT_SPLITTER_TEMPLATE


class TextSplitterAgent(BaseAgent):
    """Splits full spec into one focused text per part.

    Input:  specification (full text) + inventar teile list
    Output: {teil_id: focused_text} dict
    """

    name = "text_splitter"

    def __init__(self):
        cfg = get_config()
        self.model = getattr(cfg.models, "text_splitter",
                             getattr(cfg.models, "inventar", cfg.models.assembly))
        super().__init__()

    def split(self, specification: str, teile: list[dict]) -> dict[str, str]:
        """Return {teil_id: text} for each teil in the inventar.

        Falls back to full spec for any teil not found in LLM output.
        """
        if not teile:
            return {}

        teil_liste_str = "\n".join(
            f"  - {t['id']} ({t.get('beschreibung') or t.get('type', '')})"
            for t in teile
        )

        prompt = TEMPLATE.format(
            specification=specification,
            teil_liste=teil_liste_str,
        )
        raw = self.call(prompt, system=SYSTEM_PROMPT, json_mode=True)
        self._last_raw_response = raw

        result = self._parse(raw, teile, specification)
        log.info("text_splitter_done", parts=len(result),
                 ids=list(result.keys()))
        return result

    def _parse(self, raw: str, teile: list[dict],
               fallback: str) -> dict[str, str]:
        """Parse JSON output into {teil_id: text}. Fallback to full spec on error."""
        known_ids = {t["id"] for t in teile}
        result: dict[str, str] = {}

        try:
            # Strip markdown fences if present
            cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
            data = json.loads(cleaned)
            for entry in data.get("teile", []):
                tid = entry.get("id", "")
                text = entry.get("text", "").strip()
                if tid in known_ids and text:
                    result[tid] = text
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            log.warning("text_splitter_parse_error", error=str(e)[:120])

        # Fallback: fill in any missing teil with the full spec
        for t in teile:
            if t["id"] not in result:
                log.warning("text_splitter_missing_teil",
                            teil_id=t["id"], using="full_spec")
                result[t["id"]] = fallback

        return result
