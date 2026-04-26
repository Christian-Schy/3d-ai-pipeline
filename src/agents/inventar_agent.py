"""
src/agents/inventar_agent.py — Step 1 of the 3-Step Blueprint Chain.

Extracts a parts inventory (Stueckliste) from the user specification:
  - How many bodies (parts)?
  - What are their names, types, raw dimensions?
  - What actions (features) are described for each part?

Prompt is MODULAR: core rules always loaded, multi-part placement rules
only when the input likely describes multiple bodies.
"""

import re
import structlog

from src.agents.base import BaseAgent
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_inventar.py")
CORE_PROMPT = _prompt.CORE_PROMPT
MULTI_PART_RULES = _prompt.MULTI_PART_RULES
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT          # CORE + MULTI_PART (full)
INVENTAR_PROMPT_TEMPLATE = _prompt.INVENTAR_PROMPT_TEMPLATE

TEILE_LISTE_SYSTEM = _prompt.TEILE_LISTE_SYSTEM
TEILE_LISTE_TEMPLATE = _prompt.TEILE_LISTE_TEMPLATE
AKTIONEN_SYSTEM = _prompt.AKTIONEN_SYSTEM
AKTIONEN_TEMPLATE = _prompt.AKTIONEN_TEMPLATE

# Keywords that hint at multi-part input (placement of Teil B on Teil A)
_MULTI_PART_HINTS = re.compile(
    r"(rechts\s+(eine?|soll)|links\s+(eine?|soll)|"
    r"oben\s+(eine?|soll)|unten\s+(eine?|soll)|"
    r"vorne\s+(eine?|soll)|hinten\s+(eine?|soll)|"
    r"auf\s+der?\s+(rechten|linken|oberen|unteren)|"
    r"liegt\s+an|anliegend|daneben|darueber|darauf|"
    r"platte\b.*\bwuerfel|wuerfel\b.*\bplatte|"
    r"aufsatz|leiste\b.*\bauf\b)",
    re.IGNORECASE,
)


