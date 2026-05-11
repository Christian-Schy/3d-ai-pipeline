"""
src/agents/position_normalizer_agent.py — Position normalization (4-step chain).

Four focused mini-calls — one clear question each:
  Step 1 — Frame     : parent / seite / orientierung / anliegende_flaeche
  Step 2 — Alignment : ausrichtung (2D-Platzierung auf der Fläche)
  Step 3 — Anchor    : kind_punkt / eltern_punkt / eltern_abstand  (optional)
  Step 4 — Offset    : winkel / versatz / pre_rotation

Frame chooses WHICH face, Alignment chooses WHERE on that face.
Splitting these two was necessary because alignment vocabulary
(oben/unten/links/rechts) depends on which face was chosen —
on a top face "oben" is really "hinten" etc.
"""

import structlog

from src.agents.base import BaseAgent, DSPY_DIR
from src.config.loader import get_config
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_frame_prompt = load_prompt("prompt_position_frame.py")
_alignment_prompt = load_prompt("prompt_position_alignment.py")
_anchor_prompt = load_prompt("prompt_position_anchor.py")
_offset_prompt = load_prompt("prompt_position_offset.py")

FRAME_SYSTEM = _frame_prompt.SYSTEM_PROMPT
FRAME_TEMPLATE = _frame_prompt.POSITION_FRAME_TEMPLATE

ALIGNMENT_SYSTEM = _alignment_prompt.SYSTEM_PROMPT
_build_alignment_template = _alignment_prompt.build_alignment_template

ANCHOR_SYSTEM = _anchor_prompt.SYSTEM_PROMPT
ANCHOR_TEMPLATE = _anchor_prompt.POSITION_ANCHOR_TEMPLATE

OFFSET_SYSTEM = _offset_prompt.SYSTEM_PROMPT
OFFSET_TEMPLATE = _offset_prompt.POSITION_OFFSET_TEMPLATE


