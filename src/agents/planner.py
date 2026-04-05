"""
src/agents/planner.py — Turns a specification into a CSG-Tree Blueprint.

Stufe 5: Planner now produces a validated CSG-Tree Blueprint instead
of free-form JSON. The Coder reads this tree top-down and translates
each node directly into CadQuery operations.

Why a structured tree instead of free JSON?
  Free JSON like {"operations": ["drill hole", "add fillet"]} leaves
  interpretation to the Coder — which causes inconsistent results.
  A CSG-Tree is unambiguous: every node has an exact type and exact
  parameters. The Coder just walks the tree.

Model: qwen3:30b — geometric reasoning needs capacity.
"""

import json
import structlog
from src.config.loader import get_config
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.rag.planner_rag import PlannerRAG
from src.graph.csg_tree import Blueprint
from src.graph.feature_tree import FeatureTree
from src.graph.state import PipelineState
from src.graph.blueprint_utils import apply_patch
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_planner.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT
REVIEW_PROMPT_TEMPLATE = _prompt.REVIEW_PROMPT_TEMPLATE
FIX_PROMPT_TEMPLATE = _prompt.FIX_PROMPT_TEMPLATE

# Patch-mode system prompt — compact instructions for value-only diffs
PATCH_SYSTEM_PROMPT = (
    "You are a JSON patch assistant. Return ONLY a JSON object with a 'changes' list.\n"
    "Each change: {\"path\": \"dot.notation.path\", \"value\": <new_value>}\n"
    "Example: {\"changes\": [{\"path\": \"features.base.params.x\", \"value\": 50}]}\n"
    "Change ONLY the values mentioned. Keep all other fields exactly as-is.\n"
    "Respond with valid JSON only — no explanation, no markdown."
)

# Feature Tree output schema appended to assembled prompts
FEATURE_TREE_OUTPUT_SCHEMA = """
---
## OUTPUT FORMAT: Feature Tree JSON

You MUST output a Feature Tree (not a CSG-Tree). Use this exact JSON schema:

{
  "description": "Short model summary",
  "build_order": ["base", "feature_1", "feature_2"],
  "features": {
    "base": {
      "id": "base",
      "type": "box",
      "params": {"x": 100.0, "y": 100.0, "z": 20.0},
      "parent": null,
      "origin": "global",
      "position": {"x": 0, "y": 0, "z": 0},
      "operation": "add",
      "notes": ""
    },
    "steg": {
      "id": "steg",
      "type": "box",
      "params": {"x": 10.0, "y": 100.0, "z": 20.0},
      "parent": "base",
      "origin": "relative",
      "placement": {
        "face": ">X",
        "alignment": "flush",
        "z_position": "on_top",
        "position": "center",
        "notes": "wall along full Y, flush to +X edge"
      },
      "operation": "add",
      "notes": ""
    },
    "bohrung": {
      "id": "bohrung",
      "type": "hole",
      "params": {"diameter": 10.0, "depth": null},
      "parent": "steg",
      "origin": "relative",
      "placement": {
        "face": ">X",
        "position": "center",
        "notes": "through-hole on right face"
      },
      "operation": "subtract",
      "notes": "depth=null = through-hole"
    }
  },
  "notes": "max 150 chars — brief summary only, NO calculations here"
}

Rules:
- build_order: parent features before their children
- Root feature: parent=null, origin="global", position={x:0,y:0,z:0}
- Child features: parent=<parent id>, origin="relative", use placement (no global coords!)
- placement.face: >Z top, <Z bottom, >X right, <X left, >Y front, <Y back
- placement.position: center / offset(dx,dy) / corner_TL / corner_TR / corner_BL / corner_BR
- placement.alignment: flush_right, flush_left, flush_top, flush_bottom, centered
- placement.z_position: on_top, flush, below
- depth=null means through-hole / through-slot
- Respond with valid JSON only — no markdown, no explanation.
"""

# --- Per-Feature Planning: single FeatureEntry output schema ---
FEATURE_ENTRY_OUTPUT_SCHEMA = """\
Output ONLY a single FeatureEntry JSON (not a full tree):

{
  "type": "box|cylinder|hole|slot|fillet|chamfer|...",
  "params": {"x": float, "y": float, "z": float, "diameter": float, "depth": float|null},
  "placement": {
    "face": ">Z|>X|<X|>Y|<Y",
    "alignment": "flush_right|flush_left|flush_top|flush_bottom|flush_right_top|flush_right_bottom|flush_left_top|flush_left_bottom|centered|null",
    "z_position": "on_top|flush|below|null",
    "position": "center|offset",
    "offset_x": 0.0,
    "offset_y": 0.0,
    "notes": "max 80 chars — brief hint for Coder"
  },
  "operation": "add|subtract|modify"
}

Rules:
- placement.face = die Fläche des Parents, AUF DER das Feature angebracht wird.
  ★ NICHT die Richtung! face bestimmt WO, alignment bestimmt die genaue Position.

  Für Extrusionen (operation=add):
    face=">Z" → Feature wird AUF die Oberseite des Parents gebaut
    face=">X" → Feature wird AN die rechte Seite des Parents gebaut (ragt nach +X raus!)
    "Platte oben rechts" = face: ">Z", alignment: "flush_right"
    "Platte seitlich an rechter Wand" = face: ">X", alignment: "centered"

  Für Bohrungen (operation=subtract):
    face = die Fläche, durch die der Bohrer EINTRITT
    face=">Y" → Bohrung tritt durch Vorderseite (+Y) ein, bohrt in -Y Richtung
    face=">X" → Bohrung tritt durch rechte Seite (+X) ein, bohrt in -X Richtung
    face=">Z" → Bohrung von oben nach unten

- alignment: Position auf der gewählten Face.
  Auf >Z Face: X-Achse = links/rechts, Y-Achse = vorne/hinten
    flush_right = bündig an +X Kante (rechts)
    flush_left  = bündig an -X Kante (links)
    flush_top   = bündig an +Y Kante (hinten)
    flush_bottom = bündig an -Y Kante (vorne)
  Kombinationen:
    flush_right_top = rechts+hinten (Ecke +X/+Y)
    flush_right_bottom = rechts+vorne (Ecke +X/-Y)
    flush_left_top = links+hinten (Ecke -X/+Y)
    flush_left_bottom = links+vorne (Ecke -X/-Y)
  centered = zentriert auf der Face
  ★ Benutze NUR diese exakten Werte! Keine eigenen Kombinationen erfinden!

- ★ Berechne KEINE Offsets! Setze offset_x=0 und offset_y=0.
  Die Offsets werden automatisch aus alignment berechnet.
  NUR bei expliziter Positionsangabe ("10mm von Kante") setze offset_x/offset_y.
- depth=null means through-hole / through-slot
- Respond with valid JSON only — no markdown, no explanation.
"""

