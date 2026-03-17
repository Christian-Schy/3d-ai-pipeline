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
from pathlib import Path
from src.config.loader import get_config
from pydantic import ValidationError
from src.agents.base import BaseAgent
from src.rag.planner_rag import PlannerRAG
from src.graph.csg_tree import Blueprint
from src.graph.state import PipelineState
from src.graph.blueprint_utils import apply_patch

log = structlog.get_logger()

SYSTEM_PROMPT = """You are a 3D modeling planner. Convert a model specification
into a Blueprint using this exact JSON schema.

## Root node (base solid — CSG tree)

Primitives (leaves):
  {"type": "box",      "x": float, "y": float, "z": float, "position": {"x":0,"y":0,"z":0}}
  {"type": "cylinder", "radius": float, "height": float,   "position": {"x":0,"y":0,"z":0}}
  {"type": "sphere",   "radius": float,                    "position": {"x":0,"y":0,"z":0}}

Boolean operations (for stacking boxes, compound shapes):
  {"type": "union",     "target": <node>, "tool": <node>}
  {"type": "cut",       "target": <node>, "tool": <node>}
  {"type": "intersect", "target": <node>, "tool": <node>}

Modifiers (wrap a child — applied last):
  {"type": "fillet",  "radius": float, "edges": "", "child": <node>}   ← "" = all edges, "|Z" = vertical only
  {"type": "chamfer", "distance": float, "edges": "", "child": <node>}  ← "" = all edges, ">Z" = top only
  {"type": "shell",   "thickness": float, "open_face": ">Z", "child": <node>}

Root rules:
- Root = base solid ONLY. Do NOT put holes or slots in the root — use features list.
- Fillets/chamfers ALWAYS wrap their parent, never inside a cut tool.
- For stacking (feature ON TOP): z_center = base_height/2 + feature_height/2
  20mm plate + 20mm box on top → union tool: position z = 10 + 10 = 20

## Features list (CadQuery operations — applied in order after root)

⚠ ALWAYS use feature nodes for holes and slots. NEVER encode them as cut+cylinder or cut+box.

Holes — diameter is in mm directly (NOT radius):
  Single hole:
    {"type": "hole", "diameter": float, "depth": float_or_null,
     "position": {"x": 0, "y": 0}, "face": ">Z"}
    depth=null → through-hole.

  Multiple holes at specific positions:
    {"type": "hole_pattern", "diameter": float, "depth": float_or_null,
     "positions": [[x1,y1], [x2,y2], ...], "face": ">Z"}

  Regular grid:
    {"type": "hole_grid", "diameter": float, "depth": float_or_null,
     "x_spacing": float, "y_spacing": float, "x_count": int, "y_count": int, "face": ">Z"}

  Counterbore (socket-head screws — large flat-bottomed recess + through hole):
    {"type": "cbore_hole", "diameter": float, "cbore_diameter": float, "cbore_depth": float,
     "depth": float_or_null, "position": {"x":0,"y":0}, "face": ">Z"}

  Countersink (flat-head screws — tapered recess):
    {"type": "csk_hole", "diameter": float, "csk_diameter": float, "csk_angle": 82.0,
     "depth": float_or_null, "position": {"x":0,"y":0}, "face": ">Z"}

Slot / Groove:
  {"type": "slot", "length": float, "width": float, "depth": float_or_null,
   "angle": 0, "position": {"x":0,"y":0}, "face": ">Z"}
  depth=null → through-slot.  angle=0 = X-axis slot, angle=90 = Y-axis slot.
  Slot direction: "along X-axis" / "entlang X" → angle=0
                  "along Y-axis" / "entlang Y" → angle=90
  Coder uses rect().cutBlind(-depth) for fixed-depth, slot2D().cutThruAll() for through.
  ⚠ LENGTH FORMULA — to avoid visible walls at the slot ends:
    length = solid_dimension_along_slot + slot_width + 2
    5mm slot through 30mm cube (Y): length = 30 + 5 + 2 = 37
    8mm slot through 40mm plate:    length = 40 + 8 + 2 = 50

Regular polygon extrusion (hex peg, square boss, etc.):
  {"type": "polygon", "sides": 6, "diameter": float, "height": float,
   "position": {"x":0,"y":0,"z":0}, "subtract": false}
  subtract=true cuts shape from solid; subtract=false adds to solid.

Corner cut (right-angle triangular prism removed from a face corner):
  {"type": "corner_cut", "corner_x": float, "corner_y": float,
   "x_leg": float, "y_leg": float, "depth": float, "face": ">Z"}
  corner_x / corner_y: the exact corner coordinates on the face (= ±half dimension of the solid).
  x_leg / y_leg: how far inward to cut along each axis.
  ⚠ Use corner_cut for "remove/cut corner", "Ecke abschneiden", "triangle at corner" — NOT polygon!
  Example: "cut rear-right corner 10mm×10mm, 10mm deep" on 30mm cube (half=15):
    {"type": "corner_cut", "corner_x": 15, "corner_y": -15, "x_leg": 10, "y_leg": 10, "depth": 10, "face": ">Z"}
  Corner key: +X/-Y = rear-right, -X/-Y = rear-left, +X/+Y = front-right, -X/+Y = front-left

Engraved / embossed text:
  {"type": "text", "text": "string", "font_size": float, "depth": float,
   "cut": true, "face": ">Z"}
  cut=true engraves; cut=false embosses.

## Ordering rule — CRITICAL
List ALL hole/* features BEFORE slot features on the same face.
slot2D splits the face — holes listed after a slot may land on the wrong sub-face.

## Positioning rules

EDGE-RELATIVE POSITIONING — "Xmm from the [edge]" or "at corner":
  ⚠ Models are CENTERED at origin — edges are at ±HALF the dimension!
  Formula for -Y/near edge: center = -(half_dim) + offset
  Formula for +X/far edge:  center = +(half_dim) - offset
  Examples:
    "10mm from -Y edge" on 30mm cube (half=15): y = -15 + 10 = -5
    "20mm from edge"    on 200×200 plate (half=100): offset = 100-20 = 80 → x = ±80, y = ±80
  ⚠ NEVER default to (0,0) when spec says "from edge".
  ⚠ "Xmm from edge" means distance D from the WALL, NOT from center. Offset = half_dim - D.
     Do NOT subtract hole radius — D is the gap from the wall to the hole CENTER.

CORNER PATTERN — plate W×L, holes at distance D from corners:
  x_offset = W/2 - D,  y_offset = L/2 - D
  positions: [[+x_off,+y_off], [-x_off,+y_off], [+x_off,-y_off], [-x_off,-y_off]]
  Example: "20mm from edge" on 200×200mm plate → x_offset = 100-20 = 80, y_offset = 80
    positions: [[80,80],[-80,80],[80,-80],[-80,-80]]

FACE SELECTOR FOR STACKED UNIONS — when a box/cylinder is stacked ON TOP of the base plate:
  The base plate and the stacked part have DIFFERENT top-face Z heights.
  faces(">Z") selects the HIGHEST Z face — which is the stacked PART's top, NOT the plate.
  ⚠ If a hole belongs to the BASE PLATE (not the stacked part), use face: ">Z[-2]"
    to select the second-highest Z face (= the plate's top surface).
  Example: 200×200×10mm plate with a 100×100×20mm cube on top (cube top at Z=30, plate top at Z=10):
    - Holes in the PLATE → face: ">Z[-2]"  (selects Z=10 plate top)
    - Holes in the CUBE  → face: ">Z"      (selects Z=30 cube top)

RESIZE CORNER FEATURE — when resizing a box/feature at a corner, recompute center:
  new_center = ±(half_plate - half_NEW_feature)  NOT the old coordinates!

## Depth handling — CRITICAL
- Spec says "Xmm tief/deep" → depth=X (blind), NEVER depth=null
- Spec says "durchgehend/through/komplett durch" → depth=null
- Spec does NOT mention depth → depth=null (through by default)
- NEVER silently change a specified depth to null or vice versa
Examples:
  "Bohrung 10mm Durchmesser, 29mm tief" → {"type":"hole", "diameter":10, "depth":29}
  "Bohrung 10mm durchgehend"            → {"type":"hole", "diameter":10, "depth":null}
  "Bohrung 10mm"                        → {"type":"hole", "diameter":10, "depth":null}

## Feature completeness — MANDATORY
Before outputting the blueprint:
1. Count ALL features mentioned in the specification
2. Verify EACH feature appears in the "features" list
3. If spec says "hole AND slot" → features list MUST contain BOTH

SELF-CHECK before responding:
- Spec mentions N features → my features list has N entries?
- Each feature type matches? (hole→hole, slot→slot, not hole→slot)
- Each feature has ALL required parameters? hole: diameter + depth. slot: length + width + depth + angle.

## Output format
{
  "description": "Short human-readable summary",
  "root": { ...base solid... },
  "features": [ ...ordered hole/slot/polygon/text operations... ],
  "notes": "Optional: tolerances, assembly notes, tricky geometry"
}

Rules:
- Respond with valid JSON only — no explanation, no markdown.
- features=[] when the model has no holes/slots/text.
- All dimensions in mm. Positions relative to model center origin."""


