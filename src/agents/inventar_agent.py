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

# Alternative keys the LLM occasionally emits instead of "beschreibung"
# (it tends to name the key after the action's content: "bohrung": "...").
# Normalized to "beschreibung" before the description-gate, otherwise the
# whole action gets silently dropped in _extract_sequential.
_DESCRIPTION_ALIAS_KEYS = (
    "bohrung", "nut", "tasche", "fase", "rundung",
    "aktion", "feature", "description", "desc", "text",
    "breite",
)

# Keys that are NOT a beschreibung (used by the smart fallback below).
_NON_DESCRIPTION_KEYS = frozenset({"seite", "teil_id", "beschreibung"})


def _normalize_aktion_description(a: dict) -> None:
    """In-place: ensure 'beschreibung' is set, recovering from common LLM key
    mis-namings.

    1. Known alias keys (bohrung, breite, ...) win first.
    2. Smart fallback: if no alias matched and exactly one other string field
       exists, treat it as the beschreibung. Catches future typos (e.g.
       'durchmesser', 'tiefe', 'achse') without an exhaustive alias list.
    """
    if not isinstance(a, dict) or a.get("beschreibung"):
        return
    for alt in _DESCRIPTION_ALIAS_KEYS:
        val = a.get(alt)
        if isinstance(val, str) and val.strip():
            a["beschreibung"] = val
            return
    candidates = [
        v for k, v in a.items()
        if k not in _NON_DESCRIPTION_KEYS
        and isinstance(v, str) and v.strip()
    ]
    if len(candidates) == 1:
        a["beschreibung"] = candidates[0]


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

    # Whitelist of dimension param keys (ADR 0007): the chunked Step A
    # filters anything else so hallucinated keys like
    # 'do_not_use_this_id_if_not_needed' can never reach downstream.
    _VALID_PARAM_KEYS = frozenset({
        "x", "y", "z", "r", "h", "d",
        "radius", "hoehe", "höhe", "height",
        "durchmesser", "diameter",
        "laenge", "länge", "length", "breite", "width", "tiefe", "depth",
        "wandstaerke", "wandstärke", "thickness",
    })

    def extract_teile_chunked(self, specification: str) -> dict:
        """Step A via per-declaration micro-calls (ADR 0007).

        For long multi-part specs the one-shot `extract_teile_only` loses
        parts and hallucinates param keys (E_kombo: 11/13 plates + a bogus
        key). This splits the spec into one phrase per part declaration via
        the deterministic `teil_splitter`, runs a focused Step-A micro-call
        per phrase, and merges deterministically (param-key whitelist,
        ID renumbering for uniqueness).

        Falls back to `extract_teile_only` when the splitter finds <= 1
        declaration or all micro-calls fail.
        """
        from src.tools.teil_splitter import split_spec_into_teil_declarations

        # Chunk only when there are genuinely many part declarations — a
        # 2-3 part spec is fine one-shot. The E_kombo bug (13 plates) is the
        # target; EF (1 cube + 1 plate + 11 features) must NOT chunk.
        _CHUNK_THRESHOLD = 4
        decls = split_spec_into_teil_declarations(specification)
        if len(decls) <= _CHUNK_THRESHOLD:
            return self.extract_teile_only(specification)

        raw_parts: list[str] = []
        collected: list[dict] = []
        for i, decl in enumerate(decls):
            # Use only the head (part before the first comma) for the micro-
            # call. The tail carries orientation/anchor/placement noise that
            # references OTHER parts ("...ecke des wuerfels") — feeding the
            # full declaration makes the LLM extract phantom referenced parts
            # (E_kombo crash: 5 phantom 'wuerfel' -> parent-graph cycle).
            decl_head = decl.split(",", 1)[0].strip() or decl.strip()
            prompt = TEILE_LISTE_TEMPLATE.format(specification=decl_head)
            try:
                raw = self.call_json(prompt, system=TEILE_LISTE_SYSTEM)
            except Exception as e:  # noqa: BLE001
                self.log.warning("inventar_chunk_call_failed",
                                 idx=i, decl=decl_head[:60], error=str(e)[:120])
                continue
            raw_parts.append(f"=CHUNK_{i}=\n" + getattr(self, "_last_raw_response", ""))
            teile_raw = raw if isinstance(raw, list) else (raw or {}).get("teile", [])
            # At most ONE part per declaration head — the first valid body.
            for t in teile_raw:
                if not isinstance(t, dict):
                    continue
                rp_in = t.get("raw_params") or {}
                rp = {k: v for k, v in rp_in.items()
                      if k in self._VALID_PARAM_KEYS and isinstance(v, (int, float))}
                if not rp:
                    self.log.warning("inventar_chunk_no_valid_params",
                                     idx=i, teil=t)
                    continue
                collected.append({
                    "_llm_id": str(t.get("id", "") or "").strip(),
                    "type": t.get("type", "box") or "box",
                    "raw_params": rp,
                    "beschreibung": t.get("beschreibung", "") or "",
                })
                break  # one part per chunk

        self._last_raw_response = "=STEP_A_CHUNKED=\n" + "\n".join(raw_parts)

        if not collected:
            self.log.warning("inventar_chunked_all_failed",
                             decl_count=len(decls), spec_len=len(specification))
            return self.extract_teile_only(specification)

        # Deterministic ID renumbering: stem = LLM-id minus trailing _<n>,
        # fall back to type. Singletons keep the stem; >1 of a stem get
        # numbered (<stem>_1, <stem>_2, ...).
        def _stem(c: dict) -> str:
            base = re.sub(r"_\d+$", "", c["_llm_id"]) if c["_llm_id"] else ""
            return base or c["type"] or "teil"

        stem_total: dict[str, int] = {}
        for c in collected:
            s = _stem(c)
            stem_total[s] = stem_total.get(s, 0) + 1

        teile: list[dict] = []
        stem_seen: dict[str, int] = {}
        for c in collected:
            s = _stem(c)
            if stem_total[s] == 1:
                new_id = s
            else:
                stem_seen[s] = stem_seen.get(s, 0) + 1
                new_id = f"{s}_{stem_seen[s]}"
            teil = {"id": new_id, "type": c["type"], "raw_params": c["raw_params"]}
            if c["beschreibung"]:
                teil["beschreibung"] = c["beschreibung"]
            teile.append(teil)

        self.log.info("inventar_teile_chunked_done",
                      decl_count=len(decls), teil_count=len(teile))
        result = {"teil_count": len(teile), "teile": teile, "aktionen": []}
        return self._validate(result)

    def extract_teile_only(self, specification: str) -> dict:
        """Step A only: parts list, no actions.

        Entry point for the per-action chain (ADR 0003 Stufe 5). The action
        extraction that the legacy `extract()` does in Step B is handled by
        the deterministic aktions_splitter and the aktions_klassifizierer
        downstream — Step B is gone.

        Returns the same shape as `extract()` so downstream code that reads
        `inventar["teile"]` keeps working. `aktionen` is always [] in this
        path; callers that still iterate it for the legacy chain will simply
        see no actions and skip work — there is no implicit fallback.
        """
        teile_prompt = TEILE_LISTE_TEMPLATE.format(specification=specification)
        teile_raw = self.call_json(teile_prompt, system=TEILE_LISTE_SYSTEM)
        self._last_raw_response = "=STEP_A=\n" + getattr(
            self, "_last_raw_response", ""
        )

        if isinstance(teile_raw, list):
            teile = teile_raw
        else:
            teile = teile_raw.get("teile", [])

        valid_teile = []
        for t in teile:
            if not isinstance(t, dict):
                continue
            if not t.get("id") or not t.get("raw_params"):
                self.log.warning("inventar_step_a_invalid_teil", teil=t)
                continue
            if "type" not in t:
                t["type"] = "box"
            valid_teile.append(t)

        log.info("inventar_teile_only_done", teil_count=len(valid_teile))

        result = {
            "teil_count": len(valid_teile),
            "teile": valid_teile,
            "aktionen": [],
        }
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
                    if not isinstance(a, dict):
                        continue
                    _normalize_aktion_description(a)
                    if not a.get("beschreibung"):
                        log.warning("inventar_aktion_dropped_no_description",
                                    teil=teil_id, aktion=a)
                        continue
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
            _normalize_aktion_description(aktion)
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