# Known alignment values that FunctionDecomposer can process
_KNOWN_ALIGNMENTS = {
    "flush_right", "flush_left", "flush_top", "flush_bottom",
    "flush_right_top", "flush_right_bottom", "flush_left_top", "flush_left_bottom",
    "corner_TR", "corner_TL", "corner_BR", "corner_BL",
    "centered",
}

# Map common LLM-invented alignments to known values
_ALIGNMENT_FIXES = {
    "flush_right_centered": "flush_right",
    "flush_left_centered": "flush_left",
    "flush_top_centered": "flush_top",
    "flush_bottom_centered": "flush_bottom",
    "flush_right_back": "flush_right_top",
    "flush_left_back": "flush_left_top",
    "flush_right_front": "flush_right_bottom",
    "flush_left_front": "flush_left_bottom",
    "right": "flush_right",
    "left": "flush_left",
    "top": "flush_top",
    "bottom": "flush_bottom",
    "center": "centered",
    "flush": "centered",
}


def _normalize_alignment(alignment: str | None) -> str | None:
    """Normalize LLM-invented alignment values to known FunctionDecomposer values."""
    if not alignment:
        return alignment
    a = alignment.strip().lower()
    if a in _KNOWN_ALIGNMENTS:
        return a
    if a in _ALIGNMENT_FIXES:
        log.debug("alignment_normalized", original=alignment, fixed=_ALIGNMENT_FIXES[a])
        return _ALIGNMENT_FIXES[a]
    # Unknown — log and default to centered
    log.warning("alignment_unknown", original=alignment, fallback="centered")
    return "centered"


def _validate_face_choice(face: str, operation: str, parent_params: dict,
                          feature_params: dict, desc_rel: str,
                          logger=None) -> str:
    """Validate and potentially correct the LLM's face choice.

    Catches common LLM errors:
    1. Through-hole on the thinnest dimension (likely wrong direction)
    2. "Von vorne/seitlich" hints mismatched with face choice
    3. Extrusion on side face when "oben" was intended

    Returns corrected face string.
    """
    desc_lower = desc_rel.lower() if desc_rel else ""
    px = float(parent_params.get("x", 0))
    py = float(parent_params.get("y", 0))
    pz = float(parent_params.get("z", 0))

    if not (px and py and pz):
        return face

    # --- Directional hints from description ---
    if operation == "subtract":
        # "Von vorne" → face should involve Y axis
        if any(kw in desc_lower for kw in ("von vorne", "vorderseite", "front")):
            if face not in (">Y", "<Y"):
                if logger:
                    logger.info("face_corrected", original=face, corrected=">Y",
                                reason="desc says 'von vorne'")
                return ">Y"
        # "Von der Seite", "seitlich" → face should be >X or <X (or >Y/<Y)
        if any(kw in desc_lower for kw in ("von der seite", "seitlich", "quer durch")):
            if face in (">Z", "<Z"):
                # Drill through thinnest horizontal dimension
                better = ">X" if px <= py else ">Y"
                if logger:
                    logger.info("face_corrected", original=face, corrected=better,
                                reason="desc says 'seitlich' but face was Z")
                return better
        # "Von oben" → keep >Z
        if any(kw in desc_lower for kw in ("von oben", "oberseite")):
            return face

        # Plausibility: through-hole on >Z but Z is the thinnest dimension
        # AND the description mentions a face dimension hint
        depth_dim = feature_params.get("depth")
        if depth_dim is None and face in (">Z", "<Z"):
            # Through-hole: check if Z is much thinner than X/Y
            # If the description mentions a specific face size, use that
            import re
            face_hint = re.search(r"(\d+)\s*[x×]\s*(\d+)\s*(?:seite|fläche|face)",
                                  desc_lower)
            if face_hint:
                d1, d2 = float(face_hint.group(1)), float(face_hint.group(2))
                # Match face dimensions to parent axes
                # The face the drill enters should have those dimensions
                if _dims_match(d1, d2, px, py):
                    pass  # >Z face is px × py → correct
                elif _dims_match(d1, d2, px, pz):
                    if logger:
                        logger.info("face_corrected", original=face, corrected=">Y",
                                    reason=f"face hint {d1}x{d2} matches >Y face {px}x{pz}")
                    return ">Y"
                elif _dims_match(d1, d2, py, pz):
                    if logger:
                        logger.info("face_corrected", original=face, corrected=">X",
                                    reason=f"face hint {d1}x{d2} matches >X face {py}x{pz}")
                    return ">X"

    return face