PATCH_SYSTEM_PROMPT = Path("data/prompts/agents/planner_patch.md").read_text(encoding="utf-8")


class PlannerAgent(BaseAgent):
    """Converts a model specification into a validated CSG-Tree Blueprint.

    The Blueprint is validated with Pydantic before being stored in state.
    If validation fails, a clear error is returned rather than a silent bad blueprint.
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

        # V4: use focused assembled system prompt when available
        active_system = state.get("assembled_system_prompt", "") or SYSTEM_PROMPT
        # prompt_assembler already injected RAG examples into the system prompt —
        # skip the redundant enrich_prompt() on the user prompt to avoid duplicates.
        _has_assembled = bool(state.get("assembled_system_prompt", ""))

        # --- Plan-fix mode: Plan-Validator found logic errors in the blueprint ---
        current_bp = state.get("blueprint", {})
        if plan_issues and not feedback:
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
                "Return a corrected CSG-Tree Blueprint with all issues fixed."
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
                "Return a corrected CSG-Tree Blueprint. "
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
                f"Return a complete new CSG-Tree Blueprint that includes ALL existing "
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
                    "Return a complete updated Blueprint with ONLY the requested change applied. "
                    "Keep ALL other dimensions, positions, and geometry unchanged — do NOT remove any existing nodes."
                )
                if not _has_assembled:
                    self._ensure_rag()
                    prompt = self._rag.enrich_prompt(prompt, change_desc)
                raw = self.call_json(prompt, system=active_system)

        # --- Fresh mode: build from scratch ---
        else:
            self.log.info("planner_fresh", specification=specification[:80])
            prompt = f"Create a CSG-Tree Blueprint for:\n\n{specification}"
            if not _has_assembled:
                self._ensure_rag()
                prompt = self._rag.enrich_prompt(prompt, specification)
            raw = self.call_json(prompt, system=active_system)

        # Validate with Pydantic — catches structural errors immediately
        try:
            blueprint = Blueprint.model_validate(raw)
            bp_dict = blueprint.to_dict()
            self.log.info("planner_done",
                          description=blueprint.description[:60],
                          root_type=blueprint.root.type,
                          blueprint_json=json.dumps(bp_dict, ensure_ascii=False, separators=(',', ':')))
            return {"blueprint": bp_dict}

        except ValidationError as e:
            # Log what was wrong — return raw dict as fallback so pipeline continues
            self.log.error("planner_validation_failed",
                           error=str(e)[:200],
                           raw_keys=list(raw.keys()))
            # Store compact error (strip pydantic URL lines, truncate)
            _err_lines = [l for l in str(e).splitlines()
                          if "pydantic.dev" not in l and l.strip()]
            raw["_validation_error"] = "\n".join(_err_lines)[:300]
            return {"blueprint": raw}