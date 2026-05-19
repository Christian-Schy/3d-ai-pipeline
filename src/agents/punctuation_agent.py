"""
src/agents/punctuation_agent.py — Pre-processor for the spec text.

Inserts commas at natural pause points so downstream agents (Inventar,
PositionExtractor, ...) see a properly segmented spec. Voice input has no
commas; without them the Inventar misreads "auf der linken seite" as part
of the body description and picks the wrong action side.

Hard safety guarantee: the agent NEVER changes any word, number, or unit.
A token-equality guard compares words before/after — if they differ at all,
the original text is kept. Worst case = no change. Best case = commas set.
"""

import re

import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_punctuation.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
PUNCTUATION_PROMPT_TEMPLATE = _prompt.PUNCTUATION_PROMPT_TEMPLATE
FEW_SHOT_EXAMPLES = _prompt.FEW_SHOT_EXAMPLES


# Skip heuristic: if the text already has roughly one comma per ~80 chars
# AND no obvious unsegmented action phrase, don't bother calling the LLM.
_ACTION_PHRASE = re.compile(
    r"\b(?<![,.\s])\s+(auf\s+der\s+(linken|rechten|oberen|unteren|vorderen|hinteren)\s+seite\s+(soll|kommt|ist))",
    re.IGNORECASE,
)


class PunctuationAgent(BaseAgent):
    """Inserts commas into a free-text CAD spec without changing any word."""

    name = "punctuation"

    # DSPy training hook — same shape as other agents. Not yet trained.
    dspy_demo_fields = {
        "input_fields": ["specification"],
        "output_field": "punctuated",
    }

    def __init__(self):
        cfg = get_config()
        # Falls back to inventar model if 'punctuation' not set in config
        self.model = getattr(cfg.models, "punctuation", cfg.models.inventar)
        super().__init__()
        # Seed the few-shot demo list with the static examples if no DSPy
        # training data is present yet. DSPy demos (if any) take precedence.
        if not self._dspy_demos:
            self._dspy_demos = [
                (f"specification: {ex['input']}", ex["output"])
                for ex in FEW_SHOT_EXAMPLES
            ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def punctuate(self, specification: str) -> str:
        """Return the spec with commas inserted at natural pause points.

        If the text already looks well-punctuated, or if the LLM altered
        any word, the original text is returned unchanged.
        """
        if not specification or not specification.strip():
            return specification

        if self._already_punctuated(specification):
            log.info("punctuation_skip", reason="already_punctuated",
                     length=len(specification))
            return specification

        prompt = PUNCTUATION_PROMPT_TEMPLATE.format(specification=specification)

        try:
            raw = self.call(prompt, system=SYSTEM_PROMPT, json_mode=False)
        except Exception as e:
            log.warning("punctuation_call_failed", error=str(e)[:120])
            return specification

        candidate = self._strip_response(raw)

        if not self._tokens_match(specification, candidate):
            log.warning("punctuation_token_mismatch",
                        original_chars=len(specification),
                        candidate_chars=len(candidate))
            return specification

        if candidate.strip() == specification.strip():
            return specification

        commas_added = candidate.count(",") - specification.count(",")
        log.info("punctuation_applied", commas_added=commas_added)
        return candidate

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _already_punctuated(text: str) -> bool:
        """Skip the LLM call only when there is no unsegmented action phrase.

        Length is NOT a skip criterion — even short voice inputs like
        "100mm wuerfel auf der linken seite soll bohrung" need the comma.
        """
        return _ACTION_PHRASE.search(text) is None

    @staticmethod
    def _strip_response(raw: str) -> str:
        """Pull the punctuated text out of the model response.

        Handles markdown fences and a leading label like 'Output:'.
        """
        text = raw.strip()

        # Strip markdown code fences if the model wrapped the answer
        if text.startswith("```"):
            lines = text.split("\n")
            end = len(lines)
            for i in range(len(lines) - 1, 0, -1):
                if lines[i].strip().startswith("```"):
                    end = i
                    break
            text = "\n".join(lines[1:end]).strip()

        # Strip a leading label "Output:", "Spezifikation:", etc.
        for prefix in ("Output:", "OUTPUT:", "Spezifikation:", "SPEZIFIKATION:"):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip()
                break

        return text

    @staticmethod
    def _normalize_tokens(text: str) -> list[str]:
        """Lowercase word tokens (letters + digits + underscore + umlauts)."""
        return re.findall(r"\w+", text.lower(), flags=re.UNICODE)

    @classmethod
    def _tokens_match(cls, original: str, candidate: str) -> bool:
        """True if both texts have the exact same word sequence."""
        return cls._normalize_tokens(original) == cls._normalize_tokens(candidate)