def _dims_match(d1: float, d2: float, a1: float, a2: float) -> bool:
    """Check if two dimension pairs match (order-independent)."""
    return (abs(d1 - a1) < 0.1 and abs(d2 - a2) < 0.1) or \
           (abs(d1 - a2) < 0.1 and abs(d2 - a1) < 0.1)


def _resolve_plate_orientation(params: dict, desc_rel: str, specification: str,
                                logger=None) -> dict:
    """Resolve plate orientation from 'X×Y Fläche liegt auf' hints.

    When user says "die 20×80 Fläche liegt auf" for a plate 80×40×20,
    we need to remap params so the contact face becomes the XY plane
    and the remaining dimension becomes Z (height).

    Returns corrected params dict.
    """
    import re

    text = f"{desc_rel} {specification}".lower().replace("×", "x")
    px = float(params.get("x", 0))
    py = float(params.get("y", 0))
    pz = float(params.get("z", 0))
    dims = {px, py, pz}

    if len(dims) < 2 or not all(d > 0 for d in dims):
        return params

    # Look for "AxB Fläche liegt auf" or "AxB Auflagefläche"
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*(?:fläche|auflagefläche|seite)?\s*"
        r"(?:liegt\s*auf|aufliegt|kontakt|auflage)",
        text
    )
    if not m:
        return params

    contact_d1 = float(m.group(1))
    contact_d2 = float(m.group(2))

    # Find which plate dimension is NOT in the contact face → that's the height (Z)
    plate_dims = sorted([px, py, pz])
    contact_sorted = sorted([contact_d1, contact_d2])

    # Match contact dimensions to plate dimensions
    remaining = list(plate_dims)
    matched = []
    for cd in contact_sorted:
        best = min(remaining, key=lambda d: abs(d - cd))
        if abs(best - cd) < 1.0:  # tolerance 1mm
            matched.append(best)
            remaining.remove(best)

    if len(matched) == 2 and len(remaining) == 1:
        height = remaining[0]
        # Contact face = X × Y, height = Z
        # ★ Preserve USER's dimension order from "AxB Fläche liegt auf":
        #   "20×80 Fläche liegt auf" → x=20, y=80 (not x=80, y=20)
        #   This matters for flush_right: x=20 → narrow plate on right edge
        new_x = contact_d1
        new_y = contact_d2
        new_z = height

        if abs(new_x - px) > 0.1 or abs(new_y - py) > 0.1 or abs(new_z - pz) > 0.1:
            if logger:
                logger.info("plate_orientation_corrected",
                            original=f"{px}x{py}x{pz}",
                            corrected=f"{new_x}x{new_y}x{new_z}",
                            contact_face=f"{contact_d1}x{contact_d2}",
                            height=height)
            return {**params, "x": new_x, "y": new_y, "z": height}

    return params


def _parse_root_dimensions(desc_rel: str, specification: str) -> dict | None:
    """Try to extract root body dimensions deterministically from text.

    Looks for patterns like "100x100x20", "∅30mm Höhe 50mm", "Platte 100×100×20mm".
    Returns {"type": "box"|"cylinder", "params": {...}} or None if not parseable.
    """
    import re

    text = f"{desc_rel} {specification}".replace("×", "x").replace("X", "x")

    # Pattern: AxBxC (box dimensions)
    m = re.search(r"(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)", text)
    if m:
        dims = sorted([float(m.group(1)), float(m.group(2)), float(m.group(3))], reverse=True)
        # Convention: largest two → X,Y (horizontal), smallest → Z (height)
        # Unless explicitly stated otherwise
        x, y, z = dims[0], dims[1], dims[2]

        # Check for explicit height indicators
        text_lower = text.lower()
        if "höhe" in text_lower or "hoch" in text_lower:
            h_match = re.search(r"(?:höhe|hoch)\s*[:=]?\s*(\d+(?:\.\d+)?)", text_lower)
            if h_match:
                h = float(h_match.group(1))
                remaining = [d for d in dims if d != h]
                if len(remaining) >= 2:
                    x, y = remaining[0], remaining[1]
                    z = h

        return {"type": "box", "params": {"x": x, "y": y, "z": z}}

    # Pattern: ∅D Höhe H or Durchmesser D Höhe H (cylinder)
    m_cyl = re.search(
        r"(?:∅|durchmesser|⌀)\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*(?:,?\s*)?(?:höhe|h)\s*[:=]?\s*(\d+(?:\.\d+)?)",
        text, re.IGNORECASE
    )
    if m_cyl:
        d = float(m_cyl.group(1))
        h = float(m_cyl.group(2))
        return {"type": "cylinder", "params": {"radius": d / 2, "height": h}}

    return None


# Root feature schema — even simpler
ROOT_FEATURE_SCHEMA = """\
Output ONLY a single root FeatureEntry JSON:

{
  "type": "box|cylinder|sphere",
  "params": {"x": float, "y": float, "z": float},
  "operation": "add"
}

Respond with valid JSON only — no markdown, no explanation.
"""