class PositionNormalizerAgent(BaseAgent):
    """Normalizes free-text position descriptions via 4 focused mini-calls.

    Step 1 — Frame     : parent, seite, orientierung, anliegende_flaeche
    Step 2 — Alignment : ausrichtung (wo auf der Fläche)
    Step 3 — Anchor    : kind_punkt, eltern_punkt, eltern_abstand (optional)
    Step 4 — Offset    : winkel, versatz, pre_rotation

    Pipeline-Node-Name + Training-Target: 'platzierer'
    (Class is named PositionNormalizerAgent for historical reasons.)
    """

    name = "platzierer"
    # The runtime agent is a 4-step chain. Do not load the legacy monolithic
    # `platzierer_optimized.json` into every mini-call; each step needs demos
    # in its own output format.
    dspy_demo_fields = None

    _STEP_DEMO_FIELDS = {
        "platzierer_frame": {
            "input_fields": ["teil_id", "teil_type", "teil_params",
                             "alle_teile", "position_sentence"],
            "output_field": "frame",
        },
        "platzierer_alignment": {
            "input_fields": ["seite", "position_sentence"],
            "output_field": "alignment",
        },
        "platzierer_anchor": {
            "input_fields": ["teil_id", "teil_type", "teil_params",
                             "parent", "position_sentence"],
            "output_field": "anchor",
        },
        "platzierer_offset": {
            "input_fields": ["position_sentence"],
            "output_field": "offset",
        },
    }

    def __init__(self):
        cfg = get_config()
        self.model = getattr(cfg.models, "platzierer",
                             getattr(cfg.models, "normalizer",
                                     cfg.models.assembly))
        super().__init__()
        self._step_demos = {
            step: self._load_step_demos(step, fields)
            for step, fields in self._STEP_DEMO_FIELDS.items()
        }

    def _load_step_demos(self, step_name: str, fields: dict) -> list[tuple[str, str]]:
        """Load DSPy demos for one PositionNormalizer mini-call."""
        path = DSPY_DIR / f"{step_name}_optimized.json"
        if not path.exists():
            self.log.info("dspy_step_demos_not_found",
                          step=step_name, path=str(path))
            return []

        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8"))
            demos = data.get("predict", {}).get("demos", [])
        except (OSError, json.JSONDecodeError, KeyError) as e:
            self.log.warning("dspy_step_demos_load_error",
                             step=step_name, error=str(e))
            return []

        pairs: list[tuple[str, str]] = []
        input_fields = fields["input_fields"]
        output_field = fields["output_field"]
        for demo in demos:
            parts = []
            for key in input_fields:
                val = demo.get(key, "")
                if val:
                    parts.append(f"{key}: {val}")
            user_msg = "\n".join(parts)
            assistant_msg = str(demo.get(output_field, "") or "").strip()
            if user_msg and assistant_msg:
                pairs.append((user_msg, assistant_msg))

        self.log.info("dspy_step_demos_loaded",
                      step=step_name, count=len(pairs))
        return pairs

    def normalize(self, teil_id: str, teil_type: str, teil_params: dict,
                  alle_teile: list[dict], specification: str) -> dict:
        """Normalize position for one child part using 3 mini-calls.

        Returns dict with: parent, seite, ausrichtung, orientierung,
                           anliegende_flaeche, abstand, winkel, anker,
                           pre_rotation, notes
        """
        # Collect raw responses for tracing
        raw_parts: list[str] = []

        # Format shared context
        teile_lines = []
        for t in alle_teile:
            params = t.get("raw_params", t.get("params", {}))
            params_str = ", ".join(f"{k}={v}" for k, v in params.items())
            teile_lines.append(f"  {t['id']}: {t.get('type', 'box')} ({params_str})")
        alle_teile_str = "\n".join(teile_lines)
        params_str = ", ".join(f"{k}={v}" for k, v in teil_params.items())

        # Determine parent for anchor call (best effort before parse)
        root_id = alle_teile[0]["id"] if alle_teile else ""

        # ── Step 1: Frame (parent + face + orientation) ─────────────
        frame_prompt = FRAME_TEMPLATE.format(
            specification=specification,
            teil_id=teil_id,
            teil_params=params_str,
            alle_teile=alle_teile_str,
        )
        frame_raw = self.call(
            frame_prompt, system=FRAME_SYSTEM, json_mode=False,
            demos=self._step_demos.get("platzierer_frame", []),
        )
        raw_parts.append("=FRAME=\n" + frame_raw)
        frame = self._parse_kv(frame_raw)

        # ── Step 2: Alignment (wo auf der Fläche) ────────────────────
        seite_for_alignment = frame.get("seite", "oben") or "oben"
        # Template is built per-seite so the face-word cannot appear in keywords
        alignment_prompt = _build_alignment_template(seite_for_alignment).format(
            specification=specification,
        )
        alignment_raw = self.call(
            alignment_prompt, system=ALIGNMENT_SYSTEM, json_mode=False,
            demos=self._step_demos.get("platzierer_alignment", []),
        )
        raw_parts.append("=ALIGNMENT=\n" + alignment_raw)
        alignment = self._parse_kv(alignment_raw)

        # ── Step 3: Anchor (only when input contains anchor language) ──
        parent_id = frame.get("parent", root_id) or root_id
        anchor: dict = {}
        spec_lower = specification.lower()
        _ANCHOR_TRIGGERS = ("ecke", "kante auf", "punkt auf", "auf der kante",
                            "auf die kante", "auf der ecke", "auf die ecke")
        needs_anchor = any(t in spec_lower for t in _ANCHOR_TRIGGERS)
        if needs_anchor:
            anchor_prompt = ANCHOR_TEMPLATE.format(
                specification=specification,
                kind_id=teil_id,
                kind_params=params_str,
                eltern_id=parent_id,
            )
            anchor_raw = self.call(
                anchor_prompt, system=ANCHOR_SYSTEM, json_mode=False,
                demos=self._step_demos.get("platzierer_anchor", []),
            )
            raw_parts.append("=ANCHOR=\n" + anchor_raw)
            anchor = self._parse_kv(anchor_raw)
        else:
            raw_parts.append("=ANCHOR=\n(skipped — no anchor keywords)")

        # ── Step 4: Offset + Rotation ─────────────────────────────────
        offset_prompt = OFFSET_TEMPLATE.format(specification=specification)
        offset_raw = self.call(
            offset_prompt, system=OFFSET_SYSTEM, json_mode=False,
            demos=self._step_demos.get("platzierer_offset", []),
        )
        raw_parts.append("=OFFSET=\n" + offset_raw)
        offset = self._parse_kv(offset_raw)

        self._last_raw_response = "\n".join(raw_parts)

        return self._merge(frame, alignment, anchor, offset, teil_id, alle_teile)

    # ──────────────────────────────────────────────────────────────────
    # Parsing helpers
    # ──────────────────────────────────────────────────────────────────

    def _parse_kv(self, raw: str) -> dict:
        """Parse 'key: value' lines into a flat dict (lowercased keys).

        Same key on multiple lines accumulates into a single comma-joined
        string. This matters for `kantenabstand:` and `versatz:` where the
        model may emit one line per axis (e.g.
        `kantenabstand: oben=10` + `kantenabstand: rechts=10`); without
        accumulation the second overwrites the first and one axis is lost.
        """
        result: dict[str, str] = {}
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            val = val.strip()
            if not val or val == "-":
                continue
            if key in result:
                result[key] = f"{result[key]}, {val}"
            else:
                result[key] = val
        return result

    def _parse_abstand_str(self, text: str) -> dict:
        """Parse 'richtung=mm, richtung=mm' into numeric dict."""
        params = {}
        for part in text.split(","):
            part = part.strip()
            if "=" not in part:
                continue
            k, _, v = part.partition("=")
            k = k.strip().lower()
            v = v.strip()
            try:
                params[k] = float(v) if "." in v else int(v)
            except ValueError:
                params[k] = v
        return params

    def _merge(self, frame: dict, alignment: dict, anchor: dict, offset: dict,
               teil_id: str, alle_teile: list[dict]) -> dict:
        """Merge the 4 step results into the normalized_position dict."""
        known_ids = {t["id"] for t in alle_teile}
        root_id = alle_teile[0]["id"] if alle_teile else ""

        # ── Frame fields ──
        parent = frame.get("parent", "").lower().replace(" ", "_")
        if parent not in known_ids:
            log.warning("pos_normalizer_unknown_parent",
                        parent=parent, fallback=root_id)
            parent = root_id

        seite = frame.get("seite", "oben").lower()
        valid_seiten = {"oben", "unten", "rechts", "links", "vorne", "hinten"}
        if seite not in valid_seiten:
            log.warning("pos_normalizer_invalid_seite", seite=seite)
            seite = "oben"

        orientierung = frame.get("orientierung", "standard").lower()
        anliegende_flaeche = frame.get("anliegende_flaeche", "keine").lower()

        # ── Anchor fields ──
        kind_punkt = anchor.get("kind_punkt", "").lower().replace(" ", "_")
        eltern_punkt = anchor.get("eltern_punkt", "").lower().replace(" ", "_")
        eltern_abstand_raw = anchor.get("eltern_abstand", "")

        # Build anker string (position_builder expects "child_auf_parent" or "")
        has_anchor = bool(kind_punkt and kind_punkt not in ("center", "zentrum", "mitte", "leer")
                          or eltern_punkt and eltern_punkt not in ("center", "zentrum", "mitte", "leer"))
        anker_str = ""
        if has_anchor:
            cp = kind_punkt if kind_punkt else "center"
            pp = eltern_punkt if eltern_punkt else "center"
            anker_str = f"{cp}_auf_{pp}"

        # Parse eltern_abstand → abstand dict with versatz_* keys
        # (position_builder _build_anchor reads versatz_* from abstand)
        abstand: dict = {}
        if eltern_abstand_raw:
            raw_dict = self._parse_abstand_str(eltern_abstand_raw)
            for k, v in raw_dict.items():
                abstand[f"versatz_{k}"] = v

        # ── Offset fields ──
        winkel_raw = offset.get("winkel", "")
        try:
            winkel = float(winkel_raw) if winkel_raw else 0.0
        except ValueError:
            winkel = 0.0

        versatz_raw = offset.get("versatz", "")
        if versatz_raw:
            for k, v in self._parse_abstand_str(versatz_raw).items():
                abstand[f"versatz_{k}"] = v

        # kantenabstand → abstand_<richtung> (position_builder reads abstand_*
        # and produces edge_distances, which the resolver applies face-aware)
        kantenabstand_raw = offset.get("kantenabstand", "")
        if kantenabstand_raw:
            for k, v in self._parse_abstand_str(kantenabstand_raw).items():
                abstand[f"abstand_{k}"] = v

        pre_rotation_raw = offset.get("pre_rotation", "")
        pre_rotation: dict = {}
        if pre_rotation_raw:
            for k, v in self._parse_abstand_str(pre_rotation_raw).items():
                try:
                    pre_rotation[k] = float(v)
                except (TypeError, ValueError):
                    pass

        # ── ausrichtung: from Alignment step (separate mini-call) ──
        ausrichtung = alignment.get("ausrichtung", "zentriert").lower()
        # Override if anchor/offset presence implies a different ausrichtung
        if anker_str and ausrichtung == "zentriert":
            ausrichtung = "von_kanten"
        elif abstand and ausrichtung == "zentriert":
            ausrichtung = "von_mitte"

        return {
            "parent": parent,
            "seite": seite,
            "ausrichtung": ausrichtung,
            "orientierung": orientierung,
            "anliegende_flaeche": anliegende_flaeche,
            "abstand": abstand,
            "winkel": winkel,
            "anker": anker_str,
            "pre_rotation": pre_rotation,
            "notes": "",
        }
