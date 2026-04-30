"""
src/agents/normalizer_agent.py — Text normalization step.

Takes a free-text action description and converts it to a standardized
short-form using a fixed vocabulary. The KI only does text understanding —
no JSON schema, no spatial reasoning.

Output is plain text with key: value lines that the deterministic
FeatureBuilder can parse reliably.
"""

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_normalizer.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
NORMALIZER_PROMPT_TEMPLATE = _prompt.NORMALIZER_PROMPT_TEMPLATE


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