def _format_parent_context(feature_id: str, params: dict,
                           parent_placement: dict | None = None,
                           parent_parent_params: dict | None = None) -> str:
    """Build a deterministic parent context string for per-feature planning.

    Shows the parent's dimensions and available faces with their areas,
    so the LLM can reason about face selection and offset calculation
    without needing to understand the global assembly.
    """
    px = float(params.get("x", 0))
    py = float(params.get("y", 0))
    pz = float(params.get("z", 0))
    pr = float(params.get("radius", 0))
    ph = float(params.get("height", 0))

    lines = [f'Parent "{feature_id}":']

    if pr > 0 and ph > 0:
        # Cylinder
        d = pr * 2
        lines.append(f"  Typ: Zylinder, ∅{d}mm, Höhe {ph}mm")
        lines.append(f"  Top (>Z): z={ph}, Kreisfläche ∅{d}")
        lines.append(f"  Mantel: Höhe {ph}, Umfang {d*3.14159:.1f}")
    elif px > 0 and py > 0 and pz > 0:
        # Box
        lines.append(f"  Typ: Box {px}×{py}×{pz}mm (X×Y×Z)")
        lines.append(f"  Verfügbare Flächen (face → was darauf platziert wird):")
        lines.append(f"    >Z (Oberseite):     Fläche {px}×{py}mm — für Features die OBEN drauf kommen")
        lines.append(f"    <Z (Unterseite):    Fläche {px}×{py}mm — für Features an der Unterseite")
        lines.append(f"    >X (rechte Seite):  Fläche {py}×{pz}mm — für Features die SEITLICH nach +X ragen")
        lines.append(f"    <X (linke Seite):   Fläche {py}×{pz}mm — für Features die SEITLICH nach -X ragen")
        lines.append(f"    >Y (Vorderseite):   Fläche {px}×{pz}mm — für Features die nach VORNE ragen / Bohrung von vorne")
        lines.append(f"    <Y (Rückseite):     Fläche {px}×{pz}mm — für Features die nach HINTEN ragen / Bohrung von hinten")
        lines.append(f"  ★ 'oben rechts' = face >Z + alignment flush_right (NICHT face >X!)")
    else:
        lines.append(f"  Params: {params}")

    return "\n".join(lines)