class InventarAgent(BaseAgent):
    """Extracts a structured parts inventory from a natural-language specification."""

    name = "inventar"
    dspy_demo_fields = {
        "input_fields": ["specification"],
        "output_field": "inventar",
    }

    def __init__(self):
        cfg = get_config()
        self.model = cfg.models.inventar
        super().__init__()

    def _build_system_prompt(self, specification: str) -> str:
        """Build system prompt — add MULTI_PART section only when relevant."""
        if _MULTI_PART_HINTS.search(specification):
            log.debug("inventar_prompt_mode", mode="multi_part")
            return CORE_PROMPT + MULTI_PART_RULES
        log.debug("inventar_prompt_mode", mode="core_only")
        return CORE_PROMPT

    # Threshold: use sequential mode when spec is complex enough
    _SEQUENTIAL_THRESHOLD = 350  # characters

    def _is_complex(self, specification: str) -> bool:
        """True for multi-part specs long enough that one-shot extraction often fails."""
        return (
            len(specification) > self._SEQUENTIAL_THRESHOLD
            and bool(_MULTI_PART_HINTS.search(specification))
        )

    def extract(
        self,
        specification: str,
        retry_feedback: str = "",
        previous_inventar: dict | None = None,
    ) -> dict:
        """Parse the user spec into an inventory of parts and actions.

        For simple specs: one-shot JSON call (fast).
        For complex multi-part specs: two sequential micro-calls so the LLM
        can focus on one task at a time (reduces hallucinations on long inputs).

        Args:
            specification: The complete, unambiguous spec from Interpreter.
            retry_feedback: Validator-Feedback from a previous run.
            previous_inventar: Previous inventar result for retry mode.

        Returns:
            dict with keys: teil_count, teile, aktionen
        """
        # Retry mode: always one-shot with correction hint
        if retry_feedback and previous_inventar:
            return self._extract_oneshot(specification, retry_feedback, previous_inventar)

        if self._is_complex(specification):
            log.info("inventar_sequential_mode", spec_len=len(specification))
            return self._extract_sequential(specification)

        log.info("inventar_oneshot_mode", spec_len=len(specification))
        return self._extract_oneshot(specification)

    def _extract_oneshot(
        self,
        specification: str,
        retry_feedback: str = "",
        previous_inventar: dict | None = None,
    ) -> dict:
        """Single-call extraction (simple specs or retry mode)."""
        system = self._build_system_prompt(specification)
        prompt = INVENTAR_PROMPT_TEMPLATE.format(specification=specification)

        if retry_feedback and previous_inventar:
            import json as _json
            prev_teile = previous_inventar.get("teile", [])
            prev_json = _json.dumps(prev_teile, ensure_ascii=False, indent=2)
            prompt = (
                "★★★ KORREKTUR-MODUS ★★★\n"
                "Dein vorheriger Inventar-Output hatte einen Fehler. Der Validator sagt:\n\n"
                f"  {retry_feedback}\n\n"
                "Dein vorheriges Inventar (TEILE):\n"
                f"{prev_json}\n\n"
                "Erzeuge das Inventar NEU und korrigiere den gemeldeten Fehler.\n"
                "Masse WOERTLICH aus der Spezifikation uebernehmen!\n\n"
                + prompt
            )

        result = self.call_json(prompt, system=system)
        return self._validate(result)

    def _extract_sequential(self, specification: str) -> dict:
        """Two-step extraction for complex multi-part specs.

        Step A: Extract part list only (id, type, raw_params) — no action noise.
        Step B: Per-part, extract actions separately — focused, short input.

        This halves the cognitive load per call and avoids the LLM dropping
        parts when the full spec is too long or too interleaved.
        """
        raw_parts: list[str] = []

        # ── Step A: Teil-Liste ────────────────────────────────────────────
        teile_prompt = TEILE_LISTE_TEMPLATE.format(specification=specification)
        teile_raw = self.call_json(teile_prompt, system=TEILE_LISTE_SYSTEM)
        raw_parts.append("=STEP_A=\n" + getattr(self, "_last_raw_response", ""))
        # LLM sometimes returns a list directly instead of {"teile": [...]}
        if isinstance(teile_raw, list):
            teile = teile_raw
        else:
            teile = teile_raw.get("teile", [])

        if not teile:
            log.warning("inventar_sequential_step_a_empty",
                        spec_len=len(specification))
            # Fallback: one-shot (better than nothing)
            return self._extract_oneshot(specification)

        log.info("inventar_sequential_step_a_done", teil_count=len(teile))

        # Validate teil list basic structure
        valid_teile = []
        for t in teile:
            if not t.get("id") or not t.get("raw_params"):
                log.warning("inventar_step_a_invalid_teil", teil=t)
                continue
            if "type" not in t:
                t["type"] = "box"
            valid_teile.append(t)

        if not valid_teile:
            return self._extract_oneshot(specification)

        # ── Step B: Aktionen pro Teil ─────────────────────────────────────
        aktionen: list[dict] = []
        for teil in valid_teile:
            teil_id = teil["id"]
            teil_beschreibung = teil.get("beschreibung", f"{teil_id} {teil.get('raw_params', {})}")
            aktionen_prompt = AKTIONEN_TEMPLATE.format(
                specification=specification,
                teil_id=teil_id,
                teil_beschreibung=teil_beschreibung,
            )
            try:
                raw = self.call_json(aktionen_prompt, system=AKTIONEN_SYSTEM)
                raw_parts.append(f"=STEP_B_{teil_id}=\n" + getattr(self, "_last_raw_response", ""))
                # Response is either a list or {"aktionen": [...]}
                if isinstance(raw, list):
                    teil_aktionen = raw
                elif isinstance(raw, dict):
                    teil_aktionen = raw.get("aktionen", [])
                else:
                    teil_aktionen = []

                for a in teil_aktionen:
                    if isinstance(a, dict) and a.get("beschreibung"):
                        a["teil_id"] = teil_id
                        if not a.get("seite"):
                            a["seite"] = "oben"
                        aktionen.append(a)

                log.info("inventar_sequential_step_b_done",
                         teil=teil_id, aktionen=len(teil_aktionen))
            except Exception as e:
                log.error("inventar_sequential_step_b_failed",
                          teil=teil_id, error=str(e)[:120])

        self._last_raw_response = "\n".join(raw_parts)
        result = {
            "teil_count": len(valid_teile),
            "teile": valid_teile,
            "aktionen": aktionen,
        }
        return self._validate(result)

    def _validate(self, data: dict) -> dict:
        """Ensure required fields exist and are consistent."""
        if "teile" not in data or not isinstance(data["teile"], list):
            raise ValueError("Inventar: 'teile' fehlt oder ist keine Liste")

        # Ensure teil_count matches
        data["teil_count"] = len(data["teile"])

        # Ensure each teil has required fields
        for teil in data["teile"]:
            if "id" not in teil:
                raise ValueError(f"Inventar: Teil ohne 'id': {teil}")
            if "type" not in teil:
                teil["type"] = "box"  # sensible default
            if "raw_params" not in teil:
                raise ValueError(f"Inventar: Teil '{teil['id']}' ohne 'raw_params'")

        # Ensure aktionen references valid teil_ids and have seite
        valid_seiten = {"oben", "unten", "rechts", "links", "vorne", "hinten"}
        teil_ids = {t["id"] for t in data["teile"]}
        default_teil = data["teile"][0]["id"] if data["teile"] else ""

        for aktion in data.get("aktionen", []):
            # Fix missing or hallucinated teil_id key (e.g. "teil_rag" instead of "teil_id")
            if not aktion.get("teil_id"):
                # Check for common hallucinated key variants
                for wrong_key in ("teil_rag", "teil", "part_id", "id"):
                    if wrong_key in aktion and aktion[wrong_key] in teil_ids:
                        aktion["teil_id"] = aktion.pop(wrong_key)
                        self.log.warning("inventar_fixed_teil_id_key",
                                         wrong_key=wrong_key, teil_id=aktion["teil_id"])
                        break
                # Still no teil_id? Auto-assign to the only/first teil
                if not aktion.get("teil_id"):
                    aktion["teil_id"] = default_teil
                    self.log.warning("inventar_auto_assigned_teil_id",
                                     teil_id=default_teil,
                                     beschreibung=aktion.get("beschreibung", "")[:60])

            if aktion.get("teil_id") and aktion["teil_id"] not in teil_ids:
                self.log.warning("inventar_invalid_aktion_ref",
                                 teil_id=aktion["teil_id"],
                                 valid_ids=list(teil_ids))
            # Validate seite field
            seite = aktion.get("seite", "")
            if seite and seite not in valid_seiten:
                self.log.warning("inventar_invalid_seite",
                                 seite=seite, beschreibung=aktion.get("beschreibung","")[:60])
                aktion["seite"] = ""
            if not seite:
                self.log.warning("inventar_missing_seite",
                                 beschreibung=aktion.get("beschreibung","")[:60])

        if "aktionen" not in data:
            data["aktionen"] = []

        return data