class PlannerAgent(BaseAgent):
    """Converts a model specification into a Feature Tree Blueprint.

    Phase 1: outputs Feature Tree JSON (build_order + features dict).
    The Blueprint is validated with Pydantic before being stored in state.
    Falls back to raw dict on validation failure so the pipeline continues.
    """

    model = get_config().models.planner  # set from config.yaml
    name = "planner"

    def __init__(self):
        super().__init__()
        self._rag = PlannerRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("planner_rag_missing", path="data/knowledge/planner")
            self._rag_ready = True

    def review(self, state: PipelineState) -> dict:
        """Review a pre-assembled blueprint and correct errors.

        Called after the Häppchen pipeline (Feature Assigner → Position Assigner
        → Blueprint Assembler) has produced a blueprint. The Planner acts as a
        reviewer: checks the blueprint against the specification and corrects
        only what's wrong. If everything looks good, returns it unchanged.

        Returns {"blueprint": dict}.
        """
        import json as _json

        specification = state.get("specification") or state.get("description", "")
        blueprint = state.get("blueprint", {})
        plan_issues = state.get("plan_validation_issues", "")

        if not blueprint:
            self.log.warning("planner_review_no_blueprint")
            return {"blueprint": {}}

        # If plan_validator or coordinate_validator sent us back with issues,
        # use the fix template instead of the review template.
        if plan_issues:
            self.log.info("planner_review_fix", issues=plan_issues[:80])
            prompt = FIX_PROMPT_TEMPLATE.format(
                validation_errors=plan_issues,
                previous_blueprint=_json.dumps(blueprint, indent=2),
            )
        else:
            self.log.info("planner_review_fresh",
                          features=len(blueprint.get("features", {})),
                          build_order=blueprint.get("build_order", []))
            prompt = REVIEW_PROMPT_TEMPLATE.format(
                specification=specification,
                blueprint_json=_json.dumps(blueprint, indent=2),
            )

        # Inject RAG geometry rules for the reviewer
        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, specification)

        raw = self.call_json(prompt, system=SYSTEM_PROMPT)

        # Validate with Pydantic
        if FeatureTree.is_feature_tree(raw):
            try:
                ft = FeatureTree.model_validate(raw)
                bp_dict = ft.to_dict()
                self.log.info("planner_review_done",
                              description=ft.description[:60],
                              feature_count=len(ft.features))
                return {"blueprint": bp_dict}
            except ValidationError as e:
                self.log.error("planner_review_validation_failed",
                               error=str(e)[:200])
                _err_lines = [l for l in str(e).splitlines()
                              if "pydantic.dev" not in l and l.strip()]
                raw["_validation_error"] = "\n".join(_err_lines)[:300]
                return {"blueprint": raw}
        else:
            # Response doesn't look like Feature Tree — return as-is
            self.log.warning("planner_review_not_feature_tree",
                             keys=list(raw.keys())[:5])
            return {"blueprint": raw}

    def _apply_diff(self, blueprint: dict, diff: dict, change_hint: str = "") -> tuple[dict, int]:
        """Apply a diff returned by the LLM to the existing blueprint.

        Delegates to src.graph.blueprint_utils.apply_patch().
        Returns (updated_blueprint, changes_applied: int)
        """
        return apply_patch(blueprint, diff, change_hint=change_hint)

    def run(self, state: PipelineState) -> dict:
        """Generate or patch a CSG-Tree Blueprint.

        Four modes:
          patch:        modification + previous_blueprint → update existing tree
          revise:       validator_feedback set → fix semantic issue
          plan_fix:     plan_validation_issues set → fix blueprint logic errors
          fresh:        no previous context → build from scratch

        V4: uses assembled_system_prompt from PromptAssembler when available.
        Falls back to SYSTEM_PROMPT when assembler output is missing.
        """
        import json as _json
        specification = state.get("specification") or state.get("description", "")
        feedback = state.get("validator_feedback", "")
        plan_issues = state.get("plan_validation_issues", "")
        change_desc = state.get("change_description", "")
        previous_bp = state.get("previous_blueprint", {})

        # Debug: log which branch will be taken
        _fs = state.get("feature_specs", [])
        self.log.info("planner_run_debug",
                      has_plan_issues=bool(plan_issues),
                      has_feedback=bool(feedback),
                      has_change_desc=bool(change_desc),
                      has_previous_bp=bool(previous_bp),
                      feature_specs_count=len(_fs),
                      feature_specs_has_children=any(s.get("parent") for s in _fs) if _fs else False,
                      plan_issues_preview=plan_issues[:60] if plan_issues else "")

        # V4: use focused assembled system prompt when available.
        # Phase 1: always append FEATURE_TREE_OUTPUT_SCHEMA to ensure Feature Tree output.
        _assembled = state.get("assembled_system_prompt", "")
        if _assembled:
            # Assembled prompt provides task-specific context + RAG examples.
            # Append Feature Tree output schema so LLM outputs correct format.
            active_system = _assembled + FEATURE_TREE_OUTPUT_SCHEMA
        else:
            active_system = SYSTEM_PROMPT
        # prompt_assembler already injected RAG examples into the system prompt —
        # skip the redundant enrich_prompt() on the user prompt to avoid duplicates.
        _has_assembled = bool(_assembled)

        # --- Plan-fix mode: Plan-Validator found logic errors in the blueprint ---
        current_bp = state.get("blueprint", {})
        if plan_issues and not feedback:
            # Try targeted re-planning: extract affected feature IDs from issues
            feature_specs = state.get("feature_specs", [])
            if feature_specs and FeatureTree.is_feature_tree(current_bp):
                affected_ids = self._extract_affected_features(plan_issues, current_bp)
                if affected_ids:
                    self.log.info("planner_plan_fix_targeted",
                                  affected=affected_ids, issues=plan_issues[:80])
                    return self._replan_features(
                        state, feature_specs, current_bp, affected_ids, plan_issues)

            # Fallback: full re-plan
            self.log.info("planner_plan_fix", issues=plan_issues[:80])
            import json as _json3
            bp_context = (
                f"Current Blueprint (fix the issues below — keep everything else):\n"
                f"```json\n{_json3.dumps(current_bp, indent=2)}\n```\n\n"
                if current_bp else ""
            )
            prompt = (
                f"Specification: {specification}\n\n"
                f"{bp_context}"
                f"{plan_issues}\n\n"
                "Return a corrected Feature Tree Blueprint with all issues fixed."
            )
            if not _has_assembled:
                self._ensure_rag()
                prompt = self._rag.enrich_prompt(prompt, specification)
            raw = self.call_json(prompt, system=active_system)

        # --- Revise mode: fix semantic validation failure ---
        # Checked FIRST — validator feedback means the blueprint structure is wrong.
        # A value-diff (patch) cannot fix structural errors like union vs cut.
        elif feedback:
            self.log.info("planner_revise", feedback=feedback[:80])
            import json as _json2
            bp_context = (
                f"Current Blueprint (keep dimensions/structure, fix only what the feedback says):\n"
                f"```json\n{_json2.dumps(current_bp, indent=2)}\n```\n\n"
                if current_bp else ""
            )
            prompt = (
                f"Specification: {specification}\n\n"
                f"{bp_context}"
                f"Validator rejected this blueprint:\n{feedback}\n\n"
                "Return a corrected Feature Tree Blueprint. "
                "Keep all dimensions and geometry from the current blueprint unless the feedback says otherwise."
            )
            if not _has_assembled:
                self._ensure_rag()
                prompt = self._rag.enrich_prompt(prompt, specification)
            # Use revise model (default: 8b) — validator feedback is usually a positional
            # or value fix. Avoids costly VRAM swap back to 30b after coder+validator.
            revise_model = get_config().models.planner_revise
            original_model = self.model
            self.model = revise_model
            raw = self.call_json(prompt, system=active_system)
            self.model = original_model

        # --- Rebuild mode: additive change — patch cannot add new CSG nodes ---
        elif change_desc and previous_bp and state.get("is_additive", False):
            self.log.info("planner_rebuild", change=change_desc[:80])
            # List all existing node types so the model knows what to preserve
            import re as _re
            existing_types = _re.findall(r'"type":\s*"(\w+)"', _json.dumps(previous_bp))
            existing_summary = ", ".join(dict.fromkeys(existing_types))  # unique, ordered
            prompt = (
                f"Existing Blueprint (⚠ PRESERVE ALL existing nodes — only ADD the new feature):\n"
                f"```json\n{_json.dumps(previous_bp, indent=2)}\n```\n\n"
                f"Existing node types that MUST remain: {existing_summary}\n\n"
                f"Change to ADD: {change_desc}\n\n"
                f"Return a complete new Feature Tree Blueprint that includes ALL existing "
                f"geometry (every node above) AND wraps it with the new addition. "
                f"Do NOT remove or restructure any existing nodes."
            )
            if not _has_assembled:
                self._ensure_rag()
                prompt = self._rag.enrich_prompt(prompt, change_desc)
            raw = self.call_json(prompt, system=active_system)

        # --- Patch mode: value-only change (sizes, positions, radii) ---
        elif change_desc and previous_bp:
            self.log.info("planner_patch", change=change_desc[:80])
            prompt = (
                f"Blueprint:\n```json\n{_json.dumps(previous_bp, separators=(',', ':'))}\n```\n\n"
                f"Change: {change_desc}\n\n"
                f"Return only the diff (changed values with dot-notation paths)."
            )
            patch_model = get_config().models.planner_patch
            original_model = self.model
            self.model = patch_model
            diff_response = self.call_json(prompt, system=PATCH_SYSTEM_PROMPT)
            self.model = original_model
            diff_count = len(diff_response.get("changes", []))
            raw, applied = self._apply_diff(previous_bp, diff_response, change_hint=change_desc[:60])

            if applied == 0 or applied < diff_count:
                # Fallback: full rebuild when patch is incomplete or finds nothing
                self.log.warning("planner_patch_incomplete",
                                 applied=applied, requested=diff_count)
                import re as _re2
                existing_types2 = _re2.findall(r'"type":\s*"(\w+)"', _json.dumps(previous_bp))
                existing_summary2 = ", ".join(dict.fromkeys(existing_types2))
                prompt = (
                    f"Existing Blueprint:\n```json\n{_json.dumps(previous_bp, indent=2)}\n```\n\n"
                    f"Existing node types to preserve: {existing_summary2}\n\n"
                    f"Change: {change_desc}\n\n"
                    "Return a complete updated Feature Tree Blueprint with ONLY the requested change applied. "
                    "Keep ALL other dimensions, positions, and geometry unchanged — do NOT remove any existing nodes."
                )
                if not _has_assembled:
                    self._ensure_rag()
                    prompt = self._rag.enrich_prompt(prompt, change_desc)
                raw = self.call_json(prompt, system=active_system)

        # --- Fresh mode: per-feature or single-call ---
        else:
            feature_specs = state.get("feature_specs", [])
            # Per-feature planning: 2+ features with parent-child depth >= 2
            has_children = any(s.get("parent") for s in feature_specs)
            if feature_specs and len(feature_specs) >= 2 and has_children:
                self.log.info("planner_per_feature",
                              specification=specification[:80],
                              feature_count=len(feature_specs))
                return self._plan_per_feature(state, feature_specs)
            else:
                self.log.info("planner_fresh", specification=specification[:80])
                prompt = f"Create a Feature Tree Blueprint for:\n\n{specification}"
                if not _has_assembled:
                    self._ensure_rag()
                    prompt = self._rag.enrich_prompt(prompt, specification)
                raw = self.call_json(prompt, system=active_system)

        # Validate with Pydantic — try Feature Tree first, then CSG-Tree fallback
        if FeatureTree.is_feature_tree(raw):
            try:
                ft = FeatureTree.model_validate(raw)
                bp_dict = ft.to_dict()
                self.log.info("planner_done_feature_tree",
                              description=ft.description[:60],
                              build_order=ft.build_order,
                              feature_count=len(ft.features))
                return {"blueprint": bp_dict}
            except ValidationError as e:
                self.log.error("planner_feature_tree_validation_failed",
                               error=str(e)[:200],
                               raw_keys=list(raw.keys()))
                _err_lines = [l for l in str(e).splitlines()
                              if "pydantic.dev" not in l and l.strip()]
                raw["_validation_error"] = "\n".join(_err_lines)[:300]
                return {"blueprint": raw}
        else:
            # Legacy CSG-Tree fallback (backward compat)
            try:
                blueprint = Blueprint.model_validate(raw)
                bp_dict = blueprint.to_dict()
                self.log.info("planner_done_csg_tree",
                              description=blueprint.description[:60],
                              root_type=blueprint.root.type)
                return {"blueprint": bp_dict}
            except ValidationError as e:
                self.log.error("planner_validation_failed",
                               error=str(e)[:200],
                               raw_keys=list(raw.keys()))
                _err_lines = [l for l in str(e).splitlines()
                              if "pydantic.dev" not in l and l.strip()]
                raw["_validation_error"] = "\n".join(_err_lines)[:300]
                return {"blueprint": raw}

    # ------------------------------------------------------------------
    # Per-Feature Planning
    # ------------------------------------------------------------------

    def _plan_per_feature(self, state: PipelineState, feature_specs: list[dict]) -> dict:
        """Plan each feature individually, building context incrementally.

        Each feature is planned with only its parent's resolved geometry as context.
        This ensures the LLM reasons locally (relative to parent) not globally.

        Returns {"blueprint": dict} — a complete FeatureTree blueprint.
        """
        specification = state.get("specification") or state.get("description", "")
        per_feature_rules = state.get("per_feature_rules", {})

        planned: dict[str, dict] = {}  # feature_id → FeatureEntry dict
        build_order: list[str] = []

        for spec in feature_specs:
            fid = spec["id"]
            ftype = spec.get("type", "unknown")
            parent_id = spec.get("parent")
            desc_rel = spec.get("description_relative", "")

            build_order.append(fid)

            # --- Root feature (no parent) ---
            if parent_id is None:
                # Try deterministic extraction first — root dimensions are
                # usually explicit in the specification ("Platte 100x100x20mm").
                parsed = _parse_root_dimensions(desc_rel, specification)
                if parsed:
                    self.log.info("planner_pf_root_deterministic",
                                  feature=fid, params=parsed)
                    planned[fid] = {
                        "id": fid,
                        "type": parsed.get("type", "box"),
                        "params": parsed["params"],
                        "parent": None,
                        "origin": "global",
                        "position": {"x": 0, "y": 0, "z": 0},
                        "operation": "add",
                        "notes": "",
                    }
                else:
                    # Fallback: ask LLM
                    system = self._get_per_feature_system(
                        ftype, is_root=True,
                        rules_text=per_feature_rules.get(fid, ""))
                    prompt = (
                        f"Gesamtbeschreibung: {specification}\n\n"
                        f"Erstelle das Basis-Feature:\n{desc_rel}\n\n"
                        f"Bestimme Typ und exakte Dimensionen (params)."
                    )
                    original_model = self.model
                    self.model = get_config().models.planner_revise
                    self.log.info("planner_pf_root_llm", feature=fid, type=ftype,
                                  model=self.model)
                    raw_entry = self.call_json(prompt, system=system)
                    self.model = original_model

                    planned[fid] = {
                        "id": fid,
                        "type": raw_entry.get("type", ftype),
                        "params": raw_entry.get("params", {}),
                        "parent": None,
                        "origin": "global",
                        "position": {"x": 0, "y": 0, "z": 0},
                        "operation": "add",
                        "notes": raw_entry.get("notes", ""),
                    }
                continue

            # --- Child feature (has parent) ---
            parent_entry = planned.get(parent_id)
            if not parent_entry:
                self.log.error("planner_pf_missing_parent",
                               feature=fid, parent=parent_id)
                continue

            parent_context = _format_parent_context(
                parent_id, parent_entry.get("params", {}))

            # Sibling summary: other children already placed on the same parent
            siblings = [
                f'  - "{sid}": {s.get("type")} ({s.get("params", {})})'
                for sid, s in planned.items()
                if s.get("parent") == parent_id and sid != fid
            ]
            sibling_text = ""
            if siblings:
                sibling_text = (
                    f"\nBereits auf Parent platziert:\n"
                    + "\n".join(siblings) + "\n"
                )

            system = self._get_per_feature_system(
                ftype, is_root=False,
                rules_text=per_feature_rules.get(fid, ""))
            prompt = (
                f"Gesamtbeschreibung: {specification}\n\n"
                f"{parent_context}\n"
                f"{sibling_text}\n"
                f"Plane dieses Feature relativ zum Parent:\n"
                f"  ID: {fid}\n"
                f"  Beschreibung: {desc_rel}\n\n"
                f"Bestimme: type, params, placement (face, alignment, offset_x, offset_y), operation."
            )

            # Per-feature calls are focused enough for the smaller model
            original_model = self.model
            self.model = get_config().models.planner_revise
            self.log.info("planner_pf_child", feature=fid, type=ftype,
                          parent=parent_id, model=self.model)
            raw_entry = self.call_json(prompt, system=system)
            self.model = original_model

            # Normalize the response into a FeatureEntry dict
            placement = raw_entry.get("placement", {})
            alignment = placement.get("alignment")

            # Normalize invented alignments to known values
            alignment = _normalize_alignment(alignment)

            # When alignment is set, let FunctionDecomposer compute offsets
            # (LLM-computed offsets are often wrong). Only keep explicit offsets
            # when no alignment is set (manual positioning).
            ox = placement.get("offset_x", 0.0)
            oy = placement.get("offset_y", 0.0)
            if alignment and alignment not in ("centered", ""):
                ox = None
                oy = None

            face = placement.get("face", ">Z")
            operation = raw_entry.get("operation", "add")
            feature_params = raw_entry.get("params", {})

            # Resolve plate orientation from "AxB Fläche liegt auf" hints
            if operation == "add" and feature_params:
                feature_params = _resolve_plate_orientation(
                    feature_params, desc_rel, specification, self.log)

            # Post-LLM plausibility: validate face choice against parent geometry
            face = _validate_face_choice(
                face, operation, parent_entry.get("params", {}),
                feature_params, desc_rel, self.log)

            planned[fid] = {
                "id": fid,
                "type": raw_entry.get("type", ftype),
                "params": feature_params,
                "parent": parent_id,
                "origin": "relative",
                "placement": {
                    "face": face,
                    "alignment": alignment,
                    "z_position": placement.get("z_position", "on_top"),
                    "position": placement.get("position", "center"),
                    "offset_x": ox,
                    "offset_y": oy,
                    "notes": placement.get("notes", ""),
                },
                "operation": operation,
                "notes": raw_entry.get("notes", ""),
            }

        # Assemble into a FeatureTree blueprint
        return self._assemble_tree(planned, build_order, specification)

    def _get_per_feature_system(self, feature_type: str, is_root: bool,
                                 rules_text: str = "") -> str:
        """Build a focused system prompt for a single feature planning call.

        Much smaller than the monolithic SYSTEM_PROMPT — only contains
        the output schema + type-specific rules.
        """
        if is_root:
            base = (
                "Du bist ein CAD-Planner. Plane EIN Basis-Feature (Grundkörper).\n"
                "Bestimme den Typ und die exakten Dimensionen.\n\n"
            )
            return base + ROOT_FEATURE_SCHEMA

        base = (
            "Du bist ein CAD-Planner. Plane EIN Feature relativ zu seinem Parent.\n"
            "Du siehst NUR den Parent-Körper und dein Feature — nichts anderes.\n\n"
            "WICHTIG:\n"
            "- Denke NUR relativ zum Parent, NICHT global!\n"
            "- face = die Fläche des Parents, AUF/DURCH die das Feature kommt\n"
            "- alignment = die Position auf dieser Fläche (flush_right, centered, etc.)\n\n"
            "★ TYPISCHE FEHLER VERMEIDEN:\n"
            "- 'Platte oben auf der rechten Seite' → face='>Z' (oben!), alignment='flush_right'\n"
            "  NICHT face='>X'! '>X' bedeutet die Platte ragt seitlich raus!\n"
            "- 'Bohrung von vorne durch die Platte' → face='>Y' (Bohrer tritt vorne ein)\n"
            "  NICHT face='>Z'! '>Z' bohrt von oben nach unten!\n"
            "- 'Bohrung seitlich durch' → face der Seite, durch die der Bohrer eintritt\n"
            "  Bei Box 80×40×20: 'durch die 80×40 Seite' → face='>Y' (40mm Tiefe)\n"
            "  'durch die 80×20 Seite' → face='>Z' (20mm Tiefe)\n"
        )

        if rules_text:
            base += f"\n## Regeln für {feature_type}\n{rules_text}\n"

        base += f"\n{FEATURE_ENTRY_OUTPUT_SCHEMA}"
        return base

    def _assemble_tree(self, planned: dict[str, dict],
                       build_order: list[str],
                       specification: str) -> dict:
        """Combine individually planned features into a FeatureTree blueprint.

        Validates with Pydantic. Falls back to raw dict on validation failure.
        """
        description = specification[:80] if specification else "Model"

        blueprint = {
            "description": description,
            "build_order": build_order,
            "features": planned,
        }

        try:
            ft = FeatureTree.model_validate(blueprint)
            bp_dict = ft.to_dict()
            self.log.info("planner_per_feature_done",
                          description=ft.description[:60],
                          build_order=ft.build_order,
                          feature_count=len(ft.features))
            return {"blueprint": bp_dict}
        except ValidationError as e:
            self.log.error("planner_per_feature_validation_failed",
                           error=str(e)[:200])
            _err_lines = [l for l in str(e).splitlines()
                          if "pydantic.dev" not in l and l.strip()]
            blueprint["_validation_error"] = "\n".join(_err_lines)[:300]
            return {"blueprint": blueprint}

    def _extract_affected_features(self, issues_text: str,
                                    blueprint: dict) -> list[str]:
        """Extract feature IDs mentioned in validation issues text.

        Looks for known feature IDs from the blueprint in the issues string.
        Returns list of affected feature IDs, or empty list if none found.
        """
        features = blueprint.get("features", {})
        affected = []
        issues_lower = issues_text.lower()
        for fid in features:
            if fid.lower() in issues_lower:
                affected.append(fid)
        return affected

    def _replan_features(self, state: PipelineState,
                          feature_specs: list[dict],
                          current_bp: dict,
                          affected_ids: list[str],
                          issues_text: str) -> dict:
        """Re-plan only the affected features, keeping all others unchanged.

        Uses the same per-feature planning approach but only for the features
        that failed validation. Parent context comes from the existing blueprint.
        """
        specification = state.get("specification") or state.get("description", "")
        per_feature_rules = state.get("per_feature_rules", {})

        # Start with existing features
        planned = dict(current_bp.get("features", {}))
        build_order = list(current_bp.get("build_order", []))

        # Build spec lookup
        spec_map = {s["id"]: s for s in feature_specs}

        for fid in affected_ids:
            spec = spec_map.get(fid)
            if not spec:
                continue

            parent_id = spec.get("parent")
            desc_rel = spec.get("description_relative", "")
            ftype = spec.get("type", "unknown")

            if parent_id is None:
                # Re-plan root — unlikely but handle it
                system = self._get_per_feature_system(
                    ftype, is_root=True,
                    rules_text=per_feature_rules.get(fid, ""))
                prompt = (
                    f"Gesamtbeschreibung: {specification}\n\n"
                    f"Erstelle das Basis-Feature:\n{desc_rel}\n\n"
                    f"Vorheriger Fehler: {issues_text}\n\n"
                    f"Bestimme Typ und exakte Dimensionen (params)."
                )
                original_model = self.model
                self.model = get_config().models.planner_revise
                raw_entry = self.call_json(prompt, system=system)
                self.model = original_model

                planned[fid] = {
                    "id": fid,
                    "type": raw_entry.get("type", ftype),
                    "params": raw_entry.get("params", {}),
                    "parent": None,
                    "origin": "global",
                    "position": {"x": 0, "y": 0, "z": 0},
                    "operation": "add",
                    "notes": raw_entry.get("notes", ""),
                }
            else:
                parent_entry = planned.get(parent_id, {})
                parent_context = _format_parent_context(
                    parent_id, parent_entry.get("params", {}))

                system = self._get_per_feature_system(
                    ftype, is_root=False,
                    rules_text=per_feature_rules.get(fid, ""))
                prompt = (
                    f"Gesamtbeschreibung: {specification}\n\n"
                    f"{parent_context}\n\n"
                    f"Plane dieses Feature relativ zum Parent:\n"
                    f"  ID: {fid}\n"
                    f"  Beschreibung: {desc_rel}\n\n"
                    f"Vorheriger Fehler: {issues_text}\n\n"
                    f"Bestimme: type, params, placement (face, alignment, offset_x, offset_y), operation."
                )
                original_model = self.model
                self.model = get_config().models.planner_revise
                self.log.info("planner_replan_feature", feature=fid,
                              parent=parent_id, model=self.model)
                raw_entry = self.call_json(prompt, system=system)
                self.model = original_model

                placement = raw_entry.get("placement", {})
                alignment = placement.get("alignment")
                ox = placement.get("offset_x", 0.0)
                oy = placement.get("offset_y", 0.0)
                if alignment and alignment not in ("centered", ""):
                    ox = None
                    oy = None

                planned[fid] = {
                    "id": fid,
                    "type": raw_entry.get("type", ftype),
                    "params": raw_entry.get("params", {}),
                    "parent": parent_id,
                    "origin": "relative",
                    "placement": {
                        "face": placement.get("face", ">Z"),
                        "alignment": alignment,
                        "z_position": placement.get("z_position", "on_top"),
                        "position": placement.get("position", "center"),
                        "offset_x": ox,
                        "offset_y": oy,
                        "notes": placement.get("notes", ""),
                    },
                    "operation": raw_entry.get("operation", "add"),
                    "notes": raw_entry.get("notes", ""),
                }

        return self._assemble_tree(planned, build_order, specification)